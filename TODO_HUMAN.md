# SiteWork setup — P0

Updated 29 October 2026, Europe/Stockholm.

## AgentSafe gateway

- **Selected and connected:** the user chose the existing `https://dci.decionisedge.com` gateway. Its locally stored ingress key matches the active fleet registry. An authenticated `GET /v1/health` returned HTTP 200, `ok: true`, and `agentsafe-execution: PASSTHROUGH` on 29 October 2026. The key is now in SiteWork's ignored `.env` with mode 0600.
- **API authentication verified:** the workspace API key for `124e5022-6eee-4717-ab65-a03899db6237` is now saved in ignored `.env`, mode 0600. Direct and gateway-routed `POST /v1/auth/credential-context` returned HTTP 200 for that workspace. The key has `org:read`, `decision:run`, `decision:read`, and `policy:read` scopes. SiteWork policy evaluation and signed inspection decisions remain work for P1.
- **Policy authoring access ready:** `DECIONIS_POLICY_API_KEY` is saved in ignored `.env`, mode 0600, with exactly `policy:read` and `policy:write`. Direct authentication verified the dci workspace and those scopes at 03:50 Stockholm on 29 October. Use it with `DECIONIS_API_BASE`. AgentSafe's runtime key validation requires narrower scopes, so `DECIONIS_API_KEY` retains its original scopes and still authenticates through dci. The existing authorized operator command issued the authoring key; access to the owner's mailbox was not needed.
- The separate `sitework.decionisedge.com` hostname is not provisioned. A new-workspace signup for `festus@binariesfort.com` reached email verification, after which the user chose dci instead; no new workspace was created. Clasp remains the original workspace's deployment.
- The source matching the live Decionis API revision (`67be91fb88cb2a6197f6921cd7473ccb49223f24`) still permits only one gateway per workspace. Its database reservation and fleet provisioner both enforce this restriction. See `docs/gateway-setup.md` for the concrete implementation work required.
- The operator preflight encountered a Kubernetes ExternalSecrets permission denial and an outdated CLI that refuses two vaults. The user later approved temporary `Key Vault Secrets User` access on only the dci API-key secret. The key was retrieved and verified, then that exact role assignment was deleted and confirmed absent. No permanent Azure access was added.
- SiteWork now sends the selected tenant's ingress key in `AgentSafe-Tenant-Key` and does not try another tenant with that key. Workspace authentication is checked separately using `POST /v1/auth/credential-context` and the configured organization ID.

## Nebius offers and credentials

- **Issued promo codes submitted (29 October).** Two redemption codes arrived in `mail.festus@gmail.com` and were submitted through **Top up balance → With promo code** in `Decionis, Inc.-g65`. The 06:21 email's code produced the explicit confirmation **"Promo code applied. $25.00 added to your account balance."** The 09:11 email specifies $25 and redemption before 31 December 2026; its first submission closed the form, and one recheck returned **"Promocode apply limit exceeded"**. Do not keep resubmitting either code. The emails say credits do not expire once applied.
- **Credit reconciliation complete (29 October).** You confirmed that the combined **$50 Nebius Token Factory credit** is now verified. This closes the earlier reconciliation blocker, when the console still showed -$0.12 and no payment documents. No card top-up was submitted by this setup work. The redemption history and your confirmation are recorded in ignored `.local/setup/nebius-promo-status.json`.
- **Nebius AI Builder Program accepted.** The 29 October welcome email confirms membership and a $25 Token Factory offer sent separately. This acceptance does not approve the separate AI Cloud compute grant.
- An existing AI Builder Program Compute Grants application is also awaiting review. Nebius acknowledged receipt; this is not an approved AI Cloud grant.
- AI Cloud billing is not activated. Its setup form requires a card and says submission will charge $25 to top up the balance. No billing details were submitted or GPU instance created.
- The hackathon publishes $25 in Token Factory credit through the direct form and another $25 through the Builders Program. Its FAQ does not publish a separate AI Cloud credit grant. The compute-grant application is a separate reviewed program.
- **`NEBIUS_API_KEY` configured and verified (29 October).** Created the approved `SiteWork` key in `Decionis, Inc.-g65 / default-project` and saved it in ignored `.env`, mode 0600. The configured `us-central1` endpoint returned HTTP 200 and 18 models; the same catalog request without a key returned 401. A live OpenAI SDK completion on `nvidia/nemotron-3-super-120b-a12b` returned HTTP 200 and `OK`. That exact ID is now recorded in `sitework/config.py`.
- **Vision and audio resolved (29 October).** `us-central1` lists no vision model, but the global endpoint serves `nvidia/Nemotron-3.5-Super-VL`; SiteWork now uses the global endpoint and records that ID. Token Factory rejects `input_audio` for every model (HTTP 422), so the DSP check decides seating alone.

Sources: [hackathon resources](https://nebiusglobalaihackathon.devpost.com/resources), [hackathon FAQ](https://nebiusglobalaihackathon.devpost.com/details/faqs), [Builders Program](https://dev.nebius.com/builders).

## Tavily account and credentials

- Created and email-verified the account for `festus@binariesfort.com` on 29 October 2026. The account uses the free **Researcher** plan with 1,000 API credits per month; pay-as-you-go is off.
- The existing default development API key is saved as `TAVILY_API_KEY` in ignored `.env`, mode 0600. The live `TavilyCheck` passed at 03:00 Stockholm and returned three results from the configured OSHA/eCFR allowlist, all on `www.osha.gov`.
- Nebius Builders advertises an additional $25 Tavily credit, subject to eligibility and partner terms. The Builders application is now accepted, and its welcome email includes partner claim links. The Tavily partner offer has not been claimed or applied. The Tavily dashboard has a **Coupon** field for an issued code.

Sources: [Tavily pricing](https://tavily.com/pricing), [Builders Program](https://dev.nebius.com/builders).

## Still needed from you

- [x] **`NEBIUS_API_KEY` saved and tested.** Catalog authentication and a Nemotron Super completion succeeded. Tavily and Decionis ENFORCEMENT checks also pass.
- [x] **Callable vision/audio models.** Vision: `nvidia/Nemotron-3.5-Super-VL` on the global endpoint, verified with image input. Audio: none callable; the DSP decides (see below).
- [x] **Decionis gate route** (your call, 29 Oct): dci gateway with verdicts ALLOW / BLOCK / ESCALATE / ERROR.
  - The SDK's `/v1/authority/evaluate` and `/enforce` return 404 on the live API.
  - SiteWork therefore sends an Agent-Safe Intent v1 to `/v1/authority/enforce-and-bind`, with `tenant_id` = the org UUID, then claims the grant at `/v1/execution/consume-token`.
  - One SHADOW integration intent returned ALLOW with dossier `e81018f7-2a9b-40ea-8e4f-6141afa91d1e`.
  - Not exercised live yet: claiming a real grant. That needs a clean ALLOW.
- [x] **SiteWork policy loaded** (29 Oct, 04:05 Stockholm, on your go-ahead). `scripts/policy.py submit` sent bundle `decionis-starter-v2+sitework-1` (artifact `c8cd1370-04db-4fb5-9582-fd0faf062d82`) with `DECIONIS_POLICY_API_KEY`.
  - It keeps all 10 starter rules verbatim and adds 7 rules scoped to SiteWork action types (`policies/sitework.json`). It became active immediately.
  - The same errored SHADOW intent that got ALLOW before now gets **ESCALATE** (`POLICY_ACTION_ESCALATE`, `should_execute=false`, dossier `4f0ecb44-eccf-44dd-ba23-1af62b9df591`).
  - Not yet seen live: the ALLOW and BLOCK rules matching on `context.sitework_*` facts. That needs a real clean inspection.
- [x] **ENFORCEMENT scope fixed.** Issued `DECIONIS_ENFORCE_API_KEY` with exactly `decision:enforce`, role MEMBER. SiteWork selects it for ENFORCEMENT/PARALLEL evaluations and grant claims. `DECIONIS_API_KEY` remains the read/SHADOW credential, so dossier retrieval continues to work.
  - The old key's enforced probe reproduced the missing-scope 403. The new key passed that check, exposing the separate provisional-workspace restriction; the approved owner claim below resolved it.
  - `check.py` now checks scopes and workspace mode. `--gate` tests the configured mode, with deliberately incomplete evidence; it no longer forces SHADOW.
  - A live request and response both reported ENFORCEMENT and returned **ESCALATE** for missing evidence, `should_execute=false`, with dossier `b4bdc118-5394-43ce-8a77-e94ec5affe82`. Its signature and required artifact coverage verified offline; verification against Decionis's official JWKS also confirmed the issuer. A clean inspection and an ALLOW grant claim remain separate validation work.
- [ ] **Resolve the first policy update.** Tavily Research found AFS 2025:6 and AFS 2025:8, amendments to AFS 2023:13 published on av.se.
  - The `policy.update` proposal `b07aff06-f2fa-422c-aaa1-f5a482cd9b47` went through the gate in SHADOW mode and came back **ESCALATE** (dossier `14332762-ce65-4cf8-a7ce-0041fb3000b9`, which verifies offline).
  - Approve or reject it with your name on the dashboard, or with `uv run python scripts/watch.py resolve <id> --approve --approver "Your Name"`.
- [x] **Approve decking, trench and plumbing sources in both packs.** Recorded all six approvals on 29 October under the supplied name **Festus B. Jejelowo**, with source excerpts, hashes and timestamps. See [the approval review](docs/requirements.md).
  - US decking: TimberTech Advanced PVC with Cortex screws, gap **3.175–6.35 mm**. This is the selected product-specific bench reference; no board-angle limit is stated.
  - US trench: OSHA 29 CFR 1926.652(b)(1)(i), Option 1, **34° maximum** from horizontal for the bench sloping profile. Field configuration, soil, depth and protective-system assessment remain outside this angle check.
  - SE decking, SE trench and both plumbing approvals are **qualitative**, with empty threshold dictionaries. They intentionally retain human review; six source approvals do not mean six automatic-release profiles.
- [x] **dci owner claim completed.** With the user's explicit approval, claimed the existing `decionisedge dci Agent Workspace` under the verified `mail.festus@gmail.com` account through Decionis's claim page. The workspace, gateway, policies and ledger were retained. Its mode now reports `max_mode: ENFORCEMENT`; the provisional cap no longer blocks requests.
- [ ] **Complete the SE decking fixture profile.** Identify timber type and nominal width, measure actual width and edge-to-edge spacing, then establish an applicable clear-gap check. Svenskt Trä explicitly says Table 3 spacing is not the clear gap; its 3 mm `fogsprång` limit is a vertical step. Neither is a universal `gap_mm` threshold.
- [ ] **One accidental decision to know about.** While probing routes on 29 Oct, an empty-body `POST /v1/protocol/evaluate-decision` returned 200 `verdict: ALLOW` (`authority_classification: OBSERVATIONAL`) instead of a validation error. It may have recorded one decision, with idempotency key `probe-empty-body`. It was not repeated.
- [ ] **Complete the plumbing bench acceptance criteria, for P4.** Both source requirements are approved, but automatic release still needs supported criteria for `seat_audio` and `angle_deg`.
  - Identify the actual fitting/system, pipe size and supplier insertion instructions. Establish mechanical seating independently, then calibrate the acoustic detector against it. A click alone is not proof of full insertion.
  - Neither selected source gives a numeric pipe-to-fitting alignment tolerance. Säker Vatten's `fixerad vinkelrätt` concerns penetrations relative to a wall/floor, not this joint angle. No 2° tolerance has been approved.
  - Both packs currently escalate plumbing. A live plumbing ALLOW/BLOCK sequence remains unvalidated; a qualitative approval does not enable it.
- [x] **Plumbing audio, decided 29 Oct:** the DSP check decides alone (`AUDIO_MODE=dsp`), because Token Factory rejects `input_audio` for every model.
- [ ] **Calibrate the DSP** (`AUDIO_ONSET_RATIO`, `AUDIO_CENTROID_HZ`) on a few bench recordings of a seated and an unseated joint.
- [x] **Vision precision, decided 29 Oct:** edge snapping added. Model lines are snapped to image edges and the fit quality is the confidence; no clear edge escalates. On synthetic renders it fixed trench and plumbing angles to within 0.25° (NOTES_FEEDBACK.md).
- [x] **Decking locate step, fixed 29 Oct.** Asked for edges, Nemotron VL returned box diagonals, so every decking inspection escalated. It now returns each board's four corners and code takes the long sides; all five synthetic decking renders measure after snapping. Still to confirm on real bench frames, where wood grain and shadows add competing edges.
- [ ] **Calibrate snapping with eval.** `EdgeSnapper.MAX_RESIDUAL_PX` (4 px), `EdgeSnapper.CLEAR` (0.5) and `SNAP_REACH_FRAC` (0.04) are starting values; check them, and the policy's confidence floor, against bench and Cosmos clips. `tests/stress.py` checks on synthetic noise, blur, low contrast, shadow, texture, rain, glare and wood grain that a frame is measured right, refused, or below the floor; real frames are the real test.
- [ ] **Label the clips and run eval (P5).**
  - The 29 October readiness invocation of `scripts/eval.py` exited with code 2 because `eval/labels.csv` has no rows. It processed no clips and generated no Results files. The 48 relevant unit tests passed; those are not bench metrics.
  - For every bench, Cosmos and outdoor clip, add a row to `eval/labels.csv` with the truth you set and the verdict you expect (see README, Evaluation).
  - Then run `uv run python scripts/eval.py --run-label "run 1"`.
  - If any condition shows false ALLOWs, decide whether to raise its floor in `policies/sitework.json`, submit it, and run again as "run 2". Both runs go into `eval/results.md` and then into the brief's Results table.
  - Needs: recorded clips and independent measurements. Vision and DSP are configured, and the six source approvals are saved. Qualitative profiles expect ESCALATE; they do not demonstrate automatic release. Review Cosmos geometry and visibility before inheriting labels.
- [ ] **Cosmos Transfer run (you run it on a GPU).** The scripts and full instructions are in `scripts/cosmos/README.md`. Steps:
  1. Record 3–5 clean clips, 6–10 s each, into `data/clips/clean/`. Use a fixed camera, keep the ArUco marker in frame, and set the work up beforehand: decking at known angles, trench at known slopes.
  2. Activate Nebius AI Cloud billing (see above). Create a preemptible `gpu-h100-sxm` VM (`eu-north1`) or a `gpu-h200-sxm` VM, preset `1gpu-16vcpu-200gb`, using image family `ubuntu24.04-cuda12` and a 200 GiB `network_ssd` boot disk.
  3. **AWS fallback quota requests filed:** 16 vCPU each for Running On-Demand P instances (`L-417A185B`) and All P Spot Instance Requests (`L-7212CCBC`) in Stockholm (`eu-north-1`). Both are `CASE_OPENED`, awaiting approval. EC2 confirms `p5.4xlarge` is offered there and supports both purchase options, with one 80 GiB H100. Request IDs and status commands are in [the handoff](scripts/cosmos_transfer/README.md). No GPU instance was launched.
  4. Create a Hugging Face Read token and accept the NVIDIA Open Model License at huggingface.co/nvidia/Cosmos-Guardrail1.
  5. On the VM, run `setup.sh`, then `hf auth login`, then `run.py --cloud nebius --instance "<platform> <preset>" --distilled`.
  6. Copy `data/clips/` back. `RUN_INFO.md` records which cloud ran the job, plus per-variant wall times.
- [ ] **Bench rig.**
  - The user confirmed on 29 October that the physical rig still needs preparation. No physical media was found and `eval/labels.csv` is header-only; no Results numbers can be produced yet.
  - Print the [prepared marker and capture worksheet](output/pdf/sitework-bench.pdf) at 100%. Check both black edges are 40 mm and the check bar is 100 mm. The vector dimensions and marker ID 0 were verified digitally; the paper print still needs measuring.
  - Follow [the capture matrix and measurement record](docs/bench-rig.md): measure board angles and gaps, model trench slopes, and an unseated push-fit joint followed by proper seating with audio. Keep calibration takes separate from evaluation takes.
  - Record outdoor phone clips and 3–5 clean originals, preserving measured ground truth and original audio. Suggested fixture angles in the worksheet are not policy thresholds.
