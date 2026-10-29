"""Run every clip in eval/labels.csv through the full pipeline and score it per condition.

  uv run python scripts/eval.py --run-label "run 1"
  uv run python scripts/eval.py --run-label "run 2: rain floor 0.90"   # after a policy change

Each run is appended to eval/results.json and eval/results.md is re-rendered from all runs.
Gate calls are real Decionis decisions (SHADOW by default, so no grant is ever claimed).
"""

import argparse
import json
import subprocess
import sys
from pathlib import Path

from sitework.capture import FileAudio, FileSource
from sitework.config import ROOT, Settings, get_settings
from sitework.dossier import DossierStore
from sitework.evaluate import Label, LabelFile, MarkdownReport, Results, Run, Scorer
from sitework.gate.authority import make_gate
from sitework.ground.packs import PackStore
from sitework.proof import ProofError, Proofs
from sitework.scenes import DeckingInspection, PlumbingInspection, TrenchInspection

EVAL = ROOT / "eval"


class Floors:
    """The per-condition confidence floors the loaded SiteWork policy file applies."""

    @staticmethod
    def read(path: Path) -> dict[str, float]:
        floors = {}
        for rule in json.loads(path.read_text())["rules"]:
            conds = {c["field"]: c for c in rule["when"].get("all", [])}
            cond, conf = conds.get("context.sitework_condition"), conds.get("context.sitework_min_confidence")
            if rule["then"]["action"] == "AUTO_APPROVE" and cond and conf:
                floors[cond["value"]] = conf["value"]
        return floors


class EvalRunner:
    def __init__(self, settings: Settings, verify: bool):
        self.settings = settings
        self.gate = make_gate(settings)
        self.store = DossierStore(settings.data_dir / "dossiers")
        packs = PackStore(settings.data_dir / "packs")
        self.scenes = {cls.scene: cls(settings, self.gate, self.store, packs)
                       for cls in (DeckingInspection, TrenchInspection, PlumbingInspection)}
        self.proofs = Proofs(settings) if verify and self.gate.mode == "live" else None
        self.scorer = Scorer()

    def run(self, labels: list[Label], run_label: str) -> Run:
        run = Run(label=run_label, commit=_commit(), gate_mode=self.settings.decionis_gate_mode,
                  decionis_mode=self.settings.decionis_mode, floors=Floors.read(ROOT / "policies" / "sitework.json"))
        for i, label in enumerate(labels, 1):
            path = ROOT / label.clip
            scene = self.scenes[label.scene]
            if label.scene == "plumbing":
                scene.audio = FileAudio(path)
            source = FileSource(path)
            try:
                result = scene.run(source, label.condition, label.jurisdiction)
            finally:
                source.close()
            scored = self.scorer.score(label, result)
            record = self.store.get(result.record_id)
            for role, model in (record.evidence.models if record else {}).items():
                run.models.setdefault(role, [])
                if model not in run.models[role]:
                    run.models[role].append(model)
            if result.verdict and result.verdict.policy_version and result.verdict.policy_version not in run.policy_versions:
                run.policy_versions.append(result.verdict.policy_version)
            if self.proofs and scored.dossier_id:
                try:
                    scored.verified = self.proofs.verify(scored.dossier_id).verified
                except ProofError as exc:
                    scored.verified = False
                    scored.errors.append(f"proof: {exc}")
            run.rows.append(scored)
            print(f"[{i}/{len(labels)}] {label.clip}: expected {label.expected}, got {scored.decision}"
                  f"{' FALSE ALLOW' if scored.false_allow else ''}")
        return run


def _commit() -> str:
    out = subprocess.run(["git", "rev-parse", "--short", "HEAD"], cwd=ROOT, capture_output=True, text=True)
    return out.stdout.strip()


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--labels", type=Path, default=EVAL / "labels.csv")
    p.add_argument("--run-label", required=True, help='e.g. "run 1" or "run 2: rain floor 0.90"')
    p.add_argument("--gate-mode", default="SHADOW", choices=["SHADOW", "PARALLEL", "ENFORCEMENT"])
    p.add_argument("--no-verify", action="store_true", help="skip offline dossier verification")
    p.add_argument("--output", type=Path, default=EVAL)
    args = p.parse_args(argv)
    settings = get_settings().model_copy(update={"decionis_gate_mode": args.gate_mode})
    if settings.decionis_mode == "mock" and args.output.resolve() == EVAL.resolve():
        print("refusing: DECIONIS_MODE=mock results never go into eval/ (pass --output for a test directory)")
        return 2
    labels = LabelFile(args.labels).read()
    if not labels:
        print(f"{args.labels} has no rows yet; record clips and label them first (see README, Evaluation)")
        return 2
    missing = [lab.clip for lab in labels if not (ROOT / lab.clip).exists()]
    if missing:
        print("missing clips, nothing was run:\n  " + "\n  ".join(missing))
        return 2
    run = EvalRunner(settings, verify=not args.no_verify).run(labels, args.run_label)
    results = Results.load(args.output / "results.json")
    results.runs.append(run)
    results.save(args.output / "results.json")
    (args.output / "results.md").write_text(MarkdownReport().render(results))
    for s in run.by_condition():
        print(f"{s.condition:10} n={s.n} correct={s.correct_rate:.0%} false-ALLOW={s.false_allow_rate:.0%} "
              f"escalate={s.escalate_rate:.0%}")
    print(f"-> {args.output / 'results.md'}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
