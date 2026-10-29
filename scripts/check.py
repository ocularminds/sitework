"""Run P0 dependency checks; never print credential values."""

import argparse

from sitework.config import Settings
from sitework.health import DecionisCheck, Doctor


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--decionis-only", action="store_true")
    args = parser.parse_args()
    settings = Settings()
    doctor = Doctor([DecionisCheck(settings)]) if args.decionis_only else Doctor.default(settings)
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
