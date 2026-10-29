import json
from types import SimpleNamespace

import httpx
import pytest

from sitework.config import Settings
from sitework.proof import ProofFetcher, ProofFiles, Proofs, Tamper, Verifier

PACKET = {
    "packet_type": "decionis.decision_dossier.proof_packet",
    "dossier": {"dossier_id": "d-1", "portable_artifact": {"artifact": {"kind": "Decision Dossier", "n": 3}},
                "inputs_snapshot": {"decision_type": "inspection.release_hold"}},
    "proof_bundle": {"artifacts": [{"document_path": "/portable_artifact"}, {"document_path": "/inputs_snapshot"}]},
}


def settings(tmp_path) -> Settings:
    return Settings(_env_file=None, data_dir=tmp_path, decionis_api_key="runtime-key", decionis_org_id="org-1")


def test_tamper_changes_exactly_one_byte_inside_a_signed_artifact(tmp_path):
    src, dst = tmp_path / "p.json", tmp_path / "t.json"
    src.write_text(json.dumps(PACKET, indent=1))
    pointer, before, after, changed = Tamper().one_byte(src, dst)
    assert pointer == "/dossier/portable_artifact/artifact/kind"
    assert (before, after, changed) == ("Decision Dossier", "Decision DossieR", 1)
    assert json.loads(dst.read_text())["dossier"]["inputs_snapshot"] == PACKET["dossier"]["inputs_snapshot"]


def test_fetcher_saves_packet_and_jwks_and_never_sends_the_key_for_jwks(tmp_path):
    seen = []

    def respond(request):
        seen.append(request)
        if request.url.path.endswith("/proof-packet"):
            assert request.url.params["org_id"] == "org-1"
            return httpx.Response(200, json=PACKET)
        return httpx.Response(200, json={"keys": [{"kid": "k1"}]})

    files = ProofFiles(tmp_path / "proof")
    path = ProofFetcher(settings(tmp_path), files, transport=httpx.MockTransport(respond)).fetch("d-1")
    assert json.loads(path.read_text()) == PACKET and json.loads(files.jwks.read_text())["keys"][0]["kid"] == "k1"
    assert seen[0].headers["authorization"] == "Bearer runtime-key"
    assert "authorization" not in seen[1].headers
    ProofFetcher(settings(tmp_path), files, transport=httpx.MockTransport(respond)).fetch("d-1")
    assert len(seen) == 2  # cached: offline from here on


def fake_cli(report: dict, code: int):
    calls = []

    def run(cmd, **kwargs):
        calls.append(cmd)
        return SimpleNamespace(returncode=code, stdout=json.dumps(report), stderr="")
    return run, calls


@pytest.mark.parametrize("mode,jwks_suffix", [("offline", "jwks.json"), ("pinned", "/.well-known/decision-dossier-jwks.json")])
def test_verifier_runs_the_pinned_cli_and_reads_its_report(tmp_path, mode, jwks_suffix):
    run, calls = fake_cli({"verified": True, "verified_artifact_paths": ["/portable_artifact"],
                           "required_artifact_coverage_verified": True,
                           "trust_anchor": {"status": "DECIONIS_OFFICIAL"},
                           "decionis_issuer_authenticity_verified": True}, 0)
    files = ProofFiles(tmp_path)
    r = Verifier(settings(tmp_path), files, runner=run).verify(tmp_path / "p.json", mode)
    cmd = calls[0]
    assert cmd[:3] == ["npx", "-y", "@decionis/verify@0.5.0"] and cmd[cmd.index("--jwks") + 1].endswith(jwks_suffix)
    assert r.verified and r.coverage and r.trust == "DECIONIS_OFFICIAL" and r.mode == mode


def test_exit_code_one_is_invalid_even_if_the_report_says_otherwise(tmp_path):
    run, _ = fake_cli({"verified": True}, 1)
    assert not Verifier(settings(tmp_path), ProofFiles(tmp_path), runner=run).verify(tmp_path / "p.json").verified


def test_tamper_is_verified_again_and_reported(tmp_path):
    class Fetcher:
        def fetch(self, dossier_id):
            path = tmp_path / "dossiers" / "proof" / f"{dossier_id}.json"
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(json.dumps(PACKET, indent=1))
            return path

    run, calls = fake_cli({"verified": False, "verified_artifact_paths": ["/inputs_snapshot"]}, 1)
    s = settings(tmp_path)
    proofs = Proofs(s, fetcher=Fetcher(), verifier=Verifier(s, ProofFiles(tmp_path), runner=run))
    t = proofs.tamper("d-1")
    assert t.bytes_changed == 1 and not t.result.verified and calls[0][calls[0].index("--file") + 1].endswith(
        "d-1.tampered.json")
