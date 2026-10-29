"""Strict schemas for what a vision model may return: coordinates and a confidence, nothing else."""

from typing import Annotated, ClassVar

from pydantic import BaseModel, ConfigDict, Field

Point = Annotated[list[float], Field(min_length=2, max_length=2)]
Segment = Annotated[list[Point], Field(min_length=2, max_length=2)]


class View(BaseModel):
    """Base for model replies. Unknown keys are rejected so free text cannot slip through."""

    model_config = ConfigDict(extra="forbid")
    PROMPT: ClassVar[str] = ""
    confidence: float = Field(ge=0.0, le=1.0)

    def points(self) -> list[Point]:
        raise NotImplementedError

    def within(self, width: int, height: int) -> bool:
        return all(0 <= x <= width and 0 <= y <= height for x, y in self.points())


class Board(BaseModel):
    model_config = ConfigDict(extra="forbid")
    edges: Annotated[list[Segment], Field(min_length=2, max_length=2)]


class DeckingView(View):
    """Each visible deck board as its two long edges, each edge as two endpoints in pixels."""

    boards: Annotated[list[Board], Field(min_length=2)]

    def points(self) -> list[Point]:
        return [p for b in self.boards for edge in b.edges for p in edge]

    PROMPT: ClassVar[str] = (
        "You locate deck boards for a measurement program. The image is {width}x{height} pixels, "
        "origin top-left. For every deck board that is fully visible, return its two long edges. "
        "Give each edge as its two endpoints [x, y] in pixels, placed where the edge meets the "
        "board's ends. Ignore the black-and-white square marker. Reply with JSON only, exactly: "
        '{{"boards": [{{"edges": [[[x, y], [x, y]], [[x, y], [x, y]]]}}], "confidence": c}} '
        "where c is 0 to 1: how sure you are that every edge is placed on the true board edge."
    )
