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


@pytest.mark.parametrize("text,deg,ratio", [
    ("Type C soil 1½:1 (34 degrees)", [34.0], ["1½:1"]),
    ("maximum allowable slope of 3⁄4:1.", [], ["3⁄4:1"]),
    ("dip on a slope of four horizontal to one vertical (4H:1V)", [], ["4H:1V"]),
    ("släntlutning 1:1,5 vid schaktning", [], ["1:1,5"]),
    ("meeting at 10:30, ratio 12:1", [], []),
])
def test_angles_and_slope_ratios_are_kept_as_written(text, deg, ratio):
    from sitework.ground.citation import angles_deg, ratios
    assert angles_deg(text) == deg and ratios(text) == ratio


def test_qualitative_mode_keeps_rule_sentences_without_numbers():
    p = page("Slänt eller vägg kan utföras med lutning eller i avsatser, med stöttning eller spontning.",
             url="https://www.av.se/x")
    assert ClauseFinder(["slänt"]).find(p) == []
    assert len(ClauseFinder(["slänt"], require_value=False).find(p)) == 1


def test_builder_maps_crawls_extracts_and_records_sources(tmp_path):
    from sitework.ground.builder import PackBuilder, PageCache

    class FakeWeb:
        def map(self, seed, domains, topic, limit=30):
            return ["https://www.osha.gov/a", "https://www.osha.gov/b"]

        def crawl(self, seed, domains, topic, limit=10):
            return [page("Maximum allowable slope of 1½:1.", url="https://www.osha.gov/a")]

        def extract(self, urls, domains):
            return [page(f"Slope of 1:1 at {u}.", url=u) for u in urls]

    pack = Pack(jurisdiction="US", allowlist={"trench": ["osha.gov"]},
                seeds={"trench": ["https://www.osha.gov/start", "https://www.osha.gov/table.pdf"]})
    report = PackBuilder(FakeWeb(), pack, PageCache(tmp_path)).build("trench", "slopes", ["slope"])
    assert report.mapped == 2 and report.pages == 3
    assert sorted((s.url, s.via) for s in pack.sources) == [
        ("https://www.osha.gov/a", "crawl"), ("https://www.osha.gov/b", "map+extract"),
        ("https://www.osha.gov/table.pdf", "extract")]
    assert len(report.clauses) == 3
    cached = PackBuilder(None, pack, PageCache(tmp_path)).build("trench", "slopes", ["slope"], cached=True)
    assert cached.pages == 3 and len(cached.clauses) == 3
