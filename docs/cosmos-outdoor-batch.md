# Cosmos outdoor batch — 29 October 2026

Status: **prepared; GPU inference has not run**.

This batch uses three of the user's raw outdoor recordings. The user confirmed
that there are no independent measurements. The outputs can demonstrate weather
and lighting variation and support missing-evidence checks; they cannot establish
gap, angle, slope, depth or seating accuracy.

| Original | Selected interval | Visible subject | Planned variants |
|---|---|---|---|
| `sw-rig02.mp4` | 8–14 s | Roof/eaves, metal support brackets and guardrail | rain, mud, dusk_glare |
| `sw-rig05.mp4` | 0–6 s | Exterior vertical pipe and drainage base | rain, mud, dusk_glare |
| `sw-rig08.mp4` | 0–6 s | Exterior downpipe elbow beside a wall | rain, mud, dusk_glare |

The original files remain unchanged in `data/clips/outdoor/`. Their SHA-256 values
match [the outdoor intake](../eval/outdoor-intake.json). The staged six-second
segments and their hashes are recorded in the ignored local batch manifest at
`.local/cosmos-20261029/manifest.json`.

The runner's dry run prepared **nine specs**, using three portrait inputs at
**576 × 1024, 16 fps and 93 frames each**. This is preparation, not a Cosmos result.
It uses the distilled edge model, four steps, guidance 3, seed 2025, edge weight
1.0 and the medium edge threshold. Cosmos Transfer 2.5 is pinned to
`2ff49d0717af02057ae79bc75c00fbff9da1b4e7`.

[Outdoor prompts](../scripts/cosmos/prompts.outdoor.json) preserve the source
camera motion and request no invented components or markers. They replace the
bench-specific prompts, because these clips have no established calibration
marker or measured fixture. Generated geometry still requires visual review;
prompt instructions do not guarantee geometric preservation. Generated clips
will contain no audio.

## GPU preparation

The user requires a **US GPU** and selected the **AWS fallback** after the
selected Nebius AI Cloud tenant still requested billing activation. The AWS
plan uses `g7e.4xlarge` in `us-east-1`, preferably `us-east-1c`: one RTX PRO Server
6000 with 96 GiB VRAM, 16 vCPUs, 128 GiB RAM and a 200 GiB encrypted gp3 disk.
The selected official Amazon image is `ami-05414055cdd6e338f`, Deep Learning
Base OSS Nvidia Driver GPU AMI (Ubuntu 24.04), dated 27 October 2026.

The latest Spot price returned for `us-east-1c` was **$1.3719/hour**, below the
approved **$1.79/hour compute ceiling**. The usage budget remains **$10**, with
a three-hour guest shutdown timer and VM/disk cleanup after output collection.
The AWS plan is saved locally at `.local/cosmos-20261029/aws-launch-plan.json`.
A guest shutdown timer is a safeguard; provider-side cleanup must still be
confirmed.

**Launch is blocked by quota.** The US G/VT On-Demand and Spot quotas remain
zero; both 16-vCPU requests are `CASE_OPENED`. See [the quota handoff](../scripts/cosmos_transfer/README.md).
No AWS or Nebius GPU VM has been created. Quota approval and available capacity
must be checked before launch, and a changed Spot price must remain within the
approved ceiling.

Hugging Face account `decionis` has accepted the NVIDIA Open Model License for
Cosmos-Guardrail1. The approved fine-grained token has read access to public
gated repositories; it is stored only in ignored `.env` with mode 0600. Token
authentication and a gated file access check returned HTTP 200.

Only the runner, staged inputs, prompts and manifest go to the VM. Copy the
approved Hugging Face token separately through SSH; never copy SiteWork's entire
`.env`. Run `.local/cosmos-20261029/run-batch.sh` on the VM after setup. The local
manifest records `prepared_awaiting_aws_quota` until real inference starts.
Collect the generated videos, ledger, logs and `RUN_INFO.md` before
deleting the VM and disk.

No new rows have been added to `eval/labels.csv` for these planned outputs. Label
only files that actually exist, with measurement and seating truth left blank.
