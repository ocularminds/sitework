# Connecting SiteWork to Decionis

SiteWork never decides a release itself. It proposes each one to Decionis as an
[Agent-Safe Intent v1](https://github.com/decionis/agent-safe-pipeline/blob/master/spec/intent/v1/README.md)
through a hosted AgentSafe gateway. Decionis returns `ALLOW`, `ESCALATE`, `BLOCK` or `ERROR`, with a
signed dossier. This guide covers the credentials, the checks to run and the errors you may see.

## Settings

Put these in `.env` (git-ignored); `.env.example` lists them.

| Variable | Purpose |
|---|---|
| `DECIONIS_GATEWAY_URL` | The hosted AgentSafe gateway for your workspace. Default `https://dci.decionisedge.com`. |
| `AGENTSAFE_TENANT_KEY` | Admits requests to that gateway, sent as `AgentSafe-Tenant-Key`. It is not the workspace API key. |
| `DECIONIS_ORG_ID` | Your workspace UUID; it becomes the intent's `tenant_id`. |
| `DECIONIS_API_KEY` | SHADOW evaluations, dossier retrieval and reading the workspace's mode limit (`org:read`, `decision:run`, `decision:read`, `policy:read`). |
| `DECIONIS_ENFORCE_API_KEY` | ENFORCEMENT and PARALLEL evaluations, plus claiming and finalizing execution grants (`decision:enforce`). |
| `DECIONIS_POLICY_API_KEY` | Loading SiteWork's rules (`policy:read`, `policy:write`), sent directly to `DECIONIS_API_BASE`. |
| `DECIONIS_API_BASE` | The Decionis API, `https://api.decionis.com`. |
| `DECIONIS_GATE_MODE` | `ENFORCEMENT` (default), `PARALLEL` or `SHADOW`. |

Keep runtime and authoring keys separate: a gateway runtime key is not allowed to hold `policy:write`.
If no enforcement key is set, SiteWork falls back to `DECIONIS_API_KEY`, but the readiness check still
requires a scope that the selected mode accepts.

## Check the connection

```bash
uv run --frozen python scripts/check.py --decionis-only
```

It checks, in order:
1. Gateway health through the configured gateway, with your tenant key.
2. That the API key belongs to `DECIONIS_ORG_ID` (`POST /v1/auth/credential-context`).
3. That the key's scopes allow the configured mode.
4. The workspace's `max_mode`. A SHADOW-only workspace is a blocker for ENFORCEMENT.

Add `--gate` to send one deliberately incomplete intent in the configured mode. It must come back
ESCALATE or BLOCK, and it never claims a grant. `--gate-mode SHADOW` tests SHADOW explicitly; a SHADOW
pass says nothing about enforcement.

## Load SiteWork's rules

SiteWork's rules are in [`policies/sitework.json`](../policies/sitework.json), and their rationale is
in [`policies/sitework.md`](../policies/sitework.md). Load them with the authoring key:

```bash
uv run --frozen python scripts/policy.py plan          # show the bundle that would be loaded
uv run --frozen python scripts/policy.py submit --yes  # load it
uv run --frozen python scripts/policy.py current       # show the active bundle
```

Every non-SiteWork rule in the active bundle is kept verbatim; only `sitework_*` rules are replaced.
Without SiteWork's rules, a workspace's starter policy can auto-approve an intent that has no evidence.

## Modes

| Mode | What happens |
|---|---|
| `SHADOW` | Decionis decides and signs a dossier, but nothing executes. SiteWork never claims a grant. The evaluation harness uses this mode. |
| `PARALLEL` | Decided alongside your existing process, with no effect. SiteWork never claims a grant. |
| `ENFORCEMENT` | The verdict governs the hold. On ALLOW, SiteWork claims the single-use grant and finalizes it before the light turns green. |

## Errors you may see

| Response | Meaning | What to do |
|---|---|---|
| 403 "API key missing required scope … `decision:enforce`" | The key cannot run the selected mode. | Set a `decision:enforce` key as `DECIONIS_ENFORCE_API_KEY`. |
| 403 `PROVISIONAL_WORKSPACE_SHADOW_ONLY` | The workspace is unclaimed and limited to SHADOW. | Claim the workspace in Decionis, then rerun the check. |
| 421 `HOST_NOT_SERVED` | That gateway hostname is not provisioned for a tenant. | Use the gateway URL issued for your workspace. |
| 400 `AUTHORITY_IDEMPOTENCY_KEY_MISMATCH` | An `Idempotency-Key` header was sent with the intent. | Don't send one. SiteWork puts the key only in `context.idempotency_key`. |
| 409 `CURRENT_STATE_UNRESOLVED` on a claim | An earlier claim on this target was never finalized, and its lease expired. | Reconcile the earlier claim in Decionis. SiteWork finalizes every claim inside its 30-second lease, so its own claims don't leave this behind. |

## What the client guarantees

- The tenant key goes only to the configured gateway. There is no automatic fallback to another
  hostname, tenant or mode.
- A missing credential never downgrades a request to SHADOW.
- A passing public health check is not proof that a gateway is active. HTTP 421, a missing tenant
  key and any unsuccessful response are reported as blockers.
- Execution tokens are redacted before a dossier record is written to disk.
