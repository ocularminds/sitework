# Cosmos Transfer 2.5 run

Written by `scripts/cosmos/run.py` from its ledger. Updated 2026-10-30T00:03:10Z.

| Setting | Value |
|---|---|
| Model | Cosmos-Transfer2.5-2B `edge/distilled` |
| Cosmos commit | `2ff49d0717af02057ae79bc75c00fbff9da1b4e7` |
| Control | edge, weight 1.0, threshold medium |
| Steps | 4 |
| Guidance / seed | 3 / 2025 |
| Input | 16 fps, max 93 frames |
| Prompts | `prompts.json` |

| Clip | Condition | Status | Frames | Seconds | Cloud | Instance | GPU | Finished (UTC) |
|---|---|---|---|---|---|---|---|---|
| sw-rig02-t08 | rain | done | 93 | 57.0 | nebius | us-central1 gpu-rtx6000 1gpu-24vcpu-218gb | NVIDIA RTX PRO 6000 Blackwell Server Edition 97887 MiB driver 580.173.02 | 2026-10-29T23:56:14Z |
| sw-rig02-t08 | mud | done | 93 | 54.2 | nebius | us-central1 gpu-rtx6000 1gpu-24vcpu-218gb | NVIDIA RTX PRO 6000 Blackwell Server Edition 97887 MiB driver 580.173.02 | 2026-10-30T00:03:10Z |
| sw-rig02-t08 | dusk_glare | done | 93 | 48.8 | nebius | us-central1 gpu-rtx6000 1gpu-24vcpu-218gb | NVIDIA RTX PRO 6000 Blackwell Server Edition 97887 MiB driver 580.173.02 | 2026-10-30T00:03:10Z |
| sw-rig05-t00 | rain | done | 93 | 48.8 | nebius | us-central1 gpu-rtx6000 1gpu-24vcpu-218gb | NVIDIA RTX PRO 6000 Blackwell Server Edition 97887 MiB driver 580.173.02 | 2026-10-29T23:56:14Z |
| sw-rig05-t00 | mud | done | 93 | 48.7 | nebius | us-central1 gpu-rtx6000 1gpu-24vcpu-218gb | NVIDIA RTX PRO 6000 Blackwell Server Edition 97887 MiB driver 580.173.02 | 2026-10-30T00:03:10Z |
| sw-rig05-t00 | dusk_glare | done | 93 | 48.8 | nebius | us-central1 gpu-rtx6000 1gpu-24vcpu-218gb | NVIDIA RTX PRO 6000 Blackwell Server Edition 97887 MiB driver 580.173.02 | 2026-10-30T00:03:10Z |
| sw-rig08-t00 | rain | done | 93 | 48.8 | nebius | us-central1 gpu-rtx6000 1gpu-24vcpu-218gb | NVIDIA RTX PRO 6000 Blackwell Server Edition 97887 MiB driver 580.173.02 | 2026-10-29T23:56:14Z |
| sw-rig08-t00 | mud | done | 93 | 49.2 | nebius | us-central1 gpu-rtx6000 1gpu-24vcpu-218gb | NVIDIA RTX PRO 6000 Blackwell Server Edition 97887 MiB driver 580.173.02 | 2026-10-30T00:03:10Z |
| sw-rig08-t00 | dusk_glare | done | 93 | 48.9 | nebius | us-central1 gpu-rtx6000 1gpu-24vcpu-218gb | NVIDIA RTX PRO 6000 Blackwell Server Edition 97887 MiB driver 580.173.02 | 2026-10-30T00:03:10Z |

## Scope and verification

Built on NVIDIA Cosmos. This run generated **nine visual stress variants from
three unmeasured outdoor source segments**. These are synthetic derivatives,
not nine independent physical recordings or calibrated bench tests.

All nine delivered files match the VM's SHA-256 hashes. Every file has one video
stream, **576 × 1024, 16 fps, 93 frames, 5.8125 seconds, no audio**. All **837
frames** decoded locally; no `DICT_4X4_50` calibration marker was detected.
Prompt and generated-video guardrails passed for every completed sample.

The recorded per-sample wall time totals **453.2 seconds (7 min 33.2 s)**,
with a range of **48.7–57.0 seconds**. It includes sample processing and guardrail
checks, but excludes environment setup, checkpoint downloads and model loading.
The table's Finished column is the ledger collection time for each sub-batch,
not the exact instant each video finished encoding.

Sampled frames 0, 46 and 92 were visually reviewed against the source for all
nine variants. The requested surface and lighting changes are visible, but
fine details, labels and textures also change. Rain is strongest in the roof
clip and subtler in the pipe clips. The mud roof clip has a pink edge artifact
at its start. These outputs do not justify inherited dimensional, slope,
seating or construction-compliance truth. No new evaluation metric is claimed.

Files: `data/clips/{rain,mud,dusk_glare}/{sw-rig02-t08,sw-rig05-t00,sw-rig08-t00}.mp4`.
The private batch archive, source hashes, raw outputs, logs and ledger are in
`.local/cosmos-20261029/collected/`; local media QA is in
`.local/cosmos-20261029/review/`. Videos and private receipts remain git-ignored.

## Resource cleanup and app runtime

The temporary US Nebius VM and its managed 200 GiB disk were deleted after
collection, as authorized. The project then showed **zero standalone VMs and
zero disks**. The compute price cap was $1.79/hour, with a $10 usage budget;
the three-hour shutdown safeguard was verified before running the batch.
Private provisioning and cleanup receipts are in `.local/setup/`.

This GPU performed offline video generation only. It did not host the SiteWork
web app. Replaying these files and running live inspections use the separate
SiteWork Python app, Nebius Token Factory and the dci gateway. A judge can run
`make demo` locally with configured credentials and input media; a public demo
URL needs a separate app host. The deleted GPU is not required for either path.
