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
- `NEBIUS_API_KEY` and `TAVILY_API_KEY` are not configured. Verify Token Factory's `/models` and the Tavily search after credentials are available. Exact model IDs remain unverified. Decionis's connection and workspace-identity checks now pass.

Sources: [hackathon resources](https://nebiusglobalaihackathon.devpost.com/resources), [hackathon FAQ](https://nebiusglobalaihackathon.devpost.com/details/faqs), [Builders Program](https://dev.nebius.com/builders).
