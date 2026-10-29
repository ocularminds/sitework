import json

import pytest

from sitework.config import Settings
from sitework.gate.authority import MockGate
from sitework.ground.packs import Pack
from sitework.ground.watch import SCHEMA, AmendmentWatch, PolicyUpdate, ProposalStore

PACK = Pack(jurisdiction="SE", authority="AFS 2023:13", allowlist={"trench": ["av.se"], "decking": ["svenskttra.se"]})
RESULT = {
    "status": "completed", "request_id": "r-1",
    "content": {"findings": [
        {"kind": "amendment", "scene": "trench", "title": "AFS 2025:6 – ändring i AFS 2023:13",
         "source_url": "https://www.av.se/x/afs2025-6.pdf", "effective_date": "2025-12-19"},
        {"kind": "recall", "scene": "decking", "title": "Blog post", "source_url": "https://blog.example.com/y"},
        {"kind": "rumour", "scene": "trench", "title": "bad kind", "source_url": "https://www.av.se/z"},
    ]},
    "sources": [{"url": "https://www.av.se/x/afs2025-6.pdf"}, {"url": "https://www.regelradet.se/r.pdf"}],
}


def test_schema_top_level_is_what_tavily_accepts():
    assert set(SCHEMA) == {"properties", "required"}


def test_findings_are_validated_and_checked_against_the_scene_allowlist():
    p = AmendmentWatch(None, PACK).proposal("r-1", "q", RESULT)
    assert [(f.kind, f.allowlisted) for f in p.findings] == [("amendment", True), ("recall", False)]
    assert p.cited == ["https://www.av.se/x/afs2025-6.pdf", "https://www.regelradet.se/r.pdf"]
    assert len(p.result_sha256) == 64


def test_content_may_arrive_as_a_json_string():
    p = AmendmentWatch(None, PACK).proposal("r-1", "q", {**RESULT, "content": json.dumps(RESULT["content"])})
    assert len(p.findings) == 2


def test_failed_research_is_not_a_proposal():
    with pytest.raises(ValueError, match="failed"):
        AmendmentWatch(None, PACK).proposal("r-1", "q", {"status": "failed"})


def test_policy_update_sends_structured_facts_only_and_needs_a_named_resolution(tmp_path):
    gate = MockGate(Settings(_env_file=None, decionis_org_id="00000000-0000-4000-8000-000000000002"))
    store = ProposalStore(tmp_path)
    updates = PolicyUpdate(gate, store)
    p = updates.propose(AmendmentWatch(None, PACK).proposal("r-1", "q", RESULT))
    request = p.exchange["request"]
    assert request["action"]["type"] == "policy.update" and request["action"]["resource"] == "sitework/policy/SE"
    assert request["context"]["sitework_findings"] == 2 and request["context"]["sitework_findings_allowlisted"] == 1
    assert "AFS 2025:6" not in json.dumps(request)  # titles reach the gate only as hashes
    assert request["context"]["sitework"]["cited_domains"] == ["www.av.se", "www.regelradet.se"]
    with pytest.raises(ValueError, match="named approver"):
        updates.resolve(p.id, True, " ")
    done = updates.resolve(p.id, True, "A Person", "rebuild SE trench pack")
    assert done.status == "approved" and store.get(p.id).resolved_by == "A Person"
    with pytest.raises(ValueError, match="already approved"):
        updates.resolve(p.id, False, "Someone Else")
