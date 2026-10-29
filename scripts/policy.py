"""Load the SiteWork rules into the Decionis workspace policy without touching anything else.

  uv run python scripts/policy.py plan          # show what would be submitted (default)
  uv run python scripts/policy.py submit --yes  # submit it with DECIONIS_POLICY_API_KEY
  uv run python scripts/policy.py current       # which bundle hosted evaluation runs now

The new bundle is the active bundle with every non-SiteWork rule kept verbatim, previous
`sitework_*` rules replaced by policies/sitework.json, and a new version label.
"""

import argparse
import json
import re
import sys
import uuid
from base64 import urlsafe_b64decode
from datetime import datetime, timezone

import httpx

from sitework.config import ROOT, Settings, get_settings

RULES = ROOT / "policies" / "sitework.json"
PREFIX = "sitework_"


class PolicyApi:
    """The two published routes this needs, called with the policy-authoring key only."""

    def __init__(self, settings: Settings):
        key = settings.secret("decionis_policy_api_key")
        self.base = settings.decionis_api_base.rstrip("/")
        self.http = httpx.Client(timeout=30, headers={"Authorization": f"Bearer {key}"})

    def current(self) -> tuple[dict, dict]:
        """The active bundle as hosted evaluation selects it (decoded from its signed issuance)."""
        res = self.http.get(f"{self.base}/v1/edge/policy-bundles/current", params={"ttl_seconds": 60})
        res.raise_for_status()
        body = res.json()
        claims = json.loads(urlsafe_b64decode(body["signed_bundle"].split(".")[1] + "=="))
        return body, claims["bundle"]["payload"]

    def submit(self, bundle: dict) -> httpx.Response:
        return self.http.post(f"{self.base}/v1/protocol/policies/bundles", json=bundle,
                              headers={"Idempotency-Key": f"sitework-policy-{bundle['bundle_id']}"})


class BundlePlan:
    """Builds the next bundle: everything else unchanged, SiteWork rules swapped in."""

    def __init__(self, active: dict, sitework_rules: list[dict]):
        self.active = active
        self.sitework_rules = sitework_rules

    @property
    def kept(self) -> list[dict]:
        return [r for r in self.active["rules"] if not r["rule_id"].startswith(PREFIX)]

    def version(self) -> str:
        base = self.active["version"]
        match = re.search(r"\+sitework-(\d+)$", base)
        n = int(match.group(1)) + 1 if match else 1
        return f"{re.sub(r'[+]sitework-[0-9]+$', '', base)}+sitework-{n}"

    def build(self, now: datetime | None = None) -> dict:
        now = now or datetime.now(timezone.utc)
        return {
            "protocol_version": self.active.get("protocol_version", "1.0"),
            "bundle_id": str(uuid.uuid4()),
            "org_id": self.active["org_id"],
            "version": self.version(),
            "effective_from": now.strftime("%Y-%m-%dT%H:%M:%S.") + f"{now.microsecond // 1000:03d}Z",
            "rules": self.kept + self.sitework_rules,
            "metadata": {"author": "SiteWork policy authoring", "source": "policies/sitework.json",
                         "change_ticket": f"sitework-policy-{self.version()}"},
        }

    def summary(self, bundle: dict) -> list[str]:
        replaced = [r["rule_id"] for r in self.active["rules"] if r["rule_id"].startswith(PREFIX)]
        lines = [f"active:  {self.active['version']} ({len(self.active['rules'])} rules)",
                 f"next:    {bundle['version']} ({len(bundle['rules'])} rules)",
                 f"kept verbatim: {len(self.kept)} non-SiteWork rules",
                 f"replaced: {replaced or 'none'}"]
        lines += [f"  + [{r['priority']}] {r['then']['action']:<12} {r['rule_id']}" for r in self.sitework_rules]
        return lines


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("cmd", nargs="?", default="plan", choices=["plan", "submit", "current"])
    p.add_argument("--yes", action="store_true", help="required for submit")
    args = p.parse_args(argv)
    api = PolicyApi(get_settings())
    issuance, active = api.current()
    if args.cmd == "current":
        print(f"{issuance['policy_version']}  bundle {issuance['bundle_id']}  ({len(active['rules'])} rules)")
        return 0
    plan = BundlePlan(active, json.loads(RULES.read_text())["rules"])
    bundle = plan.build()
    print("\n".join(plan.summary(bundle)))
    if args.cmd == "plan":
        return 0
    if not args.yes:
        print("submit needs --yes")
        return 2
    res = api.submit(bundle)
    print(f"POST /v1/protocol/policies/bundles -> {res.status_code}")
    print(json.dumps(res.json() if res.headers.get("content-type", "").startswith("application/json") else res.text,
                     indent=2)[:2000])
    return 0 if res.status_code < 300 else 1


if __name__ == "__main__":
    sys.exit(main())
