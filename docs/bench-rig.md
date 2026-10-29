# SiteWork bench preparation

Status on 29 October 2026: the physical rig still needs preparation. The
[six requirement approvals](requirements.md) are recorded under
**Festus B. Jejelowo**; no physical recordings or measured labels are available
yet. The US gap and slope profiles have numeric bounds. SE decking, SE trench
and both plumbing profiles currently require human review.

The printable [marker and capture worksheet](../output/pdf/sitework-bench.pdf)
contains a DICT_4X4_50 marker, ID 0, whose outer black square is exactly 40 mm
wide and tall. A 10 mm white border surrounds it. The [standalone SVG](../output/bench/aruco-4x4-50-id0-40mm.svg)
uses the same dimensions.

Print the PDF on A4 at Actual Size / 100%, with Fit and Shrink disabled. Measure
both black edges and the 100 mm check bar. If they are wrong, fix the print scale
and reprint before using the marker. The SVG's entire canvas is 60 mm, including
the white border; do not resize the entire canvas to 40 mm.

## Physical checklist

These tasks need to be performed on the physical rig. Preparing this worksheet
does not establish measured ground truth or a SiteWork verdict.

- [ ] Mount the checked marker on flat, matte card, in the same plane as the
  measured surface. Keep its four corners and white border visible.
- [ ] Set decking boards with a protractor. Suggested capture targets are 0,
  4 and 8 degrees; measure the actual angles and gaps and record the instruments
  and their resolution.
- [ ] Build tabletop trench walls at known slopes measured from horizontal.
  Suggested capture targets are 20, 35 and 50 degrees. Record actual slopes.
  Keep each wall's top and toe corners in frame and uncovered: depth is read
  from where the wall's edge stops.
- [ ] Use an unpressurized push-fit fixture. Mark the manufacturer's insertion
  depth, record a deliberately unseated joint, then record correct seating.
  Preserve the audio, including about three seconds around the seating event.
- [ ] Record outdoor clips of corresponding surfaces, with the marker in the
  measured plane. Include daylight and shade or glare.

The suggested angles are fixture setpoints, not construction requirements or
policy thresholds. Approved authoritative citations determine the policy;
actual measurements determine the evaluation labels.

## Capture order

Prepare and measure each configuration before recording. These are planned
captures, not files that already exist. Keep geometry fixed throughout each
clip: file replay samples its beginning, middle and end.

| Planned ID | Scene | Fixture target or event | Independent record needed |
| --- | --- | --- | --- |
| D01 | Decking | Parallel boards, about 5 mm clear gap | Actual narrowest/widest gap and angle; material and fastener or surrogate description |
| D02 / D03 | Decking | Boards set at 4° and 8°; include a gap outside the US range | Actual angles and both gap extrema over the visible joint |
| T01 / T02 / T03 | Trench | Walls at 20°, 35° and 50° from horizontal | Actual steepest slope and greatest vertical depth; marker upright and level in the cross-section |
| P01 | Plumbing | Deliberately incomplete insertion | Actual pipe-to-fitting angle; product/size, insertion mark and mechanically verified unseated state |
| P02 | Plumbing | One successful seating event, then hold still | Actual alignment; mechanically verified final insertion; original audio around the event |
| P03 | Plumbing | Unseated fixture with an unrelated sharp sound | Same mechanical checks as P01; record the unrelated sound so a false click can be detected in calibration |
| O01 / O02 / O03 | Outdoor | Corresponding decking, trench and plumbing fixtures in daylight or shade/glare | Fresh measurements after positioning; actual lighting and original audio |

For plumbing, keep the pipe and fitting axes at a fixed angle during insertion.
Keep the event within the first 10 seconds and preserve about three seconds
around it. Record the final mechanical seating state separately from what was
heard. A seated joint with no audible click and an unseated joint with a click
are useful observations; do not relabel either to agree with the DSP.

Keep calibration takes separate from the clips used for reported evaluation.
After choosing DSP or edge-fit settings, freeze those settings before collecting
or selecting the held-out evaluation takes. If an eval result motivates a change,
retain and report both runs.

## Clips and ground truth

Record 8-10 seconds per clean clip. Preserve original files and audio. Put
clean originals under data/clips/clean/ and outdoor originals under
data/clips/outdoor/. Start with 3-5 clean clips for Cosmos.

For every clip, record the scene, file name, actual measured angle/gap/slope,
unit, marker size, seating state where applicable, lighting condition,
instrument and operator. Leave unknown values unknown. Do not label a clip
ALLOW, ESCALATE or BLOCK until its expected outcome has been established
against the approved policy.

Use this record beside each original, filling it only after capture:

```text
Clip path and SHA-256:
Recorded at / operator:
Scene / condition / calibration or evaluation:
Product, size, material, fastener or geometry surrogate:
Marker black width / height (mm), checked on paper:
Instrument / resolution / measurement uncertainty:
Actual gap minimum / maximum (mm):
Actual board or pipe-to-fitting angle (degrees):
Actual steepest trench slope (degrees from horizontal) / greatest depth (mm):
Mechanical seating state / insertion mark / check performed:
Lighting, visibility and audio observations:
Applicable pack / expected verdict / independent reason:
```

Transfer only real clips and their measured truth to `eval/labels.csv`. Put
instrument, operator, product, calibration status and any uncertainty in `notes`.
Use `true` or `false` for `seated`; leave inapplicable or unknown measurements
blank. Do not use the fixture target or SiteWork's own reading as truth.

To compare jurisdictions, use one row for each `(clip, jurisdiction)` pair and
keep the physical measurements identical for the same file. Mark these as
paired evaluations in `notes`: the report counts rows, not independent videos.
For the current packs, complete applicable US numeric checks can expect ALLOW
within their bounds or BLOCK outside them. Qualitative SE checks and both
plumbing profiles expect ESCALATE. Establish expectations before seeing model
outputs; record an independent reason for any missing-evidence ESCALATE.

Cosmos may alter geometry or obscure the marker. Review each generated clip
before inheriting its source labels; mark unmeasurable or changed geometry
explicitly.

After real clips and labels are present, run:

```bash
uv run python scripts/eval.py --gate-mode SHADOW --run-label "bench run 1"
```

Keep offline dossier verification enabled. Copy Results numbers only from the
generated `eval/results.md`; an empty-input preflight produces no metrics.

## Rebuild the print sheet

From the repository root:

    uv run --with reportlab python scripts/bench/make_print_sheet.py

This uses OpenCV's actual dictionary generator and draws vector modules at
physical millimetre dimensions. The generated PDF is also checked by decoding
its rasterized marker with OpenCV before delivery.
