"""Decision Dossier proof: fetch the signed packet, verify it offline, and show a one-byte tamper fail."""

import json
import shutil
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Literal

import httpx
from pydantic import BaseModel

from sitework.config import Settings

VERIFIER = "@decionis/verify@0.5.0"
JWKS_PATH = "/.well-known/decision-dossier-jwks.json"


class ProofError(RuntimeError):
    """The packet could not be fetched or the verifier could not run."""


class VerifyResult(BaseModel):
    verified: bool
    mode: Literal["offline", "pinned"]
    file: str
    artifact_paths: list[str] = []
    coverage: bool = False
    trust: str = ""
    issuer_authentic: bool = False
    checked_at: datetime


class TamperResult(BaseModel):
    file: str
    pointer: str  # JSON pointer of the changed string, inside a signed artifact
    before: str
    after: str
    bytes_changed: int
    result: VerifyResult


class ProofFiles:
    """Where packets live: data/dossiers/proof/<dossier_id>.json, the saved JWKS, tampered copies."""

    def __init__(self, directory: Path):
        self.directory = directory

    def packet(self, dossier_id: str) -> Path:
        return self.directory / f"{dossier_id}.json"

    def tampered(self, dossier_id: str) -> Path:
        return self.directory / f"{dossier_id}.tampered.json"

    @property
    def jwks(self) -> Path:
        return self.directory / "jwks.json"


class ProofFetcher:
    """Downloads a dossier's signed proof packet and the Decionis dossier JWKS once, then works offline."""

    def __init__(self, settings: Settings, files: ProofFiles, transport: httpx.BaseTransport | None = None):
        key = settings.decionis_api_key
        self.settings = settings
        self.files = files
        self.http = httpx.Client(timeout=settings.request_timeout, transport=transport,
                                 headers={"Authorization": f"Bearer {key.get_secret_value()}"} if key else {})
        self.public = httpx.Client(timeout=settings.request_timeout, transport=transport)  # no credentials

    def fetch(self, dossier_id: str) -> Path:
        path = self.files.packet(dossier_id)
        if path.exists():
            return path
        base = self.settings.decionis_api_base.rstrip("/")
        res = self.http.get(f"{base}/v1/protocol/dossiers/{dossier_id}/proof-packet",
                            params={"org_id": self.settings.decionis_org_id})
        if res.status_code != 200:
            raise ProofError(f"proof packet for {dossier_id}: HTTP {res.status_code}")
        self._write(path, res.json())
        if not self.files.jwks.exists():
            jwks = self.public.get(f"{base}{JWKS_PATH}")
            if jwks.status_code != 200:
                raise ProofError(f"dossier JWKS: HTTP {jwks.status_code}")
            self._write(self.files.jwks, jwks.json())
        return path

    @staticmethod
    def _write(path: Path, body: dict) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(body, indent=1))


class Verifier:
    """Runs the published `@decionis/verify` CLI. Offline uses the saved JWKS; pinned uses Decionis's URL."""

    def __init__(self, settings: Settings, files: ProofFiles, runner=subprocess.run):
        self.files = files
        self.pinned_jwks = settings.decionis_api_base.rstrip("/") + JWKS_PATH
        self.runner = runner

    def verify(self, file: Path, mode: Literal["offline", "pinned"] = "offline") -> VerifyResult:
        if shutil.which("npx") is None:
            raise ProofError("npx not found; install Node 18+")
        jwks = str(self.files.jwks) if mode == "offline" else self.pinned_jwks
        out = self.runner(["npx", "-y", VERIFIER, "--file", str(file), "--jwks", jwks, "--json"],
                          capture_output=True, text=True, timeout=120)
        if out.returncode not in (0, 1):
            raise ProofError(f"verifier exit {out.returncode}: {out.stderr.strip()[:300]}")
        report = json.loads(out.stdout)
        return VerifyResult(
            verified=report.get("verified") is True and out.returncode == 0, mode=mode, file=file.name,
            artifact_paths=report.get("verified_artifact_paths") or [],
            coverage=report.get("required_artifact_coverage_verified") is True,
            trust=(report.get("trust_anchor") or {}).get("status", ""),
            issuer_authentic=report.get("decionis_issuer_authenticity_verified") is True,
            checked_at=datetime.now(timezone.utc),
        )


class Tamper:
    """Changes exactly one byte of one string inside a signed artifact of a saved packet."""

    def one_byte(self, src: Path, dst: Path) -> tuple[str, str, str, int]:
        packet = json.loads(src.read_text())
        dossier = packet.get("dossier", packet)
        signed = [a["document_path"] for a in packet.get("proof_bundle", dossier.get("integrity", {})
                                                          .get("proof_bundle", {})).get("artifacts", [])]
        for root in signed:
            found = _first_string(_resolve(dossier, root), root)
            if found:
                pointer, value = found
                break
        else:
            raise ProofError("no string inside a signed artifact to change")
        changed = value[:-1] + (value[-1].swapcase() if value[-1].isalpha() and value[-1].isascii()
                                else ("1" if value[-1] != "1" else "2"))
        _assign(dossier, pointer, changed)
        before, after = json.dumps(json.loads(src.read_text()), indent=1), json.dumps(packet, indent=1)
        dst.write_text(after)
        return f"/dossier{pointer}" if "dossier" in packet else pointer, value, changed, \
            sum(a != b for a, b in zip(before.encode(), after.encode()))


class Proofs:
    """The dossier-proof facade the app and scripts use."""

    def __init__(self, settings: Settings, fetcher: ProofFetcher | None = None, verifier: Verifier | None = None):
        self.files = ProofFiles(settings.data_dir / "dossiers" / "proof")
        self.fetcher = fetcher or ProofFetcher(settings, self.files)
        self.verifier = verifier or Verifier(settings, self.files)

    def verify(self, dossier_id: str, mode: Literal["offline", "pinned"] = "offline") -> VerifyResult:
        return self.verifier.verify(self.fetcher.fetch(dossier_id), mode)

    def tamper(self, dossier_id: str) -> TamperResult:
        src = self.fetcher.fetch(dossier_id)
        dst = self.files.tampered(dossier_id)
        pointer, before, after, changed = Tamper().one_byte(src, dst)
        return TamperResult(file=dst.name, pointer=pointer, before=before, after=after, bytes_changed=changed,
                            result=self.verifier.verify(dst, "offline"))


def _resolve(doc, pointer: str):
    for part in [p for p in pointer.split("/") if p]:
        doc = doc[int(part)] if isinstance(doc, list) else doc[part.replace("~1", "/").replace("~0", "~")]
    return doc


def _first_string(node, pointer: str) -> tuple[str, str] | None:
    if isinstance(node, str) and node:
        return pointer, node
    items = node.items() if isinstance(node, dict) else enumerate(node) if isinstance(node, list) else []
    for key, value in items:
        found = _first_string(value, f"{pointer}/{key}")
        if found:
            return found
    return None


def _assign(doc, pointer: str, value) -> None:
    parts = [p for p in pointer.split("/") if p]
    parent = _resolve(doc, "/" + "/".join(parts[:-1]))
    last = parts[-1]
    parent[int(last) if isinstance(parent, list) else last] = value
