"""Run dependency checks; never print credential values.

--gate adds one SHADOW-mode Decionis authority call (it is recorded in the Decionis ledger).
"""

import argparse

from sitework.config import Settings
from sitework.health import DecionisCheck, Doctor, GateCheck


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--decionis-only", action="store_true")
    parser.add_argument("--gate", action="store_true", help="also make one SHADOW gate call")
    args = parser.parse_args()
    settings = Settings()
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
