"""Build a jurisdiction pack: find candidate clauses with Tavily, then a named person approves a threshold.

  uv run python scripts/pack.py search decking "deck board spacing gap between boards"
  uv run python scripts/pack.py approve decking 2 --requirement "..." \
      --threshold '{"gap_mm": {"min": 3.2, "max": 6.4}}' --approver "Full Name"
  uv run python scripts/pack.py show
"""

import argparse
import json
import sys

from sitework.config import Settings, get_settings
from sitework.ground.citation import Clause, ClauseFinder
from sitework.ground.packs import PackStore
from sitework.ground.web import WebClient

KEYWORDS = {
    "decking": ["gap", "spacing", "space between", "spaced"],
    "trench": ["slope", "sloping", "angle", "horizontal to", "vertical"],
}


class PackCli:
    """Search proposes; only `approve`, with a person's name, adds a requirement to the pack."""

    def __init__(self, settings: Settings, jurisdiction: str):
        self.settings = settings
        self.store = PackStore(settings.data_dir / "packs")
        self.pack = self.store.load(jurisdiction)
        self.candidates = settings.data_dir / "packs" / "candidates" / f"{jurisdiction}-{{scene}}.json"

    def search(self, scene: str, query: str, max_results: int) -> int:
        domains = self.pack.allowlist.get(scene)
        if not domains:
            print(f"no allowlist for {scene} in {self.store.path(self.pack.jurisdiction)}")
            return 1
        web = WebClient(self.settings)
        hits = web.search(query, domains, max_results=max_results)
        pages = web.extract([h.url for h in hits], domains)
        finder = ClauseFinder(KEYWORDS.get(scene, []))
        clauses = [c for page in pages for c in finder.find(page)]
        path = self._candidates(scene)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps([c.model_dump(mode="json") for c in clauses], indent=2) + "\n")
        for i, c in enumerate(clauses):
            print(f"[{i}] {c.source_domain}  mm={c.mm_values}\n    {c.excerpt}\n    {c.url}")
        print(f"{len(clauses)} candidates from {len(pages)} pages saved to {path}")
        return 0

    def approve(self, scene: str, index: int, requirement: str, threshold: str, approver: str) -> int:
        clauses = [Clause.model_validate(c) for c in json.loads(self._candidates(scene).read_text())]
        req = self.pack.approve(scene, clauses[index], requirement, json.loads(threshold), approver)
        path = self.store.save(self.pack)
        print(f"approved by {req.approved_by}: {req.requirement} {req.threshold}\n  {req.clause.url}\n-> {path}")
        return 0

    def show(self) -> int:
        print(f"{self.pack.jurisdiction}: allowlist {self.pack.allowlist}")
        for r in self.pack.requirements:
            print(f"- [{r.scene}] {r.requirement} {r.threshold}  ({r.clause.source_domain}, "
                  f"approved by {r.approved_by} {r.approved_at:%Y-%m-%d})")
        return 0

    def _candidates(self, scene: str):
        return self.candidates.with_name(self.candidates.name.format(scene=scene))


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--jurisdiction", default=None)
    sub = p.add_subparsers(dest="cmd", required=True)
    s = sub.add_parser("search")
    s.add_argument("scene")
    s.add_argument("query")
    s.add_argument("--max-results", type=int, default=5)
    a = sub.add_parser("approve")
    a.add_argument("scene")
    a.add_argument("index", type=int)
    a.add_argument("--requirement", required=True, help="short structured statement of the rule")
    a.add_argument("--threshold", required=True, help='JSON, e.g. {"gap_mm": {"min": 3.2, "max": 6.4}}')
    a.add_argument("--approver", required=True, help="your full name; recorded in the pack")
    sub.add_parser("show")
    args = p.parse_args(argv)
    settings = get_settings()
    cli = PackCli(settings, args.jurisdiction or settings.sitework_jurisdiction)
    if args.cmd == "search":
        return cli.search(args.scene, args.query, args.max_results)
    if args.cmd == "approve":
        return cli.approve(args.scene, args.index, args.requirement, args.threshold, args.approver)
    return cli.show()


if __name__ == "__main__":
    sys.exit(main())
