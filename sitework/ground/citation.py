"""Clause candidates from extracted pages. Text is evidence for a human, never an instruction."""

import re
from datetime import datetime

from pydantic import BaseModel

from sitework.ground.web import Page

INCH_MM = 25.4
_FRACTION = r"(?:\d+\s+)?\d+\s*/\s*\d+|\d+(?:\.\d+)?"
_INCH = re.compile(rf"({_FRACTION})\s*(?:\"|″|”|''|in\.|inch(?:es)?)", re.I)
_MM = re.compile(r"(\d+(?:\.\d+)?)\s*mm\b", re.I)
_SENTENCE = re.compile(r"(?<=[.!?])\s+|\n+")


class Clause(BaseModel):
    """One sentence that states a measurable requirement, with where and when it was read."""

    excerpt: str
    url: str
    source_domain: str
    content_sha256: str  # hash of the whole extracted page text
    retrieved_at: datetime
    mm_values: list[float]  # every length in the sentence converted to mm, as a reading aid


class ClauseFinder:
    """Picks sentences that mention the topic and a length, so a person can approve a threshold."""

    def __init__(self, keywords: list[str], max_chars: int = 400):
        self.keywords = [k.lower() for k in keywords]
        self.max_chars = max_chars

    def find(self, page: Page) -> list[Clause]:
        clauses = []
        for sentence in _SENTENCE.split(page.text):
            text = " ".join(sentence.split())
            if not text or len(text) > self.max_chars:
                continue
            if not any(k in text.lower() for k in self.keywords):
                continue
            values = lengths_mm(text)
            if values:
                clauses.append(Clause(excerpt=text, url=page.url, source_domain=page.domain,
                                      content_sha256=page.sha256, retrieved_at=page.retrieved_at,
                                      mm_values=values))
        return clauses


def lengths_mm(text: str) -> list[float]:
    """All inch and millimetre lengths in `text`, in mm, rounded to 0.01."""
    values = [round(_inches(m.group(1)) * INCH_MM, 2) for m in _INCH.finditer(text)]
    values += [float(m.group(1)) for m in _MM.finditer(text)]
    return values


def _inches(token: str) -> float:
    token = re.sub(r"\s*/\s*", "/", token.strip())
    if "/" not in token:
        return float(token)
    whole, _, frac = token.rpartition(" ")
    num, den = (float(x) for x in frac.replace(" ", "").split("/"))
    return (float(whole) if whole.strip() else 0.0) + num / den
