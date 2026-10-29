import pytest

from sitework.config import Settings
from sitework.ground.web import WebClient, allowed


class FakeTavily:
    def __init__(self, results):
        self.results = results
        self.calls = []

    def search(self, **kwargs):
        self.calls.append(kwargs)
        return {"results": self.results}


@pytest.mark.parametrize("domain,ok", [
    ("osha.gov", True), ("www.osha.gov", True), ("evilosha.gov", False), ("osha.gov.evil.com", False),
])
def test_allowlist_accepts_domain_and_subdomains_only(domain, ok):
    assert allowed(domain, ["osha.gov"]) is ok


def test_search_restricts_domains_and_drops_off_list_results():
    fake = FakeTavily([
        {"url": "https://www.osha.gov/laws-regs/1926.652", "title": "1926.652", "content": "x", "score": 0.9},
        {"url": "https://blog.example.com/trenches", "title": "blog", "content": "y", "score": 0.8},
    ])
    results = WebClient(Settings(_env_file=None), client=fake).search("q", ["osha.gov"])
    assert [r.domain for r in results] == ["www.osha.gov"]
    assert fake.calls[0]["include_domains"] == ["osha.gov"]
    assert fake.calls[0]["include_domains_mode"] == "restrict"
