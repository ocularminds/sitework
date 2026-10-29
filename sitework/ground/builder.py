"""Builds a jurisdiction pack from its allowlisted seeds with Tavily map + crawl, caching every page."""

import json
from pathlib import Path

from pydantic import BaseModel

from sitework.ground.citation import Clause, ClauseFinder
from sitework.ground.packs import Pack, Source
from sitework.ground.web import Page, WebClient


class PageCache:
    """Extracted page text on disk (data/packs/pages/<jurisdiction>/<scene>/<sha256>.json, git-ignored)."""

    def __init__(self, directory: Path):
        self.directory = directory

    def put(self, scene: str, page: Page) -> Path:
        path = self.directory / scene / f"{page.sha256}.json"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(page.model_dump_json(indent=1))
        return path

    def pages(self, scene: str) -> list[Page]:
        folder = self.directory / scene
        return [Page.model_validate_json(p.read_text()) for p in sorted(folder.glob("*.json"))] if folder.exists() else []


class BuildReport(BaseModel):
    scene: str
    seeds: int
    mapped: int
    pages: int
    clauses: list[Clause]


class PackBuilder:
    """Map finds relevant URLs under each seed, crawl reads the seed's neighbourhood, and mapped
    pages the crawl missed are extracted. PDF seeds are extracted directly. Nothing off-allowlist is read."""

    def __init__(self, web: WebClient, pack: Pack, cache: PageCache, map_limit: int = 30,
                 crawl_limit: int = 10, extra_limit: int = 5):
        self.web = web
        self.pack = pack
        self.cache = cache
        self.map_limit, self.crawl_limit, self.extra_limit = map_limit, crawl_limit, extra_limit

    def build(self, scene: str, topic: str, keywords: list[str], qualitative: bool = False,
              cached: bool = False) -> BuildReport:
        finder = ClauseFinder(keywords, require_value=not qualitative)
        if cached:
            pages = self.cache.pages(scene)
            return BuildReport(scene=scene, seeds=0, mapped=0, pages=len(pages),
                               clauses=[c for page in pages for c in finder.find(page)])
        domains = self.pack.allowlist.get(scene, [])
        seeds = self.pack.seeds.get(scene, [])
        if not domains or not seeds:
            raise ValueError(f"{self.pack.jurisdiction} pack has no allowlist or seeds for {scene}")
        mapped, read = 0, 0
        for seed in seeds:
            pages, found = self._read(seed, domains, topic)
            mapped += found
            for page, via in pages:
                self.cache.put(scene, page)
                self.pack.record(Source(scene=scene, url=page.url, content_sha256=page.sha256,
                                        retrieved_at=page.retrieved_at, via=via))
                read += 1
        clauses = [c for page in self.cache.pages(scene) for c in finder.find(page)]
        return BuildReport(scene=scene, seeds=len(seeds), mapped=mapped, pages=read, clauses=clauses)

    def _read(self, seed: str, domains: list[str], topic: str) -> tuple[list[tuple[Page, str]], int]:
        """Pages read from one seed, and how many URLs map found."""
        if seed.lower().split("?")[0].endswith(".pdf"):
            return [(p, "extract") for p in self.web.extract([seed], domains)], 0
        urls = self.web.map(seed, domains, topic, limit=self.map_limit)
        crawled = self.web.crawl(seed, domains, topic, limit=self.crawl_limit)
        seen = {p.url for p in crawled}
        extra = [u for u in urls if u not in seen][: self.extra_limit]
        pages = [(p, "crawl") for p in crawled] + [(p, "map+extract") for p in self.web.extract(extra, domains)]
        return pages, len(urls)


def save_candidates(path: Path, clauses: list[Clause]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps([c.model_dump(mode="json") for c in clauses], indent=2) + "\n")
