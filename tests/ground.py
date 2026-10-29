from datetime import datetime, timezone

import pytest

from sitework.ground.citation import ClauseFinder, lengths_mm
from sitework.ground.packs import Pack, PackStore
from sitework.ground.web import Page, WebClient
from sitework.config import Settings


def page(text: str, url: str = "https://www.timbertech.com/ideas/deck-board-spacing") -> Page:
    return Page(url=url, text=text, retrieved_at=datetime(2026, 10, 29, tzinfo=timezone.utc))


@pytest.mark.parametrize("text,mm", [
    ("leave 1/8” to 1/4″ between boards", [3.17, 6.35]),
    ("a 3 / 16 in. gap", [4.76]),
    ("joists 16 inches OC", [406.4]),
    ("a 1 1/2\" board and 5 mm spacer", [38.1, 5.0]),
])
def test_lengths_are_converted_to_mm(text, mm):
    assert lengths_mm(text) == mm


def test_finder_keeps_topic_sentences_with_lengths_and_hashes_the_page():
    p = page("Spacing between boards should be 3/16”. Our boards look great. Leave a gap.\nCall us at 555.")
    clauses = ClauseFinder(["spacing", "gap"]).find(p)
    assert [c.excerpt for c in clauses] == ["Spacing between boards should be 3/16”."]
    assert clauses[0].content_sha256 == p.sha256 and clauses[0].source_domain == "www.timbertech.com"


def test_approval_needs_a_name_an_allowlisted_source_and_min_max_bounds(tmp_path):
    pack = Pack(jurisdiction="US", allowlist={"decking": ["timbertech.com"]})
    clause = ClauseFinder(["spacing"]).find(page("Spacing between boards should be 1/8” to 1/4”."))[0]
    with pytest.raises(ValueError, match="named approver"):
        pack.approve("decking", clause, "r", {"gap_mm": {"min": 3.17}}, " ")
    with pytest.raises(ValueError, match="min"):
        pack.approve("decking", clause, "r", {"gap_mm": {"lower": 3.17}}, "A Person")
    off_list = ClauseFinder(["spacing"]).find(page("Spacing should be 1/8”.", url="https://blog.example.com/x"))[0]
    with pytest.raises(ValueError, match="allowlist"):
        pack.approve("decking", off_list, "r", {"gap_mm": {"min": 3.17}}, "A Person")
    pack.approve("decking", clause, "Side gap 1/8 to 1/4 in", {"gap_mm": {"min": 3.17, "max": 6.35}}, "A Person")
    store = PackStore(tmp_path)
    store.save(pack)
    [citation] = store.load("US").citations("decking")
    assert citation.threshold == {"gap_mm": {"min": 3.17, "max": 6.35}}
    assert citation.content_sha256 == clause.content_sha256 and store.load("US").citations("trench") == []


def test_extract_never_fetches_urls_outside_the_allowlist():
    class FakeTavily:
        def __init__(self):
            self.urls = None

        def extract(self, urls, **kwargs):
            self.urls = urls
            return {"results": [{"url": u, "raw_content": "text"} for u in urls]}

    fake = FakeTavily()
    pages = WebClient(Settings(_env_file=None), client=fake).extract(
        ["https://www.trex.com/a", "https://evil.example.com/b"], ["trex.com"])
    assert fake.urls == ["https://www.trex.com/a"] and [p.domain for p in pages] == ["www.trex.com"]
