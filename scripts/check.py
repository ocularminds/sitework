"""Run dependency checks; never print credential values.

--gate adds one incomplete Decionis authority call in DECIONIS_GATE_MODE.
It may be recorded in the ledger, but never claims an execution grant.
"""

import argparse

from sitework.config import Settings
from sitework.health import DecionisCheck, Doctor, GateCheck


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--decionis-only", action="store_true")
    parser.add_argument("--gate", action="store_true", help="also check the configured mode with an incomplete intent")
    parser.add_argument("--gate-mode", choices=["SHADOW", "PARALLEL", "ENFORCEMENT"],
                        help="explicit mode override for --gate and its readiness checks")
    args = parser.parse_args()
    settings = Settings()
    if args.gate_mode:
        if not args.gate:
            parser.error("--gate-mode requires --gate")
        settings = settings.model_copy(update={"decionis_gate_mode": args.gate_mode})
    doctor = Doctor([DecionisCheck(settings)]) if args.decionis_only else Doctor.default(settings)
    if args.gate:
        doctor.checks.append(GateCheck(settings))
    results = doctor.run()
    for result in results:
        print(f"{'PASS' if result.ok else 'BLOCKED'} {result.name}")
        for detail in result.detail:
            print(f"  {detail}")
        for blocker in result.blockers:
            print(f"  BLOCKER: {blocker}")
    return 0 if all(result.ok for result in results) else 1


if __name__ == "__main__":
    raise SystemExit(main())
