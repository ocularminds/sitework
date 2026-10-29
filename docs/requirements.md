# Approved bench requirements

Approver: **Festus B. Jejelowo**, as supplied with the instruction to approve
the US and SE packs. Recorded on 29 October 2026. Each requirement in
[US.json](../data/packs/US.json) and [SE.json](../data/packs/SE.json) includes the
approver, UTC approval time, verbatim source excerpt, URL, retrieval time and
SHA-256 of the Tavily page text.

Two source-backed numeric profiles are ready for bench checks. Four requirements
are approved as qualitative rules: their empty threshold dictionaries leave
required measurements unbounded, so SiteWork sends a grounding error to the
gate and keeps automatic release closed. Approval of a source does not supply
an unstated tolerance.

| Pack / scene | Approved requirement and scope | Machine threshold | Current effect with complete evidence |
| --- | --- | --- | --- |
| US decking | [TimberTech Advanced PVC with Cortex screws](https://www.timbertech.com/ideas/installing-composite-decking): side-to-side spacing of 1/8 to 1/4 inch. A product-specific reference for the bench. | `gap_mm`: min **3.175**, max **6.35** | Check both minimum and maximum gaps. Board angle is measured but has no approved bound. |
| SE decking | [Svenskt Trä, Montering av trall, 2:2021, p. 4](https://www.svenskttra.se/siteassets/5-publikationer/pdfer/montering-av-trall-2021-publikation.pdf): select spacing using the board type and width in Table 3; never install without a gap. | `{}` | **ESCALATE** until a suitable board profile and measurable gap requirement are established. |
| US trench | [OSHA 29 CFR 1926.652(b)(1)(i), Option 1](https://www.ecfr.gov/current/title-29/section-1926.652): 1.5 horizontal to 1 vertical, stated in the rule as 34 degrees from horizontal. | `slope_deg`: max **34** | Check the steepest visible wall in the tabletop sloping demonstration. |
| SE trench | [Arbetsmiljöverket excavation guidance](https://www.av.se/produktion-industri-och-logistik/bygg/arbetsmiljorisker-vid-byggnads--och-anlaggningsarbete/markarbete-och-schaktning): adapt slope to soil, groundwater, nearby loads, weather and depth; no exact angle is prescribed. | `{}` | **ESCALATE** for a competent person's site-specific assessment. |
| US plumbing | [SharkBite installation guidance](https://www.sharkbite.com/us/en/resources/blog/service-and-repair/fitting-tips-guides/the-dos-and-donts-of-installing-sharkbite-fittings): push to the tube stop, verified by the correct insertion mark. | `{}` | **ESCALATE**; this clause supplies neither an acoustic acceptance test nor a pipe-to-fitting angle tolerance. |
| SE plumbing | [Säker Vatteninstallation 2026:1, §7.3, p. 62](https://sakervatten.se/wp-content/uploads/2025/10/branschregler-saker-vatteninstallation-2026-web-v2-lagupplost.pdf): install products and systems according to the supplier's instructions. | `{}` | **ESCALATE** until the actual system and its current dated Swedish instructions establish applicable joint checks. |

## Source interpretation

- The US gap conversion uses exactly 25.4 mm per inch: 1/8 inch is **3.175 mm**.
  The candidate extractor's 3.17 mm is a rounded reading aid, not the approved
  lower bound. The Cortex product heading was checked in the cached source;
  other decking materials and fasteners can require different spacing.
- Svenskt Trä explicitly says that Table 3's `kant-till-kant-avstånd` is **not**
  the clear gap. The PDF's Figure 2 and table were checked visually. Its
  `fogsprång` limit of 3 mm concerns the vertical step between board surfaces;
  it must not become `gap_mm <= 3`. The approximate 0.5° fall away from a house
  is also a different quantity from SiteWork's angle between adjacent boards.
- The OSHA numeric profile covers one sloping option. Field entry also needs
  the applicable excavation configuration, depth, soil and protective-system
  assessment. Those are not established by a tabletop wall's angle. The 34°
  bound is the angle explicitly stated by the rule, not an independently
  calculated or calibrated tolerance.
- In Säker Vatten, `fixerad vinkelrätt` concerns pipe penetrations through a
  floor or wall relative to that substrate. It does not set the permitted
  angle between a pipe and a fitting. Section 7.3 is the relevant supplier
  instruction requirement for the proposed joint fixture.
- A sharp sound is not independent evidence of mechanical seating. Establish
  seating from the selected fitting's insertion mark and installation checks;
  use that truth to evaluate the DSP. No 2° joint tolerance or click-only
  release criterion has been attributed to either plumbing source.

## What the unfinished rig must establish

Follow [the capture plan](bench-rig.md). Record the actual products and fitting
sizes, the instruments and their resolution, and measurements made independently
of SiteWork. Mark any substitute materials as geometry surrogates for the
stated bench profile.

For a numeric SE decking profile, identify the timber type and nominal width,
measure its actual width and edge-to-edge spacing, then establish the applicable
clear-gap check. Do not subtract a nominal width and treat the result as a
universal gap limit.

For automatic plumbing release, select the actual fitting and supplier
instructions, validate the seating detector against mechanically verified
examples, and obtain an explicit bench alignment criterion with its scope.
Until then, plumbing recordings can evaluate angle error and seating detection,
but an ESCALATE does not demonstrate an automatic plumbing release.

The physical rig was reported as still needing preparation on 29 October.
`eval/labels.csv` therefore remains header-only. Fixture setpoints in the capture
plan are not recorded measurements or evaluation labels.

## Verification on 29 October

All six stored excerpts matched the cached Tavily text and its SHA-256, with the
supplied approver name and UTC timestamps. The grounding check found no missing
required bounds for US decking/trench and retained the expected missing-bound
errors for the four qualitative approvals.

The existing grounding, scene, trench, plumbing and evaluation tests passed
(48 tests). Running `scripts/eval.py --gate-mode SHADOW --run-label "bench readiness
2026-10-29"` exited with code 2: `labels.csv has no rows yet; record clips and
label them first`. No clips were processed, no model/gateway calls were made by
that invocation, and no Results files were generated.
