# Jurisdiction packs and approved requirements

Every SiteWork verdict is judged against a requirement from a jurisdiction pack:
[`data/packs/US.json`](../data/packs/US.json) or [`data/packs/SE.json`](../data/packs/SE.json).
Decisions read the pack and never the live web.

## How a requirement enters a pack

1. **Build.** `scripts/pack.py --jurisdiction <J> build <scene>` maps and crawls the pack's allowlisted
   seeds with Tavily and extracts PDF seeds. It caches each page's text locally (`data/packs/pages/`,
   git-ignored) and records the URL, retrieval time and SHA-256 of that text.
2. **Propose.** Candidate requirement sentences are extracted from the cached text. Lengths are
   converted to millimetres and stated angles stay in degrees. Slope ratios are kept as written: US text
   is horizontal:vertical, Swedish text is vertical:horizontal.
3. **Approve.** `scripts/pack.py approve` adds a requirement only with a named approver. The pack then
   stores the verbatim excerpt, URL, retrieval time, content hash, machine threshold, approver and
   approval time.

Only structured values reach the gate: a threshold, a URL, a content hash and a date. Retrieved text
never becomes an instruction and cannot change a verdict.

## Current requirements

Two requirements carry numeric thresholds. The other four are approved as qualitative rules: their
threshold is empty (`{}`), so the measurements they would need stay unbounded. SiteWork then reports a
grounding error to the gate, and the inspection escalates. Approving a source never supplies a
tolerance the source doesn't state.

| Pack / scene | Requirement and scope | Machine threshold | Effect with complete evidence |
| --- | --- | --- | --- |
| US decking | [TimberTech Advanced PVC with Cortex screws](https://www.timbertech.com/ideas/installing-composite-decking): side-to-side spacing of 1/8 to 1/4 inch. A product-specific bench reference. | `gap_mm`: min **3.175**, max **6.35** | Both the narrowest and widest gap are checked. Board angle is measured but has no approved bound. |
| SE decking | [Svenskt Trä, Montering av trall, 2:2021, p. 4](https://www.svenskttra.se/siteassets/5-publikationer/pdfer/montering-av-trall-2021-publikation.pdf): choose spacing from the board type and width in Table 3; never install without a gap. | `{}` | **ESCALATE** until a board profile with a measurable clear gap is established. |
| US trench | [OSHA 29 CFR 1926.652(b)(1)(i), Option 1](https://www.ecfr.gov/current/title-29/section-1926.652): 1.5 horizontal to 1 vertical, stated in the rule as 34° from horizontal. | `slope_deg`: max **34** | The steepest visible wall is checked. |
| SE trench | [Arbetsmiljöverket excavation guidance](https://www.av.se/produktion-industri-och-logistik/bygg/arbetsmiljorisker-vid-byggnads--och-anlaggningsarbete/markarbete-och-schaktning): adapt the slope to soil, groundwater, nearby loads, weather and depth; no fixed angle. | `{}` | **ESCALATE** for a competent person's site-specific assessment. |
| US plumbing | [SharkBite installation guidance](https://www.sharkbite.com/us/en/resources/blog/service-and-repair/fitting-tips-guides/the-dos-and-donts-of-installing-sharkbite-fittings): push to the tube stop, verified by the correct insertion mark. | `{}` | **ESCALATE**: no acoustic acceptance test or pipe-to-fitting angle tolerance. |
| SE plumbing | [Säker Vatteninstallation 2026:1, §7.3, p. 62](https://sakervatten.se/wp-content/uploads/2025/10/branschregler-saker-vatteninstallation-2026-web-v2-lagupplost.pdf): install products and systems according to the supplier's instructions. | `{}` | **ESCALATE** until the actual system's instructions establish joint checks. |

## How the sources are read

- **US gap.** The conversion uses exactly 25.4 mm per inch, so 1/8 inch is **3.175 mm**. The
  extractor's 3.17 mm is a rounded reading aid, not the bound. The spacing applies to the Cortex
  product heading; other decking materials and fasteners can need different spacing.
- **Swedish decking.** Svenskt Trä says Table 3's `kant-till-kant-avstånd` is **not** the clear gap.
  Its 3 mm `fogsprång` limit is the vertical step between board surfaces, so it must not become
  `gap_mm <= 3`. Its roughly 0.5° fall away from a house is also a different quantity from the angle
  between adjacent boards.
- **US trench.** The numeric profile covers one sloping option. Field entry also depends on the
  excavation configuration, depth, soil and protective system, which a tabletop wall's angle doesn't
  establish. The 34° bound is the angle the rule states.
- **Swedish plumbing.** `fixerad vinkelrätt` concerns pipes passing through a floor or wall. It doesn't
  set the permitted angle between a pipe and a fitting.
- **Seating.** A sharp sound is not independent evidence of mechanical seating. Establish seating from
  the fitting's insertion mark and installation checks, and use that truth to evaluate the DSP. Neither
  plumbing source supports a joint tolerance or a click-only release rule.

## Extending the packs

- **A numeric SE decking profile.** Identify the timber type and nominal width, measure the actual
  width and edge-to-edge spacing, then establish the applicable clear-gap check. Don't subtract a
  nominal width and treat the result as a universal gap limit.
- **Automatic plumbing release.**
  1. Select the actual fitting and its supplier instructions.
  2. Validate the seating detector against mechanically verified joints.
  3. Obtain an explicit alignment criterion, with its scope.

  Until then, plumbing recordings can evaluate angle error and seating detection, but never release
  automatically.
- **Bench truth.** Follow the [capture plan](bench-rig.md). Record the products, sizes, instruments and
  measurements made independently of SiteWork. Fixture setpoints are not measurements.

## Governed policy updates

`scripts/watch.py --jurisdiction <J> run` runs a Tavily Research task with a structured schema and
checks each finding's source against the pack's allowlist. It then proposes a `policy.update` through
the same Decionis gate; only kinds, scenes, URLs, dates and title hashes are sent.

SiteWork's policy escalates every `policy.update`. A named reviewer then approves or rejects it, on the
dashboard or with `scripts/watch.py resolve`. A proposal that Decionis blocked, or never decided, can
only be rejected. Approving a proposal records the review; it doesn't rewrite a pack. A changed
requirement still goes through `pack.py approve`.

For example, a Swedish run found AFS 2025:6 and AFS 2025:8, amendments to AFS 2023:13. Decionis
escalated the proposal, and the reviewer rejected it: both amendments concern asbestos provisions, not
trench acceptance criteria.
