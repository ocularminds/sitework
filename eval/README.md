# Evaluation scope

## Outdoor recordings received on 29 October 2026

Ten raw files, `sw-rig01.mp4` through `sw-rig10.mp4`, were copied unchanged into
`data/clips/outdoor/`. SHA-256 checks match the originals. The user confirmed:
"No measurement. Just raw video recording". The [intake manifest](outdoor-intake.json)
records each file's content, hash, duration, sampled frames and selection reason.

The current [labels](labels.csv) cover **input-refusal checks only**. They do not
establish construction compliance, dimensional accuracy, joint alignment accuracy
or mechanical seating accuracy.

| Clip | Visible subject | Use |
| --- | --- | --- |
| sw-rig04.mp4 | Paired pipes and couplings against brickwork; camera pans away | Plumbing input with missing calibration |
| sw-rig05.mp4 | Exterior vertical pipe/drainage component and building base | Plumbing input with missing calibration |
| sw-rig08.mp4 | Exterior downpipe/elbow, wall panels and windows | Plumbing input with missing calibration |

Each selected file is evaluated against US and SE, giving **six rows from three
unique videos**. These are paired observations, not six independent recordings.
The `outdoor` condition follows the user's description of the uploaded set.
Neither product compatibility with a push-fit system nor a seating event has
been established. The other seven files remain available as reference footage;
the review did not establish supported decking or trench hold-point scenes in them.

Before any model/gateway run, each selected row was labeled **ESCALATE** because:

- No ArUco marker was detected in its pipeline sample frames. Across all ten
  clips, no marker was detected in the five review samples per file either.
- Both current plumbing requirements are qualitative and lack the required
  machine thresholds for seating and alignment.

All dimensional and seating truth fields remain blank. The DSP can process the
original audio, but its output cannot supply its own ground truth. The vision
step is skipped when no frame has a calibration marker; the dossier must not
claim that an unused vision model ran.

`sw-rig04.mp4` reports an unreadable final frame (index 570). The review used the
preceding readable frame for its contact sheet; the existing file-replay pipeline
returns only its two readable samples. The originals were not trimmed, repaired
or transcoded. The three selected clips yield eight readable pipeline samples
per jurisdiction, all without a detected marker.

Run the real gateway and retain offline proof verification:

```bash
uv run python scripts/eval.py --gate-mode SHADOW --run-label "outdoor input refusal 2026-10-29 - 3 clips paired US-SE"
```

Read [results.md](results.md) with this scope. A correct ESCALATE on an
uncalibrated input demonstrates that the hold remains closed. It does not measure
Nemotron's physical accuracy or demonstrate a clean ALLOW/BLOCK inspection.
Calibrated bench captures and independently measured truth are still needed for
those claims. See [the capture plan](../docs/bench-rig.md).
