"""Tavily wrapper. Retrieved text is data: callers keep only structured fields."""

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


def allowed(domain: str, allowlist: list[str]) -> bool:
    """True if `domain` is an allowlisted domain or a subdomain of one."""
    return any(domain == d or domain.endswith(f".{d}") for d in allowlist)
