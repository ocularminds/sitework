# SiteWork policy (draft for Decionis)

**Status:** draft. These rules still have to be created in the Decionis workspace, by someone with policy write access; the SiteWork workspace key only has `policy:read`.

**This matters now.** On 29 Oct 2026 a SHADOW integration intent with no measurements, no citations and an error in its evidence came back **ALLOW** from the `dci` tenant, with `POLICY_MATCHED, POLICY_ACTION_AUTO_APPROVE`, dossier `e81018f7-2a9b-40ea-8e4f-6141afa91d1e`. Until this policy is active:
- SiteWork's own interlock still refuses to claim the grant for evidence that carries errors, so the light cannot turn green.
- The verdicts themselves are not yet the SiteWork rules.

SiteWork never decides. It sends evidence and deterministic measurement facts. Decionis applies the rules below and returns `ALLOW`, `BLOCK`, `ESCALATE` or `ERROR`, which SiteWork shows verbatim. On `ALLOW` with `should_execute`, SiteWork claims the single-use execution grant (`POST /v1/execution/consume-token`). The light turns green only when that claim is valid.

## Request SiteWork sends

The request is an [Agent-Safe Intent v1](https://github.com/decionis/agent-safe-pipeline/blob/master/spec/intent/v1/README.md) binding, sent to `POST https://dci.decionisedge.com/v1/authority/enforce-and-bind`.
- Headers: `AgentSafe-Tenant-Key` and `Authorization: Bearer <workspace key>`.
- The body is the binding plus `intent_hash` and `mode`.
- The code is in `sitework/gate/authority.py` and `sitework/gate/intent.py`.
- The hash reproduces every published conformance vector.

| Field | Value |
|---|---|
| `tenant_id` | the organization UUID (`DECIONIS_ORG_ID`) |
| `mode` | `ENFORCEMENT` (`DECIONIS_GATE_MODE=SHADOW` or `PARALLEL` to evaluate without effect) |
| `actor` | `{"id": "sitework-inspector", "type": "AI_AGENT", "runtime": "sitework"}` |
| `action.type` | `inspection.release_hold`, `trench.authorize_entry`, `work.cover_up` or `policy.update` |
| `action.resource` | `sitework/<scene>` |
| `action.parameters` | `{scene, condition, evidence_sha256}`, where `evidence_sha256` is the SHA-256 of the canonical evidence bundle |
| `context.idempotency_key` | a fresh UUID per inspection, set by SiteWork |
| `downstream_target` | `{"system": "sitework", "operation": <action.type>, "endpoint": "stack-light"}` |
| `expires_at` | `captured_at` + 120 s (`DECIONIS_INTENT_TTL_S`) |
| `policy_projection` | only when `DECIONIS_DECISION_TYPE` is set; otherwise Decionis evaluates `action.type` as the decision type |

`context.sitework` carries the full evidence bundle plus two derived blocks:

| Path | Meaning |
|---|---|
| `scene`, `condition` | `decking` / `trench` / `plumbing`; `clean` / `rain` / `mud` / `dusk_glare` / `outdoor` |
| `measurements[]` | `{kind, value, confidence, method}`, e.g. `angle_deg`, `gap_mm` (`gap_mm` appears twice: narrowest and widest point of any joint) |
| `citations[]` | `{jurisdiction, requirement, threshold, url, retrieved_at, content_sha256, source_domain}`. Only human-approved pack entries are included. |
| `errors[]` | Any failure: no frames, marker not found, model invalid after retry, missing key, no approved requirement |
| `frame_sha256[]`, `models` | Hashes of the exact JPEGs the model saw; role → exact model ID |
| `summary.citation_count` | Number of citations |
| `summary.error_count` | Number of errors |
| `summary.min_confidence` | Lowest measurement confidence, or `null` when there are no measurements |
| `summary.checks_outside` | How many measurement-vs-threshold checks fall outside their bounds |
| `summary.checks_total` | Number of checks performed |
| `summary.unchecked_kinds` | Measurement kinds with no cited threshold |
| `checks[]` | `{kind, value, min, max, within, confidence, source}` per measurement and cited threshold |

## Rules, in priority order

1. `summary.error_count > 0` → **ESCALATE**. Any missing input, model failure or missing citation needs a person.
2. `summary.citation_count == 0` → **ESCALATE**. No citation, no ALLOW. Rule 1 already covers this, because a missing citation is also an error; the rule is kept so that holds even if that changes.
3. `summary.measurement_count == 0` → **ESCALATE**.
4. `summary.min_confidence < floor[condition]` → **ESCALATE**. Proposed starting floors, to be tuned from `eval/results.md`:

   | condition | floor |
   |---|---|
   | clean | 0.70 |
   | outdoor | 0.75 |
   | rain | 0.85 |
   | mud | 0.85 |
   | dusk_glare | 0.85 |

5. `summary.checks_outside > 0` → **BLOCK**. A measurement is outside its cited requirement.
6. `summary.checks_total == 0` → **ESCALATE**. Nothing could be checked against a cited threshold.
7. Otherwise → **ALLOW**.

An ESCALATE is resolved only by a named human approver. P3 records that resolution in the SiteWork dossier record.

`policy.update` actions, proposed when Tavily Research finds an amendment or recall (P2), always **ESCALATE** for a named approver.
