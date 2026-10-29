"""Amendment and recall watch: Tavily Research -> policy.update proposal -> Decionis gate -> named person.

  uv run python scripts/watch.py --jurisdiction SE run              # one research task, then the gate
  uv run python scripts/watch.py --jurisdiction SE run --from-result research.json
  uv run python scripts/watch.py list
  uv run python scripts/watch.py resolve <proposal_id> --approve --approver "Full Name" [--note "..."]
"""

import argparse
import json
import sys
from pathlib import Path

from sitework.config import get_settings
from sitework.gate.authority import make_gate
from sitework.ground.packs import PackStore
from sitework.ground.watch import AmendmentWatch, PolicyUpdate, Proposal, ProposalStore
from sitework.ground.web import WebClient


def show(p: Proposal) -> None:
    ex = p.exchange or {}
    verdict = (ex.get("result") or {})
    decision = verdict.get("decision") or f"NO DECISION ({verdict.get('error', '')})"
    print(f"{p.id}  {p.jurisdiction}  {p.status}  gate={decision}  dossier={verdict.get('dossier_id', '')}")
    for f in p.findings:
        flag = "" if f.allowlisted else "  [source not on allowlist]"
        print(f"  - {f.kind:12} {f.scene:8} {f.effective_date:10} {f.title}\n    {f.source_url}{flag}")
    if p.resolved_by:
        print(f"  resolved by {p.resolved_by} at {p.resolved_at:%Y-%m-%d %H:%M} UTC {p.note}")


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--jurisdiction", default=None)
    sub = ap.add_subparsers(dest="cmd", required=True)
    r = sub.add_parser("run")
    r.add_argument("--from-result", type=Path, help="reuse a saved research result instead of a new task")
    sub.add_parser("list")
    s = sub.add_parser("resolve")
    s.add_argument("proposal_id")
    s.add_argument("--approve", action="store_true")
    s.add_argument("--reject", action="store_true")
    s.add_argument("--approver", required=True)
    s.add_argument("--note", default="")
    args = ap.parse_args(argv)
    settings = get_settings()
    store = ProposalStore(settings.data_dir / "proposals")
    if args.cmd == "list":
        for p in store.all():
            show(p)
        return 0
    if args.cmd == "resolve":
        if args.approve == args.reject:
            ap.error("choose exactly one of --approve or --reject")
        show(PolicyUpdate(None, store).resolve(args.proposal_id, args.approve, args.approver, args.note))
        return 0
    pack = PackStore(settings.data_dir / "packs").load(args.jurisdiction or settings.sitework_jurisdiction)
    if args.from_result:
        saved = json.loads(args.from_result.read_text())
        watch = AmendmentWatch(None, pack)
        result = saved["result"]
        proposal = watch.proposal(result["request_id"], saved["question"], result)
    else:
        watch = AmendmentWatch(WebClient(settings), pack)
        proposal = watch.proposal(*watch.run())
    show(PolicyUpdate(make_gate(settings), store).propose(proposal))
    return 0


if __name__ == "__main__":
    sys.exit(main())
