# Implementation gap report — 30 October 2026

Scope: `main` at `3ea16a1` plus the UI polish on `p6-polish`, checked against
`IMPLEMENT.md` (spec) and `brief.submission.md` (public claims). Code freeze is
12:00 Stockholm. Every finding below was checked against the cited code.

## What was validated live today

All runs used the real dci gateway in ENFORCEMENT, synthetic clips with marker ID 0.

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

**Not validated live:** a named human release (blue light), a webcam source,
plumbing with real audio, any bench capture with measured truth.

## 1. Before freeze: definition of done (§9) and brief accuracy

| # | Gap | Evidence | Owner | Fix |
|---|---|---|---|---|
| D1 | INTERNAL section and 16 `⟦ ⟧` Results cells remain | `brief.submission.md:137-140`, `:198-226` | Human | Delete INTERNAL. Mark clean-bench cells "not measured" with the reason, or fill Cosmos ESCALATE/false-ALLOW from D2 |
| D2 | Eval covers outdoor only; the 9 Cosmos clips are unlabelled | `eval/labels.csv:2-7`; `sitework/evaluate.py:18-20` handles any condition | Human labels, code runs | Label the Cosmos clips as input-refusal cases (expected ESCALATE; no marker in any frame) and run `scripts/eval.py` in SHADOW. Fills ESCALATE and false-ALLOW per Cosmos condition only. `sw-rig02` is a roof clip with no matching scene |
| D3 | Plumbing demo row shows BLOCK → ALLOW; both packs make plumbing ESCALATE | `brief:149`; `sitework/scenes.py:238` | Human | Left as written by decision; film only what runs |
| D4 | "Wall slope **and depth** vs. the rule": depth is recorded, never checked | `brief:28`, `:50`; `sitework/scenes.py:225` | Human | "Wall slope vs. the rule; depth recorded" |
| D5 | "Board angle vs. the cited requirement": US decking has a gap limit only | `brief:49`, `:150`; UI shows "No cited limit" | Human | Say the angle is measured and the gap is checked. A decking BLOCK needs a gap outside 3.175–6.35 mm |
| D6 | "Pipe-to-fitting alignment … computed": code exists, but there is no approved tolerance or accuracy figure | `brief:28`; `sitework/measure/align.py:25-32` | Human | Don't imply alignment is checked against a rule |
| D7 | "Shadow Mode … our evaluation runs this way" overstates: SHADOW calls, scored against our own labels | `brief:120`; `eval/results.md:7` | Human | "Our evaluation calls Decionis in SHADOW mode" |
| D8 | "Lets us measure accuracy", "Cosmos covers…", "more careful, not more wrong" read as results | `brief:44`, `:163` | Human | Phrase as purpose and design ("is designed to") |
| D9 | "…dashboard and bench rig" built: only the print sheet and capture plan exist | `brief:171` | Human | "bench print sheet and capture plan" |
| D10 | "On ALLOW, SiteWork claims the grant": it now also finalizes | `brief:32`, `:118` | Human | "claims and finalizes the single-use grant" |
| D11 | Pending proposal `0a7c4022` never reached Decionis (403 at the time) | `data/proposals/0a7c4022-….json` | Human | Reject it by name in Policy review; approval is now refused |

## 2. Code fixes: fail-safe and correctness

| # | Gap | Evidence | Fix |
|---|---|---|---|
| F1 | Missing `ffmpeg` makes a plumbing replay return HTTP 500, with no gate call and no dossier | `sitework/capture.py:193` raises `FileNotFoundError`; `sitework/scenes.py:255-259` catches `ValueError` only | Catch `OSError` in `FileAudio.record` and raise `ValueError`, so it escalates. Add ffmpeg to README setup **Fixed on `p6-polish`.** |
| F2 | A jurisdiction switch during a running inspection changes the jurisdiction, then returns 409 without re-deciding | `sitework/app.py:139` sets it before the busy check at `:143` | Take the lock first **Fixed on `p6-polish`.** |
| F3 | Re-grounding an old ALLOW claims a fresh grant on old evidence; this happened today (`b5532637`, from `05722767`) | `sitework/scenes.py:131-137`; the evidence has no capture time or source | Don't claim on re-grounded evidence; add a capture time and source to the evidence |
| F4 | Any ALLOW with `should_execute` is claimed, whatever the action or mode: a `policy.update` ALLOW would be finalized `COMMITTED` with nothing applied, and SHADOW relies on Decionis sending `should_execute=false` | `sitework/gate/authority.py:104-110` | Claim only release actions (`inspection.release_hold`, `trench.authorize_entry`), never in SHADOW **Fixed on `p6-polish`.** |
| F5 | The phone light turns blue for a resolution on **any** record, and keeps the last green after the source changes | `static/light.mjs:35`; `sitework/app.py:101-109` | Send `record_id` with the light and match it; reset the light when the source changes **Fixed on `p6-polish`.** |
| F6 | The config default gateway is the unprovisioned `sitework.decionisedge.com` | `sitework/config.py:57` (`.env.example` uses dci) | Default to `https://dci.decionisedge.com` **Fixed on `p6-polish`.** |
| F7 | `DECIONIS_DECISION_TYPE` set to anything else makes the SiteWork rules miss and the starter rules apply | `policies/sitework.json:12`; `sitework/config.py:68` | Claim only when `checks_total > 0` and `checks_outside == 0`, as a SiteWork-side interlock |
| F8 | Finalize is reported before the light changes; no `expected_effect_digest` is bound, so a future INDETERMINATE claim can't be reconciled | `sitework/gate/authority.py:114-145` | Bind an expected effect digest at decision time, and finalize after the light state is set (FAILED if that fails). Confirm the field with Decionis first |
| F9 | A proposal Decionis BLOCKed can still be approved | `sitework/ground/watch.py:165-177` | Allow approval only after ESCALATE or REVIEW_REQUIRED |

## 3. Spec items partial or missing

| # | Spec | Status | Owner |
|---|---|---|---|
| S1 | P1 "board at a known angle … within your stated tolerance" | Missing: no bench capture with measured truth (`TODO_HUMAN.md`, Bench rig) | Human |
| S2 | P3 jurisdiction toggle | Works live. The re-grounded result drops the overlay (`scenes.py:137`), so the inspected frame disappears | Code: carry the overlay over |
| S3 | §4 ESCALATE resolution "recorded in the dossier" | Recorded alongside, in local unsigned JSON (`sitework/dossier.py:68-85`); never run live | Human: run once before filming |
| S4 | P4 audio model + DSP agree | DSP only; Token Factory rejects audio (accepted deviation) | — |
| S5 | §7 overlay on the live feed | The overlay is on the inspected still only | Accept, or code |
| S6 | §7 stack light on a phone | `make demo` binds 127.0.0.1 (`Makefile:16`); a phone can't reach `/light`. The API has no auth, so binding to the LAN lets anyone record a "human release" | Code: optional `HOST`, with a warning |
| S7 | Webcam source | Implemented (`sitework/capture.py:109-144`); camera 0 does not open on this machine; untested on a real camera | Human |
| S8 | Policy review on a fresh clone | `data/proposals/` is git-ignored, so the panel is empty | Accept, or commit a sample |
| S9 | Replay audio | First 10 s of the clip, not about 3 s around the join | Code, after bench capture |
| S10 | Doc drift | `policies/sitework.md:8` and `TODO_HUMAN.md:43` said `consume-token`; now name `claim-token` + `finalize-token` | Fixed on `p6-polish` |

## Checked and backed

- **Conformance vectors:** 11 Agent-Safe vectors and 17 mutations reproduce byte for byte (`tests/intent.py`).
- **Packs:** built with Tavily Map, Crawl and Extract under allowlists (US 60 sources, SE 19); six thresholds approved by name.
- **Fail-safe:** green only on ALLOW + execute + claimed + finalized (`sitework/light.py`). Claimed but not finalized shows red NOT RELEASED. Evidence errors block the claim. Mock mode shows red MOCK GATE.
- **Verify and tamper:** both use `@decionis/verify@0.5.0`.
- **Brief figures:** match `eval/results.md` and `RUN_INFO.md` (778.3 ms, 6/6, 453.2 s, 837 frames).

## Suggested order before 12:00

1. ~~Code fixes F1, F2, F4, F5, F6~~: done on `p6-polish`, unit-tested and smoke-tested live (`bbad88e4`).
2. Brief edits D1, D4–D10; human decision on D2.
3. Human: reject `0a7c4022` (D11), run one named release live (S3), film.
4. After freeze: F3, F7, F8, F9 and bench capture (S1).
