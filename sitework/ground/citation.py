"""Clause candidates from extracted pages. Text is evidence for a human, never an instruction."""

import re
from datetime import datetime

from pydantic import BaseModel

from sitework.ground.web import Page

INCH_MM = 25.4
_FRACTION = r"(?:\d+\s+)?\d+\s*/\s*\d+|\d+(?:\.\d+)?"
_INCH = re.compile(rf"({_FRACTION})\s*(?:\"|″|”|''|in\.|inch(?:es)?)", re.I)
_MM = re.compile(r"(\d+(?:\.\d+)?)\s*mm\b", re.I)
_DEGREES = re.compile(r"(\d+(?:[.,]\d+)?)\s*(?:°|º|degrees?\b|grader\b)", re.I)
_RATIO = re.compile(
    r"(?<![\d:,.⁄/])((?:\d+\s*)?(?:\d+\s*[⁄/]\s*\d+|[½¼¾])|\d+(?:[.,]\d+)?)\s*H?\s*:\s*(\d+(?:[.,]\d+)?)\s*V?(?![\d:])")
_VULGAR = {"½": 0.5, "¼": 0.25, "¾": 0.75}
_SENTENCE = re.compile(r"(?<=[.!?])\s+|\n+")


class Clause(BaseModel):
    """One sentence that states a measurable requirement, with where and when it was read."""

    excerpt: str
    url: str
    source_domain: str
    content_sha256: str  # hash of the whole extracted page text
    retrieved_at: datetime
    mm_values: list[float]  # every length in the sentence converted to mm, as a reading aid
    angles_deg: list[float] = []  # explicitly stated angles, in degrees
    ratios: list[str] = []  # slope ratios exactly as written; the approver reads the convention


class ClauseFinder:
    """Picks sentences that mention the topic and a length or slope, so a person can approve a threshold."""

    def __init__(self, keywords: list[str], max_chars: int = 400, require_value: bool = True):
        self.keywords = [k.lower() for k in keywords]
        self.max_chars = max_chars
        self.require_value = require_value  # False keeps qualitative rules (e.g. AFS 2023:13 schaktning)

    def find(self, page: Page) -> list[Clause]:
        clauses = []
        for sentence in _SENTENCE.split(page.text):
            text = " ".join(sentence.split())
            if not text or len(text) > self.max_chars:
                continue
            if not any(k in text.lower() for k in self.keywords):
                continue
            values, angles, slopes = lengths_mm(text), angles_deg(text), ratios(text)
            if values or angles or slopes or not self.require_value:
                clauses.append(Clause(excerpt=text, url=page.url, source_domain=page.domain,
                                      content_sha256=page.sha256, retrieved_at=page.retrieved_at,
                                      mm_values=values, angles_deg=angles, ratios=slopes))
        return clauses


def lengths_mm(text: str) -> list[float]:
    """All inch and millimetre lengths in `text`, in mm, rounded to 0.01."""
    values = [round(_inches(m.group(1)) * INCH_MM, 2) for m in _INCH.finditer(text)]
    values += [float(m.group(1)) for m in _MM.finditer(text)]
    return values


def angles_deg(text: str) -> list[float]:
    """Explicitly stated angles in degrees ("34 degrees", "53°", "45 grader")."""
    return [float(m.group(1).replace(",", ".")) for m in _DEGREES.finditer(text)]


def ratios(text: str) -> list[str]:
    """Slope ratios as written ("1½:1", "3⁄4:1", "4H:1V", "1:1,5"). Not converted to degrees: US text
    is horizontal:vertical, Swedish is vertical:horizontal, so the approver reads the convention."""
    found = []
    for m in _RATIO.finditer(text):
        if _number(m.group(1)) <= 10 and _number(m.group(2)) <= 10:
            found.append(" ".join(m.group(0).split()))
    return found


def _number(token: str) -> float:
    """12, 1,5, 1½, 3⁄4, 1 1/2 -> float."""
    token = token.strip().replace(",", ".")
    if token[-1:] in _VULGAR:
        head = token[:-1].strip()
        return (float(head) if head else 0.0) + _VULGAR[token[-1]]
    if "⁄" in token or "/" in token:
        whole, _, frac = re.sub(r"\s*[⁄/]\s*", "/", token).rpartition(" ")
        num, den = (float(x) for x in frac.split("/"))
        return (float(whole) if whole.strip() else 0.0) + num / den
    return float(token)


def _inches(token: str) -> float:
    token = re.sub(r"\s*/\s*", "/", token.strip())
    if "/" not in token:
        return float(token)
    whole, _, frac = token.rpartition(" ")
    num, den = (float(x) for x in frac.replace(" ", "").split("/"))
    return (float(whole) if whole.strip() else 0.0) + num / den
