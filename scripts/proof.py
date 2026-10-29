"""Verify a Decionis Decision Dossier offline, against the pinned key, and after a one-byte tamper.

  uv run python scripts/proof.py <dossier_id>            # offline, saved JWKS
  uv run python scripts/proof.py <dossier_id> --pinned   # also against the pinned Decionis JWKS URL
  uv run python scripts/proof.py <dossier_id> --tamper   # flip one byte in a signed artifact, verify again
"""

import argparse
import sys

from sitework.config import get_settings
from sitework.proof import Proofs, VerifyResult


def line(r: VerifyResult) -> str:
    status = "VALID" if r.verified else "INVALID"
    return (f"{status:7} {r.mode:7} {r.file}  artifacts={r.artifact_paths} coverage={r.coverage} "
            f"trust={r.trust} issuer_authentic={r.issuer_authentic}")


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("dossier_id")
    p.add_argument("--pinned", action="store_true")
    p.add_argument("--tamper", action="store_true")
    args = p.parse_args(argv)
    proofs = Proofs(get_settings())
    ok = proofs.verify(args.dossier_id, "offline")
    print(line(ok))
    if args.pinned:
        print(line(proofs.verify(args.dossier_id, "pinned")))
    if args.tamper:
        t = proofs.tamper(args.dossier_id)
        print(f"tampered {t.pointer}: {t.before!r} -> {t.after!r} ({t.bytes_changed} byte changed)")
        print(line(t.result))
        return 0 if ok.verified and not t.result.verified else 1
    return 0 if ok.verified else 1


if __name__ == "__main__":
    sys.exit(main())
