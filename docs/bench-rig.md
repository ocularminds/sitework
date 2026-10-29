# SiteWork bench preparation

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

## Clips and ground truth

Record 8-10 seconds per clean clip. Preserve original files and audio. Put
clean originals under data/clips/clean/ and outdoor originals under
data/clips/outdoor/. Start with 3-5 clean clips for Cosmos.

For every clip, record the scene, file name, actual measured angle/gap/slope,
unit, marker size, seating state where applicable, lighting condition,
instrument and operator. Leave unknown values unknown. Do not label a clip
ALLOW, ESCALATE or BLOCK until its expected outcome has been established
against the approved policy.

Cosmos may alter geometry or obscure the marker. Review each generated clip
before inheriting its source labels; mark unmeasurable or changed geometry
explicitly.

## Rebuild the print sheet

From the repository root:

    uv run --with reportlab python scripts/bench/make_print_sheet.py

This uses OpenCV's actual dictionary generator and draws vector modules at
physical millimetre dimensions. The generated PDF is also checked by decoding
its rasterized marker with OpenCV before delivery.
