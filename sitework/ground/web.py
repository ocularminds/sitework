"""Tavily wrapper. Retrieved text is data: callers keep only structured fields."""

import hashlib
from datetime import datetime, timezone
from urllib.parse import urlparse

from pydantic import BaseModel
from tavily import TavilyClient

from sitework.config import Settings


class WebResult(BaseModel):
    url: str
    title: str = ""
    content: str = ""
    score: float = 0.0

    @property
    def domain(self) -> str:
        return urlparse(self.url).netloc.lower()


class Page(BaseModel):
    """Extracted page text as read at `retrieved_at`; its hash pins what was read."""

    url: str
    text: str
    retrieved_at: datetime

    @property
    def domain(self) -> str:
        return urlparse(self.url).netloc.lower()

    @property
    def sha256(self) -> str:
        return hashlib.sha256(self.text.encode()).hexdigest()


class WebClient:
    """Allowlisted Tavily access. Every call names the domains it may read."""

    def __init__(self, settings: Settings, client: TavilyClient | None = None):
        self._client = client or TavilyClient(api_key=settings.secret("tavily_api_key"))

    def search(self, query: str, domains: list[str], max_results: int = 5) -> list[WebResult]:
        raw = self._client.search(
            query=query,
            include_domains=domains,
            include_domains_mode="restrict",
            max_results=max_results,
        )
        results = [
            WebResult(**{k: r[k] for k in WebResult.model_fields if r.get(k) is not None})
            for r in raw.get("results", [])
        ]
        return [r for r in results if allowed(r.domain, domains)]

    def extract(self, urls: list[str], domains: list[str]) -> list[Page]:
        """Full text of allowlisted pages. URLs outside the allowlist are never fetched."""
        keep = [u for u in urls if allowed(urlparse(u).netloc.lower(), domains)]
        if not keep:
            return []
        raw = self._client.extract(urls=keep, format="text")
        retrieved = datetime.now(timezone.utc)
        return [Page(url=r["url"], text=r.get("raw_content") or "", retrieved_at=retrieved)
                for r in raw.get("results", []) if r.get("raw_content")]


def allowed(domain: str, allowlist: list[str]) -> bool:
    """True if `domain` is an allowlisted domain or a subdomain of one."""
    return any(domain == d or domain.endswith(f".{d}") for d in allowlist)
