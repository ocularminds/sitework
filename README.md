# SiteWork

**Nothing gets covered until it's proven.**

Physical AI that inspects construction work at the hold point, before it disappears, and cannot release that hold without code-grounded evidence and a signed Decionis decision record.

> Models observe → code measures → policy decides → humans sign when the AI isn't sure → everything is provable.

Status: **P1, decking vertical slice.** Trench, plumbing, offline dossier verification and eval arrive in later phases (see `IMPLEMENT.md`).

## Setup

Requires [uv](https://docs.astral.sh/uv/) and Node 18+ (for `npx @decionis/verify`).

```bash
make setup               # installs Python 3.11 and dependencies into .venv
cp -n .env.example .env  # preserves an existing .env; then fill in missing keys
make check               # verifies Token Factory, Tavily and Decionis credentials
make test
make demo                # dashboard at http://127.0.0.1:8000, stack light at /light
```

`make check` lists the Nemotron models Token Factory serves to your key, runs one Tavily search, verifies the Decionis workspace identity, and checks the selected gateway. Anything it cannot verify is reported as a blocker; open items live in `TODO_HUMAN.md`.

SiteWork uses the `https://dci.decionisedge.com` gateway, explicitly selected on 29 October 2026. Its ingress key and workspace key are in the ignored `.env`. `uv run --frozen python scripts/check.py --decionis-only --gate` adds one SHADOW-mode intent through the gate; that call is recorded in the Decionis ledger. `docs/gateway-setup.md` covers the gateway setup.

## How a decking inspection runs

1. **Capture.** `SITEWORK_SOURCE` is a webcam index, or a clip to replay; three frames are sampled.
2. **Scale.** The printed ArUco `DICT_4X4_50` marker gives millimetres and a homography onto its plane. Keep the marker flat and close to the joint: one 40 mm marker extrapolates, about 1.4 % error at 250 mm in the synthetic tests.
3. **Perceive.** Nemotron VL on Token Factory returns board-edge endpoints as strict JSON. An invalid reply is retried once.
4. **Measure.** Code computes the narrowest and widest joint gap (mm) and the largest angle between adjacent boards (°). Confidence = model confidence × marker quality × agreement across frames.
5. **Ground.** Decisions read `data/packs/<jurisdiction>.json`, never the live web. `scripts/pack.py search` proposes clauses from allowlisted pages via Tavily search and extract. `scripts/pack.py approve` adds one only with a named approver and a threshold.
6. **Decide.** An [Agent-Safe Intent v1](https://github.com/decionis/agent-safe-pipeline/blob/master/spec/intent/v1/README.md) goes to `POST /v1/authority/enforce-and-bind` through dci. The verdict (`ALLOW`, `BLOCK`, `ESCALATE`, `ERROR`) is shown verbatim. The rules the policy should apply are drafted in `policies/sitework.md`.
7. **Act.** The light turns green only for `ALLOW` with `should_execute`, and only after SiteWork claims the single-use grant (`/v1/execution/consume-token`). SiteWork never claims a grant when its own evidence carries errors.
8. **Record.** Evidence, request, response and verdict are written to `data/dossiers/<dossier_id>.json`, with the execution token redacted.

Nothing is faked: errors (no marker, model failure, missing key, no approved requirement) are sent to Decionis as facts. `DECIONIS_MODE=mock` exists for tests only and puts a red MOCK GATE banner on every page.

## Bench and Cosmos preparation

Print the [40 mm ArUco marker and capture worksheet](output/pdf/sitework-bench.pdf)
at Actual Size / 100%. The [bench checklist](docs/bench-rig.md) covers board
angles, tabletop trench slopes, the unseated joint and outdoor captures.

The [Cosmos handoff](scripts/cosmos_transfer/README.md) links the resumable GPU
runner and records the AWS fallback quota requests. No SiteWork GPU run or
physical capture has been completed by this setup work.

## Environment

| Variable | Purpose |
|---|---|
| `NEBIUS_API_KEY`, `NEBIUS_BASE_URL` | Nebius Token Factory (OpenAI-compatible) |
| `NEBIUS_VLM_MODEL`, `NEBIUS_AGENT_MODEL`, `NEBIUS_AUDIO_MODEL` | Optional overrides of the model IDs recorded in `sitework/config.py` |
| `TAVILY_API_KEY` | Tavily search / extract / map / crawl / research |
| `DECIONIS_API_KEY`, `DECIONIS_ORG_ID` | Decionis credentials |
| `DECIONIS_POLICY_API_KEY` | Separate `policy:read` / `policy:write` key for authoring via `DECIONIS_API_BASE` |
| `AGENTSAFE_TENANT_KEY` | Ingress key for the selected AgentSafe tenant; distinct from the workspace API key |
| `DECIONIS_API_BASE`, `DECIONIS_GATEWAY_URL` | Decionis API and selected hosted AgentSafe gateway; no automatic switch to another tenant |
| `DECIONIS_MODE` | `live` (default). `mock` is for unit tests only |
| `DECIONIS_GATE_MODE` | `ENFORCEMENT` (default), `SHADOW` or `PARALLEL` |
| `DECIONIS_DECISION_TYPE` | Optional: sets the intent's `policy_projection.decision_type` |
| `SITEWORK_SOURCE` | Webcam index (default `0`) or a video file to replay |
| `SITEWORK_SAMPLES`, `SITEWORK_JURISDICTION`, `FIDUCIAL_MM` | Frames per inspection (3), pack to read (`US`), marker side in mm (40) |
| `COSMOS_REASON_URL` | Optional Cosmos Reason 2 endpoint (vLLM on Nebius AI Cloud) |

## Layout

```
sitework/   config, clients, perception, measurement, grounding, gate
scripts/    check.py (credentials), pack.py (jurisdiction packs), cosmos/ (Cosmos stress-test clips)
static/     dashboard (single page, no build step)
policies/   SiteWork policy draft for Decionis
eval/       labelled clips and results
data/       clips, jurisdiction packs, dossiers (large media git-ignored)
tests/      pytest suite
```

## License

Apache-2.0. See `LICENSE`.
