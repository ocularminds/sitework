# Implementation gap report — 30 October 2026

Scope: `main` at `3ea16a1` plus the UI polish on `p6-polish`, checked against
`IMPLEMENT.md` (spec) and `brief.submission.md` (public claims). Code freeze is
12:00 Stockholm. Every finding below was checked against the cited code.

## What was validated live today

The initial inspection checks below used the real dci gateway in ENFORCEMENT
and synthetic clips with marker ID 0.

| Check | Result | Record |
|---|---|---|
| Health: Token Factory, Tavily, Decionis | PASS (30 models; `nvidia/Nemotron-3.5-Super-VL`; ENFORCEMENT) | `make check` |
| In-limit decking, US | ALLOW → claimed → finalized `COMMITTED` → green | `168e5f87`, `3c4ab1e2`, `156b7b4e`, `8b55d64e` |
| Repeat release on the same target | Every claim succeeded; no target lock | as above |
| In-limit trench, US | ALLOW → claimed → finalized → green | `18ffbb5d` |
| Same trench re-decided under SE | ESCALATE, new citation, no claim | `05722767` |
| Steep trench (59.8°, truth 59.84°), US | BLOCK, red | `b50b718e` |
| Dossier verify | Offline VALID; pinned `DECIONIS_OFFICIAL`, issuer authentic; tamper copy INVALID | `168e5f87` |
| Cosmos outputs | 9 files, 576×1024, 16 fps, 93 frames each (837 total), git-ignored | `data/clips/{rain,mud,dusk_glare}/` |
| Tests | 278 pytest, 12 UI (node), ruff clean | |

Every finalize response says `effect_confirmation: UNCONFIRMED`,
`COMMIT_EVIDENCE_PENDING`. Decionis recorded the commit, not a confirmed effect.

The [subsequent readiness check](live-demo-readiness.md) rejected proposal
`0a7c4022` under **Festus Jejelowo**, exercised a named human release on a fresh
real ENFORCEMENT ESCALATE (`3cf72cca`), and observed the connected stack light
turn blue. A real FaceTime HD webcam also passed capture and dashboard-preview
checks at 1920 × 1080.

**Not validated live:** plumbing seating with a measured fixture and live
microphone audio, or any bench capture with independently measured truth.

## 1. Before freeze: definition of done (§9) and brief accuracy

| # | Gap | Evidence | Owner | Fix |
|---|---|---|---|---|
| D1 | INTERNAL section and 16 `⟦ ⟧` Results cells remain | `brief.submission.md:137-140`, `:198-226` | Human | Delete INTERNAL. Mark clean-bench cells "not measured" with the reason, or fill Cosmos ESCALATE/false-ALLOW from D2 **Done:** Results filled from the 30 Oct run; clean bench marked not measured; INTERNAL removed (its notes are in `.local/brief-internal.md`). |
| D2 | Eval covers outdoor only; the 9 Cosmos clips are unlabelled | `eval/labels.csv:2-7`; `sitework/evaluate.py:18-20` handles any condition | Human labels, code runs | Label the Cosmos clips as input-refusal cases (expected ESCALATE; no marker in any frame) and run `scripts/eval.py` in SHADOW. Fills ESCALATE and false-ALLOW per Cosmos condition only. `sw-rig02` is a roof clip with no matching scene **Done:** 12 Cosmos rows labelled; run on `8339eb4`: 18/18 ESCALATE, 0 false ALLOW, 18/18 verified, p95 735.5 ms. |
| D3 | Plumbing demo row shows BLOCK → ALLOW; both packs make plumbing ESCALATE | `brief:149`; `sitework/scenes.py:238` | Human | Left as written by decision; film only what runs |
| D4 | "Wall slope **and depth** vs. the rule": depth is recorded, never checked | `brief:28`, `:50`; `sitework/scenes.py:225` | Human | "Wall slope vs. the rule; depth recorded" **Done** in the brief. |
| D5 | "Board angle vs. the cited requirement": US decking has a gap limit only | `brief:49`, `:150`; UI shows "No cited limit" | Human | Say the angle is measured and the gap is checked. A decking BLOCK needs a gap outside 3.175–6.35 mm **Done** in the brief, with the decking demo row changed to a too-wide gap. |
| D6 | "Pipe-to-fitting alignment … computed": code exists, but there is no approved tolerance or accuracy figure | `brief:28`; `sitework/measure/align.py:25-32` | Human | Don't imply alignment is checked against a rule **Done** in the brief. |
| D7 | "Shadow Mode … our evaluation runs this way" overstates: SHADOW calls, scored against our own labels | `brief:120`; `eval/results.md:7` | Human | "Our evaluation calls Decionis in SHADOW mode" **Done** in the brief. |
| D8 | "Lets us measure accuracy", "Cosmos covers…", "more careful, not more wrong" read as results | `brief:44`, `:163` | Human | Phrase as purpose and design ("is designed to") **Done** in the brief. |
| D9 | "…dashboard and bench rig" built: only the print sheet and capture plan exist | `brief:171` | Human | "bench print sheet and capture plan" **Done** in the brief. |
| D10 | "On ALLOW, SiteWork claims the grant": it now also finalizes | `brief:32`, `:118` | Human | "claims and finalizes the single-use grant" **Done** in the brief. |
| D11 | Pending proposal `0a7c4022` never reached Decionis (403 at the time) | `data/proposals/0a7c4022-….json` | Human | **Done:** rejected in Policy review under Festus Jejelowo, 30 Oct at 02:28 UTC. The failed gate exchange is retained. |

## 2. Code fixes: fail-safe and correctness

| # | Gap | Evidence | Fix |
|---|---|---|---|
| F1 | Missing `ffmpeg` makes a plumbing replay return HTTP 500, with no gate call and no dossier | `sitework/capture.py:193` raises `FileNotFoundError`; `sitework/scenes.py:255-259` catches `ValueError` only | Catch `OSError` in `FileAudio.record` and raise `ValueError`, so it escalates. Add ffmpeg to README setup **Fixed on `p6-polish`.** |
| F2 | A jurisdiction switch during a running inspection changes the jurisdiction, then returns 409 without re-deciding | `sitework/app.py:139` sets it before the busy check at `:143` | Take the lock first **Fixed on `p6-polish`.** |
| F3 | Re-grounding an old ALLOW claims a fresh grant on old evidence; this happened today (`b5532637`, from `05722767`) | `sitework/scenes.py:131-137`; the evidence has no capture time or source | Don't claim on re-grounded evidence; add a capture time and source to the evidence **Fixed:** a re-decided ALLOW is never claimed; release needs a fresh inspection. |
| F4 | Any ALLOW with `should_execute` is claimed, whatever the action or mode: a `policy.update` ALLOW would be finalized `COMMITTED` with nothing applied, and SHADOW relies on Decionis sending `should_execute=false` | `sitework/gate/authority.py:104-110` | Claim only release actions (`inspection.release_hold`, `trench.authorize_entry`), never in SHADOW **Fixed on `p6-polish`.** |
| F5 | The phone light turns blue for a resolution on **any** record, and keeps the last green after the source changes | `static/light.mjs:35`; `sitework/app.py:101-109` | Send `record_id` with the light and match it; reset the light when the source changes **Fixed on `p6-polish`.** |
| F6 | The config default gateway is the unprovisioned `sitework.decionisedge.com` | `sitework/config.py:57` (`.env.example` uses dci) | Default to `https://dci.decionisedge.com` **Fixed on `p6-polish`.** |
| F7 | `DECIONIS_DECISION_TYPE` set to anything else makes the SiteWork rules miss and the starter rules apply | `policies/sitework.json:12`; `sitework/config.py:68` | Claim only when `checks_total > 0` and `checks_outside == 0`, as a SiteWork-side interlock **Fixed:** SiteWork's own interlock refuses to claim an ALLOW its facts contradict. |
| F8 | Finalize is reported before the light changes; no `expected_effect_digest` is bound, so a future INDETERMINATE claim can't be reconciled | `sitework/gate/authority.py:114-145` | Bind an expected effect digest at decision time, and finalize after the light state is set (FAILED if that fails). Confirm the field with Decionis first **Partly fixed:** each intent binds `expected_effect_digest` (shape from the published `@decionis/mcp` 0.4.0); live, Decionis signed it into the binding (`38a6fd9b`). The effect stays UNCONFIRMED because nothing observes the phone screen, and finalize still precedes the light update. |
| F9 | A proposal Decionis BLOCKed can still be approved | `sitework/ground/watch.py:165-177` | Allow approval only after ESCALATE or REVIEW_REQUIRED **Fixed.** |

## 3. Spec items partial or missing

| # | Spec | Status | Owner |
|---|---|---|---|
| S1 | P1 "board at a known angle … within your stated tolerance" | Missing: no bench capture with measured truth (`docs/bench-rig.md`) | Human |
| S2 | P3 jurisdiction toggle | Works live. The re-grounded result drops the overlay (`scenes.py:137`), so the inspected frame disappears | Code: carry the overlay over **Fixed:** the re-decided result keeps its frame. |
| S3 | §4 ESCALATE resolution "recorded in the dossier" | Recorded alongside, in local unsigned JSON (`sitework/dossier.py:68-85`) | **Live rehearsal done:** Festus Jejelowo released `3cf72cca`; connected light changed from amber to blue. The original gate verdict remains ESCALATE; the human record is still unsigned. |
| S4 | P4 audio model + DSP agree | DSP only; Token Factory rejects audio (accepted deviation) | — |
| S5 | §7 overlay on the live feed | The overlay is on the inspected still only | Accept, or code **Fixed:** the live feed outlines the printed marker; readings stay on the inspected frame. |
| S6 | §7 stack light on a phone | `make demo` binds 127.0.0.1 (`Makefile:16`); a phone can't reach `/light`. The API has no auth, so binding to the LAN lets anyone record a "human release" | Code: optional `HOST`, with a warning **Fixed:** `make demo HOST=0.0.0.0`, with the README warning. |
| S7 | Webcam source | **Tested:** FaceTime HD camera 0 returned five distinct 1920 × 1080 frames; dashboard preview and five streamed frames passed after a main-thread camera open | Done; see [the camera access note](live-demo-readiness.md#real-webcam) |
| S8 | Policy review on a fresh clone | `data/proposals/` is git-ignored, so the panel is empty | Accept, or commit a sample |
| S9 | Replay audio | First 10 s of the clip, not about 3 s around the join | Code, after bench capture |
| S10 | Doc drift | `policies/sitework.md:8` and the internal TODO said `consume-token`; now name `claim-token` + `finalize-token` | Fixed on `p6-polish` |

## Checked and backed

- **Conformance vectors:** 11 Agent-Safe vectors and 17 mutations reproduce byte for byte (`tests/intent.py`).
- **Packs:** built with Tavily Map, Crawl and Extract under allowlists (US 60 sources, SE 19); six thresholds approved by name.
- **Fail-safe:** green only on ALLOW + execute + claimed + finalized (`sitework/light.py`). Claimed but not finalized shows red NOT RELEASED. Evidence errors block the claim. Mock mode shows red MOCK GATE.
- **Verify and tamper:** both use `@decionis/verify@0.5.0`.
- **Brief figures:** match `eval/results.md` and `RUN_INFO.md` (778.3 ms, 6/6, 453.2 s, 837 frames).

## Current status — 30 October

Resolved on `p6-gaps`: D1, D2, D4–D10 (brief and eval), F3, F7, F9, S2, S5, S6 (code),
and F8 in part. F1, F2, F4, F5, F6 and S10 were fixed on `p6-polish` (PR #20).
D11, the live rehearsal in S3, and the camera test in S7 are now complete;
[the readiness record](live-demo-readiness.md) states their validation limits.

Still open, all needing a person or a decision:

- **D3:** plumbing demo row, left as written by decision.
- **S1:** measured bench captures, which would fill the clean-bench column.
- **F8 remainder:** confirming the physical effect needs an observer of the phone light, and Decionis to confirm the effect-evidence flow.
- Accepted as is: S4 (DSP-only audio), S8 (empty Policy review on a fresh clone), S9 (replay audio window, revisit after bench capture).
