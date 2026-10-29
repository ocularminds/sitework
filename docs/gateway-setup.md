# SiteWork gateway setup investigation

Status on 29 October 2026: **not provisioned**. SiteWork remains in P0.

The requested endpoint is `https://sitework.decionisedge.com`. A public health request reaches the AgentSafe fleet over valid TLS and returns HTTP 421 with `HOST_NOT_SERVED` and `agentsafe-execution: NOT_FORWARDED`.

The signed-in Decionis workspace currently serves `https://clasp.decionisedge.com` in enforcement mode. The user chose to retain that workspace and investigate a second tenant. Its existing gateway was not modified.

## Confirmed constraint

The live authority reports revision `67be91f`. The corresponding full source revision is `67be91fb88cb2a6197f6921cd7473ccb49223f24`.

At that revision:

1. `apps/api/src/db/migrations/0209_WorkspaceGatewayDeployments.sql` makes gateway reservations unique by organization. No later migration in this revision removes that constraint.
2. `apps/api/src/db/repositories/WorkspaceGatewayDeploymentsRepo.ts` reads a single gateway by organization. Reservation conflicts do not create another gateway.
3. `infra/azure/agentsafe/provisioner/Provisioner.py` rejects another tenant bound to the same workspace with `WORKSPACE_ALREADY_DEPLOYED`.
4. `infra/azure/agentsafe/scripts/Tenant.py` also rejects reuse of a workspace already assigned to a tenant.

The published `@decionis/agentsafe` version 0.7.0 can route separate tenant labels, but that lower-level capability does not remove the hosted control plane's ownership and reservation checks. A DNS alias or manual registry edit would not constitute supported provisioning.

## Work needed to support this request

- Permit multiple deployment records per organization while retaining globally unique tenant labels and organization-bound authorization.
- Address gateway operations by deployment ID plus organization. Update creation, activation, credential delivery, resource inventory, policy selection, enforcement changes and the workspace UI together; existing Clasp clients must retain their current deployment.
- Update the fleet's binding rules to support an explicitly authorized additional deployment under the same organization. Keep each gateway's ingress key, upstream credentials, ownership proof, reconciliation generation and runtime state separate.
- Verify concurrent creation, access from another workspace, key isolation, upstream-proof binding, and regression of the existing enforcing Clasp deployment before deploying the change.

No platform code, schema, IAM permissions, fleet registry or deployed resources were changed during this investigation.

## SiteWork integration requirements

Use the published HTTP API and packages only. The desired authority base remains `https://api.decionis.com`, as specified in `IMPLEMENT.md`. Confirm the upstream and its ownership proof as part of actual provisioning.

Gateway admission uses `AgentSafe-Tenant-Key`. The Decionis workspace API key authenticates authority calls and is a different credential. Keep both in the ignored `.env` or an approved secret store. The existing P0 client needs the tenant header wired in before it can validate an activated gateway.

A passing public authority health check is not proof of gateway activation or valid credentials. Treat HTTP 421, missing tenant credentials, and unsuccessful HTTP responses as blockers. Do not silently substitute another tenant's gateway.

Local screenshots of the Nebius request are under ignored `.local/setup/`. No credentials are stored in the tracked setup notes.
