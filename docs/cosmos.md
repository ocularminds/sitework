# Cosmos stress inputs

SiteWork uses NVIDIA Cosmos Transfer 2.5 to turn real footage into rain, mud and dusk-glare
versions of the same scene. The question is whether bad weather makes SiteWork more careful or more
wrong. The policy sets a confidence floor per condition: 0.70 for clean, 0.75 for outdoor and 0.85
for rain, mud and dusk glare.

## The generated set

Three outdoor phone recordings, each trimmed to a six-second segment, were turned into nine variants.

| Source | Segment | Subject | Variants |
|---|---|---|---|
| `sw-rig02.mp4` | 8–14 s | Roof eaves, metal brackets and guardrail | rain, mud, dusk_glare |
| `sw-rig05.mp4` | 0–6 s | Exterior vertical pipe beside a wall | rain, mud, dusk_glare |
| `sw-rig08.mp4` | 0–6 s | Exterior downpipe elbow beside a wall | rain, mud, dusk_glare |

**Settings:**
- Cosmos-Transfer2.5-2B, distilled edge control.
- 4 steps, guidance 3, seed 2025, edge weight 1.0, medium edge threshold.
- Inputs at 576 × 1024, 16 fps, 93 frames.
- Cosmos pinned at `2ff49d0717af02057ae79bc75c00fbff9da1b4e7`.

The [outdoor prompts](../scripts/cosmos/prompts.outdoor.json) change only weather, surface and lighting.
They ask Cosmos to keep the camera motion and the visible structures, and to add no components or
markers.

**Hardware and output:**
- The batch ran on one NVIDIA RTX PRO 6000 Blackwell (96 GB) on Nebius AI Cloud in `us-central1`, with
  CUDA 13.0 and PyTorch `2.9.1+cu130`.
- Each sample took 48.7–57.0 s, 453.2 s in total. These times exclude setup, checkpoint downloads and
  model loading.
- Every output has 93 frames at 16 fps and no audio, and all 837 frames decode.
- All prompts and outputs passed the Cosmos guardrails.
- [`data/clips/RUN_INFO.md`](../data/clips/RUN_INFO.md) is the per-variant ledger. The videos are
  git-ignored.

## What the variants show, and what they don't

Frames 0, 46 and 92 of every variant were reviewed against the source:
- The requested weather and lighting are visible.
- Fine details also change: labels, textures and small parts.
- Rain is strongest on the roof clip.
- The mud roof clip has a pink edge artifact at its start.
- No variant shows a calibration marker.

So the variants are **stress inputs, not measured tests**. The source recordings have no independent
measurements, and generated geometry is not guaranteed to match its source, so no measurement or seating
truth is inherited.

## How they are used

The six pipe variants (`sw-rig05`, `sw-rig08`) are labelled as **input-refusal cases** in
[`eval/labels.csv`](../eval/labels.csv), each paired across US and SE. With no marker, no audio and a
qualitative plumbing pack, the correct outcome is ESCALATE. In the evaluation, all 12 weather rows
escalated and none was released ([results](../eval/results.md), [scope](../eval/README.md)). The roof
clip matches no hold-point scene and is not evaluated.

Measuring accuracy under these conditions needs Cosmos variants of measured bench clips. Review each
variant's geometry and marker before it inherits its source's labels.

## Reproduce or extend

The resumable runner and GPU setup are in [`scripts/cosmos`](../scripts/cosmos/README.md):
- It runs on a single GPU with at least 65.4 GB of VRAM.
- On Blackwell GPUs, run setup with `COSMOS_CUDA_EXTRA=cu130`, which needs driver 580.65.06 or newer.
- Run one condition first and check its output before the rest.
- The distilled checkpoint loads only with `COSMOS_EXPERIMENTAL_CHECKPOINTS=1`, which the runner sets.
