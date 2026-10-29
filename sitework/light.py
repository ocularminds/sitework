"""Stack light at the work face. Green only when Decionis returned ALLOW with should_execute.

A named person's release of an escalated hold shows blue: released by a human, not by the gate.
"""

from typing import Literal

from pydantic import BaseModel

from sitework.gate.authority import GateFailure
from sitework.schema import Verdict

Color = Literal["green", "amber", "red", "blue", "off"]


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
        if result.decision == "ALLOW":
            return cls(color="red", label="NOT RELEASED")  # no execute, or the grant was not claimed and finalized
        return cls(color="red", label=result.decision)  # BLOCK or ERROR

    @classmethod
    def resolved(cls, approver: str, release: bool) -> "LightState":
        if release:
            return cls(color="blue", label=f"RELEASED BY {approver.upper()}")
        return cls(color="red", label=f"HELD BY {approver.upper()}")
