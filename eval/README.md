# Evaluation scope

`scripts/eval.py` runs every row of [`labels.csv`](labels.csv) through the full pipeline and the real
Decionis gate, then appends the run to [`results.json`](results.json) and re-renders
[`results.md`](results.md). Read the results with the scope below.

## What the current labels cover

The current labels are **input-refusal cases only**. They test that SiteWork refuses to release what it
cannot measure. They do not measure construction compliance, dimensional accuracy, joint alignment or
mechanical seating.

**Outdoor recordings.** Ten raw phone videos, `sw-rig01.mp4` to `sw-rig10.mp4`, are kept unchanged in
`data/clips/outdoor/`; their hashes match the originals. They have no independent measurements. The
[intake manifest](outdoor-intake.json) records each file's content, hash, duration, sampled frames and
why it was or wasn't selected. Three pipe and drainage clips are labelled:

| Clip | Visible subject | Use |
| --- | --- | --- |
| `sw-rig04.mp4` | Paired pipes and couplings against brickwork; the camera pans away | Plumbing input with no calibration marker |
| `sw-rig05.mp4` | Exterior vertical pipe and drainage at a building base | Plumbing input with no calibration marker |
| `sw-rig08.mp4` | Exterior downpipe elbow, wall panels and windows | Plumbing input with no calibration marker |

No push-fit product or seating event is established in them. The other seven clips show no supported
decking or trench hold point and remain reference footage.

**Cosmos variants.** The rain, mud and dusk-glare variants of `sw-rig05` and `sw-rig08` are also
labelled (see [Cosmos stress inputs](../docs/cosmos.md)). The roof clip `sw-rig02` and its variants match
no hold-point scene and are left out.

Each clip is evaluated against both US and SE, so there are **18 rows from nine unique videos**. These
are paired observations: the report counts rows, not independent recordings.

**Expected outcome.** Every row was labelled **ESCALATE** before any run, because:
- no frame shows the calibration marker;
- the Cosmos variants have no audio track;
- both plumbing requirements are qualitative, with no machine threshold for seating or alignment.

All dimensional and seating truth fields are blank. The DSP can process the original audio, but its
output cannot be its own ground truth. With no marker, the vision step is skipped, and the dossier
doesn't claim that an unused model ran.

## Results

The latest run, against the live dci gateway in SHADOW mode, gave:
- **18/18 ESCALATE**, with **no false ALLOW** in any condition (rain, mud and dusk glare n=4 each;
  outdoor n=6);
- no gate failures;
- **18/18 dossiers verified offline**;
- **735.5 ms** gate p95 latency (nearest rank, n=18).

An earlier run on the six outdoor rows alone also escalated all six. Both runs are kept in
[`results.md`](results.md).

A correct ESCALATE on an uncalibrated input shows that the hold stays closed. It doesn't measure
Nemotron's physical accuracy or demonstrate a clean ALLOW or BLOCK inspection. Those need calibrated
bench captures with independently measured truth; see the [capture plan](../docs/bench-rig.md).

```bash
uv run python scripts/eval.py --gate-mode SHADOW --run-label "<describe the run>"
```

## Every-frame check of the outdoor files

- **Markers.** Every second decoded frame of each file, and every frame of `sw-rig09.mp4`, was searched
  for `DICT_4X4_50` markers. None shows the printed marker. In `sw-rig09.mp4`, asphalt texture decoded
  as marker ID 17 twice, at scale quality 0.05 and 0.17. SiteWork accepts only the printed marker's ID
  (`FIDUCIAL_ID`, 0), so these are ignored.
- **Sampling.** Seeking to the last frames of `sw-rig04.mp4` (569 and 570) fails, although playback
  decodes them. Replay steps back to the nearest frame that reads, and raises an error if none within
  five frames does. That nearest frame, 568, has no marker either. The originals were not trimmed,
  repaired or transcoded.
- **Seat-click DSP.** On the first 10 s of each file's audio, the starting thresholds (onset ratio 8,
  centroid 1500 Hz) read "seated" on three files:

  | File | Onset ratio | Centroid | Confidence |
  |---|---|---|---|
  | `sw-rig02` | 8.17 | 1612 Hz | 0.04 |
  | `sw-rig04` | 8.82 | 2457 Hz | 0.21 |
  | `sw-rig07` | 9.45 | 2254 Hz | 0.36 |

  No seating event is established in these files, so these readings can't be scored. They do show that
  outdoor sounds can cross the starting thresholds. Every such reading is below the policy's lowest
  confidence floor, 0.70.

## Adding bench clips

For every bench clip, add one row per `(clip, jurisdiction)` with the truth measured independently and
the verdict the approved requirement implies. The README's Evaluation section lists the columns.
Establish the expected verdict before looking at model output, keep calibration takes separate from
evaluation takes, and report every run, including one that follows a policy change.
