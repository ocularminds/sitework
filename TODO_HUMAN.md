# SiteWork setup — P0

Updated 29 October 2026, Europe/Stockholm.

## AgentSafe gateway

- **Blocked:** `https://sitework.decionisedge.com/v1/health` returns HTTP 421, `HOST_NOT_SERVED`. DNS and TLS reach AgentSafe, but SiteWork is not provisioned.
- The currently open Decionis workspace already serves `clasp.decionisedge.com` in enforcement mode. The user explicitly asked to keep this workspace and investigate support for another tenant. Do not create another workspace or replace Clasp.
- The source matching the live Decionis API revision (`67be91fb88cb2a6197f6921cd7473ccb49223f24`) still permits only one gateway per workspace. Its database reservation and fleet provisioner both enforce this restriction. See `docs/gateway-setup.md` for the concrete implementation work required.
- Azure is signed in, but the current identity cannot list the fleet's Kubernetes ExternalSecrets. The local operator CLI also predates the additional enforcement vault and refuses its automatic vault discovery. No Azure permissions, secrets, registry entries, upstream proofs, or existing deployments were changed.
- A successful setup must issue a separate SiteWork ingress key, bind its approved upstream, and verify routing. The workload sends the ingress key in `AgentSafe-Tenant-Key`; this is separate from its Decionis workspace API key. Never reuse Clasp's ingress key.

## Nebius offers and credentials

- The official hackathon credit request was submitted for the signed-in Token Factory account with activation code `NEBIUS-DEVPOST-GLOBAL26`. Nebius confirmed: "Form submitted" and "The promo code will be emailed to you." Redeem the issued code in Token Factory's **Top up balance → With promo code** when it arrives. The activation code itself is not accepted there.
- An existing Nebius AI Builder Program application is already under review. Nebius's email says to expect an update within two business days. Do not submit a duplicate application.
- An existing AI Builder Program Compute Grants application is also awaiting review. Nebius acknowledged receipt; this is not an approved AI Cloud grant.
- The hackathon publishes $25 in Token Factory credit through the direct form and another $25 through the Builders Program. Its FAQ does not publish a separate AI Cloud credit grant. The compute-grant application is a separate reviewed program.
- `NEBIUS_API_KEY`, `TAVILY_API_KEY`, and SiteWork's Decionis credentials are not present in this repository's environment. Verify Token Factory's `/models` and the Tavily search after credentials are available. Exact model IDs remain unverified.

Sources: [hackathon resources](https://nebiusglobalaihackathon.devpost.com/resources), [hackathon FAQ](https://nebiusglobalaihackathon.devpost.com/details/faqs), [Builders Program](https://dev.nebius.com/builders).
