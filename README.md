# SiteWork

**Nothing gets covered until it's proven.**

Physical AI that inspects construction work at the hold point, before it disappears, and cannot release that hold without code-grounded evidence and a signed Decionis decision record.

> Models observe → code measures → policy decides → humans sign when the AI isn't sure → everything is provable.

Status: **P0 scaffold.** The pipeline, dashboard and eval arrive in later phases (see `IMPLEMENT.md`).

## Setup

Requires [uv](https://docs.astral.sh/uv/) and Node 18+ (for `npx @decionis/verify`).

```bash
make setup               # installs Python 3.11 and dependencies into .venv
cp -n .env.example .env  # preserves an existing .env; then fill in missing keys
make check               # verifies Token Factory, Tavily and Decionis credentials
make test
```

`make check` lists the Nemotron models Token Factory serves to your key, runs one Tavily search, verifies the Decionis workspace identity, and checks the selected gateway. Anything it cannot verify is reported as a blocker; open items live in `TODO_HUMAN.md`.

SiteWork currently uses `https://dci.decionisedge.com`, explicitly selected on 29 October 2026. Both its ingress key and workspace API key are configured locally in the ignored `.env`. Gateway health and workspace authentication pass, including an authenticated request through dci. SiteWork policy evaluation and enforcement remain work for later phases. Run only the connection checks with `uv run --frozen python scripts/check.py --decionis-only`. See `docs/gateway-setup.md` for the verified setup and limitations.

## Environment

| Variable | Purpose |
|---|---|
| `NEBIUS_API_KEY`, `NEBIUS_BASE_URL` | Nebius Token Factory (OpenAI-compatible) |
| `NEBIUS_VLM_MODEL`, `NEBIUS_AGENT_MODEL`, `NEBIUS_AUDIO_MODEL` | Optional overrides of the model IDs recorded in `sitework/config.py` |
| `TAVILY_API_KEY` | Tavily search / extract / map / crawl / research |
| `DECIONIS_API_KEY`, `DECIONIS_ORG_ID` | Decionis credentials |
| `AGENTSAFE_TENANT_KEY` | Ingress key for the selected AgentSafe tenant; distinct from the workspace API key |
| `DECIONIS_API_BASE`, `DECIONIS_GATEWAY_URL` | Decionis API and selected hosted AgentSafe gateway; no automatic switch to another tenant |
| `DECIONIS_MODE` | `live` (default). `mock` is for unit tests only |
| `COSMOS_REASON_URL` | Optional Cosmos Reason 2 endpoint (vLLM on Nebius AI Cloud) |

## Layout

```
sitework/   config, clients, perception, measurement, grounding, gate
scripts/    check.py (credentials), cosmos/ (Cosmos Transfer stress-test clips on a GPU VM)
static/     dashboard (single page, no build step)
policies/   SiteWork policies in Decionis format
eval/       labelled clips and results
data/       clips, jurisdiction packs, dossiers (large media git-ignored)
tests/      pytest suite
```

## License

Apache-2.0. See `LICENSE`.
