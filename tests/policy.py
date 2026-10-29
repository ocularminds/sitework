import importlib.util
import json
from datetime import datetime, timezone
from pathlib import Path

from sitework.config import Settings
from sitework.gate.authority import MockGate
from sitework.gate.evidence import Facts
from gate import bundle

ROOT = Path(__file__).resolve().parent.parent
_spec = importlib.util.spec_from_file_location("policy_script", ROOT / "scripts" / "policy.py")
policy = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(policy)

STARTER = {
    "protocol_version": "1.0", "org_id": "org-1", "version": "decionis-starter-v2",
    "rules": [
        {"rule_id": "starter_allow_routine", "priority": 0, "then": {"action": "AUTO_APPROVE"},
         "when": {"all": [{"field": "decision_type", "operator": "EXISTS"}]}},
        {"rule_id": "starter_block_extreme_risk", "priority": 280, "then": {"action": "AUTO_REJECT"},
         "when": {"all": [{"field": "risk_score", "operator": "GTE", "value": 0.9}]}},
    ],
}


def sitework_rules():
    return json.loads((ROOT / "policies" / "sitework.json").read_text())["rules"]


def test_plan_keeps_every_other_rule_verbatim_and_adds_sitework():
    plan = policy.BundlePlan(STARTER, sitework_rules())
    b = plan.build(datetime(2026, 10, 29, 3, 5, 22, 85000, tzinfo=timezone.utc))
    assert b["rules"][:2] == STARTER["rules"]
    assert b["version"] == "decionis-starter-v2+sitework-1" and b["org_id"] == "org-1"
    assert b["effective_from"] == "2026-10-29T03:05:22.085Z"
    assert {r["rule_id"] for r in b["rules"][2:]} == {r["rule_id"] for r in sitework_rules()}


def test_reloading_replaces_only_sitework_rules_and_bumps_the_version():
    first = policy.BundlePlan(STARTER, sitework_rules()).build()
    again = policy.BundlePlan(first, sitework_rules()).build()
    assert again["version"] == "decionis-starter-v2+sitework-2"
    assert len(again["rules"]) == len(first["rules"])
    assert [r for r in again["rules"] if not r["rule_id"].startswith("sitework_")] == STARTER["rules"]


def test_sitework_rules_outrank_starter_rules_and_cover_every_condition():
    rules = sitework_rules()
    assert min(r["priority"] for r in rules) > 300
    allow = [r for r in rules if r["then"]["action"] == "AUTO_APPROVE"]
    conditions = {c["value"] for r in allow for c in r["when"]["all"] if c["field"] == "context.sitework_condition"}
    assert conditions == {"clean", "outdoor", "rain", "mud", "dusk_glare"}
    for r in allow:
        fields = {c["field"]: c for c in r["when"]["all"]}
        assert fields["context.sitework_error_count"] == {"field": "context.sitework_error_count", "operator": "EQ", "value": 0}
        assert "policy" not in fields["decision_type"]["value"]
    catch_all = next(r for r in rules if r["rule_id"] == "sitework_escalate_otherwise")
    assert catch_all["then"]["action"] == "ESCALATE" and "policy" in catch_all["when"]["all"][0]["value"]


def test_every_field_a_rule_reads_is_sent_in_the_intent_context():
    body = MockGate(Settings(_env_file=None, decionis_org_id="00000000-0000-4000-8000-000000000002")).propose(
        bundle()).request
    read = {c["field"].removeprefix("context.") for r in sitework_rules() for c in r["when"]["all"]
            if c["field"].startswith("context.")}
    assert read <= set(body["context"])
    assert body["context"]["sitework_checks_outside"] == Facts(bundle()).summary()["checks_outside"] == 1
