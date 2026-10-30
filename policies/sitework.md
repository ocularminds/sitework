# SiteWork policy (draft for Decionis)

**Status: active** in the dci workspace since 29 Oct 2026 as bundle `decionis-starter-v2+sitework-1` (artifact `c8cd1370-04db-4fb5-9582-fd0faf062d82`).
- The machine-readable rules are in [`sitework.json`](sitework.json). `scripts/policy.py` loads them with `DECIONIS_POLICY_API_KEY`: `plan`, `submit --yes`, `current`.
- Every non-SiteWork rule of the active bundle is kept verbatim. Only `sitework_*` rules are replaced.
- Before loading, the starter policy auto-approved a SiteWork intent with no evidence (dossier `e81018f7-…`). After loading, the same intent escalates (dossier `4f0ecb44-eccf-44dd-ba23-1af62b9df591`).

SiteWork never decides. It sends evidence and deterministic measurement facts. Decionis applies the rules below and returns `ALLOW`, `BLOCK`, `ESCALATE` or `ERROR`, which SiteWork shows verbatim. On `ALLOW` with `should_execute`, SiteWork claims the single-use execution grant (`POST /v1/execution/claim-token`) and reports the release `COMMITTED` (`POST /v1/execution/finalize-token`) inside the claim's lease. The light turns green only when both succeed.

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

## Facts the rules read

`context` also carries flat copies of the summary, because the rule grammar addresses `context.<key>`:

| Field | Meaning |
|---|---|
| `sitework_scene`, `sitework_condition` | Same as in the evidence |
| `sitework_error_count` | Number of errors |
| `sitework_citation_count` | Number of citations |
| `sitework_measurement_count` | Number of measurements |
| `sitework_min_confidence` | Lowest measurement confidence, or `null` |
| `sitework_checks_total` | Number of measurement-vs-threshold checks |
| `sitework_checks_outside` | Checks outside their bounds |

## Rules as loaded (higher priority wins)

All rules apply only when `decision_type` (= `action.type`) is a SiteWork action. Starter rules have priority 300 or less, so these outrank them for SiteWork actions and leave all other decision types as they were.

| Priority | Rule | Action |
|---|---|---|
| 460 | Release action, no errors, at least one citation, `checks_outside > 0` | **AUTO_REJECT** (BLOCK) |
| 450 | Release action, no errors, at least one citation, measurements present, `checks_total > 0`, `checks_outside == 0`, `min_confidence` ≥ the condition's floor (one rule per condition) | **AUTO_APPROVE** (ALLOW) |
| 400 | Any SiteWork action (including `policy.update`) not matched above | **ESCALATE** |

Release actions are `inspection.release_hold`, `trench.authorize_entry` and `work.cover_up`. `policy.update` always escalates.

Confidence floors, to be tuned from `eval/results.md`:

| Condition | Floor |
|---|---|
| clean | 0.70 |
| outdoor | 0.75 |
| rain | 0.85 |
| mud | 0.85 |
| dusk_glare | 0.85 |

These floors implement the intent of the original draft below: errors, a missing citation, no measurements, low confidence or nothing checkable all reach a person, never a default ALLOW.

## Original draft rules

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
