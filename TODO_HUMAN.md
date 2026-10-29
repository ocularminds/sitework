# SiteWork setup — P0

Updated 29 October 2026, Europe/Stockholm.

## AgentSafe gateway

- **Selected and connected:** the user chose the existing `https://dci.decionisedge.com` gateway. Its locally stored ingress key matches the active fleet registry. An authenticated `GET /v1/health` returned HTTP 200, `ok: true`, and `agentsafe-execution: PASSTHROUGH` on 29 October 2026. The key is now in SiteWork's ignored `.env` with mode 0600.
- **API authentication verified:** the workspace API key for `124e5022-6eee-4717-ab65-a03899db6237` is now saved in ignored `.env`, mode 0600. Direct and gateway-routed `POST /v1/auth/credential-context` returned HTTP 200 for that workspace. The key has `org:read`, `decision:run`, `decision:read`, and `policy:read` scopes. SiteWork policy evaluation and signed inspection decisions remain work for P1.
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
- [ ] **Decionis gate call for P1.** Which route should SiteWork call through dci?
  - `@decionis/sdk-node` exposes `POST /v1/authority/evaluate`, which returns `status: ALLOW | BLOCK | ESCALATE | REVIEW_REQUIRED | ERROR` plus `dossier_id` and `dossier_url`.
  - It also exposes `POST /v1/protocol/evaluate-decision`, which returns `outcome: APPROVE | ESCALATE | REJECT | REVIEW`.
  - SiteWork's `Verdict` uses ALLOW/ESCALATE/BLOCK verbatim and never shows green for anything except ALLOW. Confirm how `REVIEW_REQUIRED` and `ERROR` should appear, and which `tenant_id`/`org_id` to send.
- [ ] **SiteWork policy in Decionis.** The workspace key has `policy:read` but no write scope. Create the SiteWork policy (§4 rules: citation required, per-condition confidence floors, thresholds, errors → ESCALATE, named human resolution) in the console, or issue a key that can write it. The policy file format for `policies/` is also still unknown.
- [ ] **Cosmos Transfer run (you run it on a GPU).** The scripts and full instructions are in `scripts/cosmos/README.md`. Steps:
  1. Record 3–5 clean clips, 6–10 s each, into `data/clips/clean/`. Use a fixed camera, keep the ArUco marker in frame, and set the work up beforehand: decking at known angles, trench at known slopes.
  2. Activate Nebius AI Cloud billing (see above). Create a preemptible `gpu-h100-sxm` VM (`eu-north1`) or a `gpu-h200-sxm` VM, preset `1gpu-16vcpu-200gb`, using image family `ubuntu24.04-cuda12` and a 200 GiB `network_ssd` boot disk.
  3. **In parallel, file the AWS fallback quota now:**
     - Running On-Demand P instances `L-417A185B` ≥ 16 vCPU, for `p5.4xlarge`.
     - Or Running On-Demand G and VT instances `L-DB2E81BA` ≥ 8 vCPU, for `g7e.2xlarge`.
     - New accounts start at 0.
  4. Create a Hugging Face Read token and accept the NVIDIA Open Model License at huggingface.co/nvidia/Cosmos-Guardrail1.
  5. On the VM, run `setup.sh`, then `hf auth login`, then `run.py --cloud nebius --instance "<platform> <preset>" --distilled`.
  6. Copy `data/clips/` back. `RUN_INFO.md` records which cloud ran the job, plus per-variant wall times.
- [ ] **Bench rig.**
  - Print an ArUco `DICT_4X4_50` marker at exactly 40 mm.
  - Set decking boards at known angles with a protractor.
  - Cut trench walls at known slopes.
  - Leave one push-fit joint unseated.
  - Record outdoor phone clips.
