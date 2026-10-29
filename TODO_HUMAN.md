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

- The official hackathon credit request was submitted for the signed-in Token Factory account with activation code `NEBIUS-DEVPOST-GLOBAL26`. Nebius confirmed: "Form submitted" and "The promo code will be emailed to you." Redeem the issued code in Token Factory's **Top up balance → With promo code** when it arrives. The activation code itself is not accepted there.
- An existing Nebius AI Builder Program application is already under review. Nebius's email says to expect an update within two business days. Do not submit a duplicate application.
- An existing AI Builder Program Compute Grants application is also awaiting review. Nebius acknowledged receipt; this is not an approved AI Cloud grant.
- AI Cloud billing is not activated. Its setup form requires a card and says submission will charge $25 to top up the balance. No billing details were submitted or GPU instance created.
- The hackathon publishes $25 in Token Factory credit through the direct form and another $25 through the Builders Program. Its FAQ does not publish a separate AI Cloud credit grant. The compute-grant application is a separate reviewed program.
- `NEBIUS_API_KEY` is not configured. Verify Token Factory's `/models` after its credential is available. Exact model IDs remain unverified. Tavily's live search and Decionis's connection and workspace-identity checks now pass.

Sources: [hackathon resources](https://nebiusglobalaihackathon.devpost.com/resources), [hackathon FAQ](https://nebiusglobalaihackathon.devpost.com/details/faqs), [Builders Program](https://dev.nebius.com/builders).

## Tavily account and credentials

- Created and email-verified the account for `festus@binariesfort.com` on 29 October 2026. The account uses the free **Researcher** plan with 1,000 API credits per month; pay-as-you-go is off.
- The existing default development API key is saved as `TAVILY_API_KEY` in ignored `.env`, mode 0600. The live `TavilyCheck` passed at 03:00 Stockholm and returned three results from the configured OSHA/eCFR allowlist, all on `www.osha.gov`.
- Nebius Builders advertises an additional $25 Tavily credit, subject to eligibility and partner terms. The existing Builders application is still under review, and no Tavily coupon has been issued or applied. The Tavily dashboard has a **Coupon** field for the issued code.

Sources: [Tavily pricing](https://tavily.com/pricing), [Builders Program](https://dev.nebius.com/builders).

## Still needed from you

- [ ] `NEBIUS_API_KEY` (Token Factory) in `.env`, then run `make check`. It lists the Nemotron candidates from `GET /models` and probes whether the Omni model accepts `input_audio`. The exact IDs then go into `sitework/config.py`. Tavily and Decionis credentials are already configured and verified.
- [x] **Decionis gate route** (your call, 29 Oct): dci gateway with verdicts ALLOW / BLOCK / ESCALATE / ERROR.
  - The SDK's `/v1/authority/evaluate` and `/enforce` return 404 on the live API.
  - SiteWork therefore sends an Agent-Safe Intent v1 to `/v1/authority/enforce-and-bind`, with `tenant_id` = the org UUID, then claims the grant at `/v1/execution/consume-token`.
  - One SHADOW integration intent returned ALLOW with dossier `e81018f7-2a9b-40ea-8e4f-6141afa91d1e`.
  - Not exercised live yet: claiming a real grant. That needs a clean ALLOW.
- [ ] **Load the SiteWork policy into Decionis. Urgent.** The `dci` tenant currently auto-approves SiteWork intents (`POLICY_ACTION_AUTO_APPROVE`), including one with no measurements, no citations and an error in its evidence.
  - Policy authoring is now unblocked: use `DECIONIS_POLICY_API_KEY` directly with `DECIONIS_API_BASE`. Creating the key did not create or activate the SiteWork policy.
  - SiteWork's interlock keeps the light off green when evidence has errors, but the verdicts are not the SiteWork rules until `policies/sitework.md` is active.
  - That file lists the rules and every context field they read.
  - Tell me the `policy_version` or `decision_type` to send if it should be pinned (`DECIONIS_DECISION_TYPE`).
- [ ] **Approve the decking requirement.** Run `uv run python scripts/pack.py search decking "deck board spacing gap between deck boards"`, read the candidates, then approve one with your name and the threshold you accept, in mm. For example, TimberTech states "1/8” to 1/4” side-to-side spacing" (3.17–6.35 mm):
  `uv run python scripts/pack.py approve decking <index> --requirement "..." --threshold '{"gap_mm": {"min": 3.17, "max": 6.35}}' --approver "Your Name"`
  No source found so far states an angle limit, so `angle_deg` stays unchecked unless you approve one.
- [ ] **One accidental decision to know about.** While probing routes on 29 Oct, an empty-body `POST /v1/protocol/evaluate-decision` returned 200 `verdict: ALLOW` (`authority_classification: OBSERVATIONAL`) instead of a validation error. It may have recorded one decision, with idempotency key `probe-empty-body`. It was not repeated.
- [ ] **Cosmos Transfer run (you run it on a GPU).** The scripts and full instructions are in `scripts/cosmos/README.md`. Steps:
  1. Record 3–5 clean clips, 6–10 s each, into `data/clips/clean/`. Use a fixed camera, keep the ArUco marker in frame, and set the work up beforehand: decking at known angles, trench at known slopes.
  2. Activate Nebius AI Cloud billing (see above). Create a preemptible `gpu-h100-sxm` VM (`eu-north1`) or a `gpu-h200-sxm` VM, preset `1gpu-16vcpu-200gb`, using image family `ubuntu24.04-cuda12` and a 200 GiB `network_ssd` boot disk.
  3. **AWS fallback quota requests filed:** 16 vCPU each for Running On-Demand P instances (`L-417A185B`) and All P Spot Instance Requests (`L-7212CCBC`) in Stockholm (`eu-north-1`). Both are `CASE_OPENED`, awaiting approval. EC2 confirms `p5.4xlarge` is offered there and supports both purchase options, with one 80 GiB H100. Request IDs and status commands are in [the handoff](scripts/cosmos_transfer/README.md). No GPU instance was launched.
  4. Create a Hugging Face Read token and accept the NVIDIA Open Model License at huggingface.co/nvidia/Cosmos-Guardrail1.
  5. On the VM, run `setup.sh`, then `hf auth login`, then `run.py --cloud nebius --instance "<platform> <preset>" --distilled`.
  6. Copy `data/clips/` back. `RUN_INFO.md` records which cloud ran the job, plus per-variant wall times.
- [ ] **Bench rig.**
  - Print the [prepared marker and capture worksheet](output/pdf/sitework-bench.pdf) at 100%. Check both black edges are 40 mm and the check bar is 100 mm. The vector dimensions and marker ID 0 were verified digitally; the paper print still needs measuring.
  - Follow [the bench checklist](docs/bench-rig.md): measure board angles and gaps, model trench slopes, and an unseated push-fit joint followed by proper seating with audio.
  - Record outdoor phone clips and 3–5 clean originals, preserving measured ground truth and original audio. Suggested fixture angles in the worksheet are not policy thresholds.
