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
preceding readable frame for its contact sheet; the file-replay pipeline used in the
completed run returned only its two readable samples (it now steps back to a frame
that reads; see the every-frame check below). The originals were not trimmed, repaired
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

## Completed run

`scripts/eval.py` completed the run above against the live dci gateway in SHADOW
mode, using commit `9933047` and policy `decionis-starter-v2+sitework-1`.
The generated report records **6/6 ESCALATE**, **0/6 false ALLOW**, no gate
failures, **6/6 dossiers verified offline**, and **778.3 ms gate p95 latency**
(nearest rank, six requests).

Measurement errors and seating accuracy are unavailable because their ground
truth fields are blank. The DSP processed audio; no Nemotron vision inference
ran because no sampled frame had a calibration marker. These rates apply only
to the six paired refusal cases and do not estimate accuracy on valid inspections.

## Cosmos refusal run (30 October)

The second run adds the Cosmos Transfer 2.5 rain, mud and dusk-glare variants of
`sw-rig05` and `sw-rig08` (seconds 0–6 of each), paired across US and SE: twelve
rows from six generated videos, plus the six outdoor rows again. The roof clip
`sw-rig02` and its variants matched no hold-point scene and were left out.

Every variant row was labelled **ESCALATE** before the run: no calibration
marker in any generated frame (`data/clips/RUN_INFO.md`), no audio track, and a
qualitative plumbing pack. Against the live dci gateway in SHADOW mode, commit
`8339eb4`, the report records **18/18 ESCALATE**, **0 false ALLOW** in every
condition, no gate failures, **18/18 dossiers verified offline** and **735.5 ms
gate p95** (nearest rank, n=18).

This shows that the weather variants are refused, not that SiteWork measures
correctly through rain, mud or glare. The variants derive from two outdoor clips
that are also in the file, so they are not independent recordings, and no
measurement or seating accuracy was estimated.

## Every-frame check (29 October)

A second pass over all ten files, after the run above:

- **Markers.** Every second decoded frame of each file, and every frame of
  `sw-rig09.mp4`, was searched for `DICT_4X4_50` markers. None contains the printed
  marker. In `sw-rig09.mp4`, asphalt texture decoded as **ID 17** twice: frame 35
  (31 × 5 px) and frame 184 (about 15 px), with scale quality 0.05 and 0.17.
  SiteWork used to accept any ID; it now accepts only the printed marker's
  (`FIDUCIAL_ID`, 0), so these are ignored.
- **Sampling.** Seeking to frames 569 and 570 of `sw-rig04.mp4` fails, although
  playback decodes them. Replay now steps back to the nearest frame that reads
  (568) and raises an error if none within five frames does. Frame 568 has no
  marker either.
- **Seat-click DSP.** On the first 10 s of each file's audio, the starting
  thresholds (onset ratio 8, centroid 1500 Hz) read seated on three files:
  `sw-rig02` (ratio 8.17, 1612 Hz, confidence 0.04), `sw-rig04` (8.82, 2457 Hz,
  0.21) and `sw-rig07` (9.45, 2254 Hz, 0.36). They read not seated on the other
  seven. No seating event is established in these files, so these readings cannot
  be scored. They show that outdoor sounds can cross the starting thresholds.
  Every such reading is below the policy floors, which start at 0.70.

These findings change no recorded result. The six labelled rows still have no
marker, so their ESCALATE verdicts stand.
