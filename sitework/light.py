"""Stack light at the work face. Green only when Decionis returned ALLOW with should_execute."""

from typing import Literal

from pydantic import BaseModel

from sitework.gate.authority import GateFailure
from sitework.schema import Verdict

Color = Literal["green", "amber", "red", "off"]


class LightState(BaseModel):
    color: Color
    label: str

    @classmethod
    def idle(cls) -> "LightState":
        return cls(color="off", label="NO INSPECTION")

    @classmethod
    def of(cls, result: Verdict | GateFailure | None) -> "LightState":
        if result is None:
            return cls.idle()
        if isinstance(result, GateFailure):
            return cls(color="red", label="NO DECISION")  # the hold stays closed
        if result.green:
            return cls(color="green", label="ALLOW")
        if result.decision in ("ESCALATE", "REVIEW_REQUIRED"):
            return cls(color="amber", label=result.decision)
        return cls(color="red", label=result.decision)  # BLOCK, ERROR, or ALLOW without execute
