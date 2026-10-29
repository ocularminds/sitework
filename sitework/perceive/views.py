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

    def segments(self) -> list[Segment]:
        """Line segments the dashboard draws over the frame."""
        raise NotImplementedError

    def within(self, width: int, height: int) -> bool:
        return all(0 <= x <= width and 0 <= y <= height for x, y in self.points())

    def scaled(self, sx: float, sy: float):
        """The same view with every [x, y] point multiplied by (sx, sy)."""
        def walk(node):
            if isinstance(node, list) and len(node) == 2 and all(isinstance(v, (int, float)) for v in node):
                return [node[0] * sx, node[1] * sy]
            if isinstance(node, list):
                return [walk(n) for n in node]
            if isinstance(node, dict):
                return {k: walk(v) for k, v in node.items()}
            return node
        data = self.model_dump()
        return type(self).model_validate({k: (v if k == "confidence" else walk(v)) for k, v in data.items()})


class Board(BaseModel):
    model_config = ConfigDict(extra="forbid")
    edges: Annotated[list[Segment], Field(min_length=2, max_length=2)]


class DeckingView(View):
    """Each visible deck board as its two long edges, each edge as two endpoints in pixels."""

    boards: Annotated[list[Board], Field(min_length=2)]

    def points(self) -> list[Point]:
        return [p for b in self.boards for edge in b.edges for p in edge]

    def segments(self) -> list[Segment]:
        return [edge for b in self.boards for edge in b.edges]

    PROMPT: ClassVar[str] = (
        "You locate deck boards for a measurement program. The image is {width}x{height} pixels, "
        "origin top-left. For every deck board that is fully visible, return its two long edges. "
        "Give each edge as its two endpoints [x, y] in pixels, placed where the edge meets the "
        "board's ends. Ignore the black-and-white square marker. Reply with JSON only, exactly: "
        '{{"boards": [{{"edges": [[[x, y], [x, y]], [[x, y], [x, y]]]}}], "confidence": c}} '
        "where c is 0 to 1: how sure you are that every edge is placed on the true board edge."
    )


class Wall(BaseModel):
    model_config = ConfigDict(extra="forbid")
    top: Point  # where the wall meets the ground surface
    toe: Point  # where the wall meets the trench floor


class TrenchView(View):
    """A trench seen in cross-section: each wall as its top and toe point in pixels."""

    walls: Annotated[list[Wall], Field(min_length=1, max_length=2)]

    def points(self) -> list[Point]:
        return [p for w in self.walls for p in (w.top, w.toe)]

    def segments(self) -> list[Segment]:
        return [[w.top, w.toe] for w in self.walls]

    PROMPT: ClassVar[str] = (
        "You locate trench walls for a measurement program. The image is {width}x{height} pixels, "
        "origin top-left, and shows a trench in cross-section from the side. For each trench wall "
        "you can see (one or two), return the point where the wall meets the ground surface (top) "
        "and the point where it meets the trench floor (toe), in pixels. Ignore the black-and-white "
        'square marker. Reply with JSON only, exactly: {{"walls": [{{"top": [x, y], "toe": [x, y]}}], '
        '"confidence": c}} where c is 0 to 1: how sure you are that each point is on the true wall.'
    )


class PlumbingView(View):
    """A push-fit joint seen from above: the pipe's and the fitting's centre lines, two points each."""

    pipe: Segment
    fitting: Segment

    def points(self) -> list[Point]:
        return [*self.pipe, *self.fitting]

    def segments(self) -> list[Segment]:
        return [self.pipe, self.fitting]

    PROMPT: ClassVar[str] = (
        "You locate a plumbing joint for a measurement program. The image is {width}x{height} pixels, "
        "origin top-left, and shows a pipe pushed into a fitting. Return the centre line of the pipe as two "
        "points along it, and the centre line of the fitting body as two points along it, in pixels. "
        "Ignore the black-and-white square marker. Reply with JSON only, exactly: "
        '{{"pipe": [[x, y], [x, y]], "fitting": [[x, y], [x, y]], "confidence": c}} '
        "where c is 0 to 1: how sure you are that both lines follow the true centre lines."
    )
