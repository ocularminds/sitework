# SiteWork gateway setup investigation

Status on 29 October 2026: **using the existing dci gateway at the user's request**. SiteWork remains in P0.

## Selected connection

- Gateway: `https://dci.decionisedge.com`.
- Upstream: `https://api.decionis.com` (confirmed from the active fleet registry).
- Gateway workspace: `124e5022-6eee-4717-ab65-a03899db6237`.
- The existing ingress-key handoff matches the active registry digest. Its value is stored only in ignored `.env`, mode 0600, as `AGENTSAFE_TENANT_KEY`.
- An authenticated `GET /v1/health` returned HTTP 200, `ok: true`, API revision `67be91f`, and `agentsafe-execution: PASSTHROUGH` at `2026-10-29T01:27:36.986Z`.
- The verified workspace API key is saved in ignored `.env`, mode 0600, as `DECIONIS_API_KEY`. Its scopes are `org:read`, `decision:run`, `decision:read`, and `policy:read`.
- Direct workspace authentication returned HTTP 200. An additional `POST /v1/auth/credential-context` through dci with both credentials returned HTTP 200, the expected workspace, and `agentsafe-execution: PASSTHROUGH` at `2026-10-29T01:45:11.527832Z` (02:45 Stockholm).
- These checks establish routing and authentication. SiteWork policy evaluation, signed inspection decisions, and enforcement are not yet validated.

The client now sends the ingress key only to its selected gateway. `POST /v1/auth/credential-context` independently verifies that an API key belongs to the configured workspace; missing keys, a different workspace, redirects and error responses do not pass. No automatic fallback sends a tenant key to another hostname.

Run `uv run --frozen python scripts/check_env.py --decionis-only` to repeat the connection checks. All Decionis checks pass. The full `make check` still needs Nebius and Tavily credentials.

## Temporary credential access

The user approved a temporary `Key Vault Secrets User` grant for `festus.j@decionis.com`, scoped only to `tenant-dci-decionis-api-key` in `agentsafe-kv-e0c2j8`. The key was read, its workspace identity verified, and its value saved locally without printing it. The exact temporary role assignment was then deleted; a subsequent Azure query confirmed it was absent. No other role assignment was removed.

The cleanup record and sanitized authentication evidence are retained under ignored `.local/setup/`. Neither contains the API key or ingress key.

## Original SiteWork hostname investigation

The requested endpoint is `https://sitework.decionisedge.com`. A public health request reaches the AgentSafe fleet over valid TLS and returns HTTP 421 with `HOST_NOT_SERVED` and `agentsafe-execution: NOT_FORWARDED`.

The originally signed-in Decionis workspace serves `https://clasp.decionisedge.com` in enforcement mode. After investigating another tenant in that workspace, the user authorized a separate signup under `festus@binariesfort.com` or use of dci. Signup reached email verification; the user then selected dci. No new workspace was created and Clasp was not modified.

## Confirmed constraint

The live authority reports revision `67be91f`. The corresponding full source revision is `67be91fb88cb2a6197f6921cd7473ccb49223f24`.

At that revision:

1. `apps/api/src/db/migrations/0209_WorkspaceGatewayDeployments.sql` makes gateway reservations unique by organization. No later migration in this revision removes that constraint.
2. `apps/api/src/db/repositories/WorkspaceGatewayDeploymentsRepo.ts` reads a single gateway by organization. Reservation conflicts do not create another gateway.
3. `infra/azure/agentsafe/provisioner/Provisioner.py` rejects another tenant bound to the same workspace with `WORKSPACE_ALREADY_DEPLOYED`.
4. `infra/azure/agentsafe/scripts/Tenant.py` also rejects reuse of a workspace already assigned to a tenant.

The published `@decionis/agentsafe` version 0.7.0 can route separate tenant labels, but that lower-level capability does not remove the hosted control plane's ownership and reservation checks. A DNS alias or manual registry edit would not constitute supported provisioning.

## If SiteWork must share Clasp's workspace later

- Permit multiple deployment records per organization while retaining globally unique tenant labels and organization-bound authorization.
- Address gateway operations by deployment ID plus organization. Update creation, activation, credential delivery, resource inventory, policy selection, enforcement changes and the workspace UI together; existing Clasp clients must retain their current deployment.
- Update the fleet's binding rules to support an explicitly authorized additional deployment under the same organization. Keep each gateway's ingress key, upstream credentials, ownership proof, reconciliation generation and runtime state separate.
- Verify concurrent creation, access from another workspace, key isolation, upstream-proof binding, and regression of the existing enforcing Clasp deployment before deploying the change.

No platform code, schema, fleet registry or deployed workload was changed. The temporary read grant described above was created and removed only after the user's explicit approval.

## SiteWork integration requirements

Use the published HTTP API and packages only. The desired authority base remains `https://api.decionis.com`, as specified in `IMPLEMENT.md`. Confirm the upstream and its ownership proof as part of actual provisioning.

Gateway admission uses `AgentSafe-Tenant-Key`. The Decionis workspace API key authenticates authority calls and is a different credential. Keep both in the ignored `.env` or an approved secret store. The P0 client now supplies the tenant header for gateway health checks.

A passing public authority health check is not proof of gateway activation or valid credentials. Treat HTTP 421, missing tenant credentials, and unsuccessful HTTP responses as blockers. Do not silently substitute another tenant's gateway.

Local screenshots of the Nebius request are under ignored `.local/setup/`. No credentials are stored in the tracked setup notes.
