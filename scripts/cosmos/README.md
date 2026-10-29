# Cosmos Transfer 2.5 stress-test clips

Turns 3–5 clean bench clips into **rain**, **mud** and **dusk_glare** variants with NVIDIA Cosmos Transfer 2.5 on one rented GPU. These variants feed SiteWork's per-condition eval. The run is resumable per clip: if a preemptible VM is stopped, start it again and rerun the same command.

- **Primary:** a Nebius AI Cloud GPU VM (preemptible is fine).
- **Fallback:** an AWS GPU instance.

The scripts only assume Linux, an NVIDIA driver and Python 3, so they work the same on either cloud.

```
data/clips/clean/<clip>.mp4        you record these (optional <clip>.txt caption beside each)
data/clips/<condition>/<clip>.mp4  this script writes these, same <clip> name as the clean one
data/clips/RUN_INFO.md             which cloud, instance and GPU produced each variant, and how long it took
data/clips/.work/                  ledger, prepared clips, Cosmos specs, raw outputs and logs
```

Edge control guides generation toward each clean clip's geometry, but generated
board edges, trench slopes or marker modules can still change. Review the
geometry and marker in every variant before carrying over source labels. Record
changed or unmeasurable geometry explicitly. The generated videos have no audio;
keep original recordings for the plumbing audio evaluation.

The [current handoff](../cosmos_transfer/README.md) records the US-only GPU
requirement and AWS quota requests. A separate [outdoor batch](../../docs/cosmos-outdoor-batch.md)
is prepared from three unmeasured recordings. No SiteWork GPU inference has run yet.

## Requirements

From the Cosmos repo ([setup](https://github.com/nvidia-cosmos/cosmos-transfer2.5/blob/main/docs/setup.md), [inference](https://github.com/nvidia-cosmos/cosmos-transfer2.5/blob/main/docs/inference.md)):

| Item | Requirement |
|---|---|
| GPU | Ampere or newer, **65.4 GB VRAM on one GPU** for Cosmos-Transfer2.5-2B |
| Driver | NVIDIA ≥ 570.124.06 (CUDA 12.8.1) |
| OS | Linux x86-64, glibc ≥ 2.35 (Ubuntu ≥ 22.04) |
| Access | Hugging Face token with Read permission. Accept the NVIDIA Open Model License at [nvidia/Cosmos-Guardrail1](https://huggingface.co/nvidia/Cosmos-Guardrail1). Checkpoints download on first inference. |

Our own sizing, not from the Cosmos docs:
- Use a **≥ 200 GiB network boot disk**. It holds the checkpoints, the Python environment and the clips.
- Don't put the work directory on local SSD, because local SSD is wiped when a preemptible VM stops.

`setup.sh` checks the architecture, glibc, driver version and VRAM, and stops with a message if any is too low.

## Expected runtime

These figures are from Cosmos's [inference.md](https://github.com/nvidia-cosmos/cosmos-transfer2.5/blob/main/docs/inference.md): average diffusion time for the **edge** model on one GPU, per 93-frame chunk.

| GPU | Distilled edge (`--distilled`, 4 steps) | Base edge (35 steps) |
|---|---|---|
| H100 NVL | 64.5 s | 502.6 s |
| H200 NVL | 49.8 s | 374.4 s |
| RTX PRO 6000 Blackwell SE | 78.5 s | 605.7 s |
| B200 | 24.2 s | 179.7 s |

- The table excludes model loading and control-map computation.
- Nebius's `gpu-h100-sxm` is an SXM part, which the Cosmos table doesn't list.
- Actual per-variant wall time is recorded in `RUN_INFO.md` after the run. Use that figure, not this table, in the brief.

Cosmos keeps the input's frame rate and generates in 93-frame chunks, so `run.py` first re-encodes clips to 16 fps:
- **Base model:** a 10 s clip at 16 fps is 160 frames, which takes two chunks.
- **`--distilled`:** recommended for the hackathon. It cuts each clip to 93 frames (5.8 s at 16 fps) because the distilled model only supports one chunk. A batch of 5 clips × 3 conditions is then 15 single-chunk jobs.

## Before you start

1. **Record the clean clips:**
   - 3–5 clips, 6–10 s each.
   - Fixed camera, ArUco `DICT_4X4_50` marker in frame, work already in place (decking boards at a known angle, trench at a known slope).
   - Static scenes keep every frame valid against the clip's label.
   - Save them as `data/clips/clean/<clip>.mp4`, with unique names such as `deck15deg.mp4`.
   - Optionally add `data/clips/clean/<clip>.txt` with a one-sentence description of the scene. Otherwise the generic caption in `prompts.json` is used.
2. **Nebius AI Cloud:**
   - Activate billing.
   - Make sure the project has quota for one GPU of the platform you pick.
3. **AWS fallback:** the 16-vCPU G/VT On-Demand and Spot requests in `us-east-1` are filed. Check approval using the [handoff](../cosmos_transfer/README.md); do not submit duplicates. Earlier Stockholm requests are historical and must not be used under the US-only requirement.
4. **Hugging Face:**
   - Create a Read token.
   - Accept the license linked above.

## Provision: Nebius AI Cloud (primary)

Platforms with enough memory on one GPU ([VM types](https://docs.nebius.com/compute/virtual-machines/types)):

| Platform | GPU | 1-GPU preset | Regions |
|---|---|---|---|
| `gpu-h100-sxm` | H100 80 GB | `1gpu-16vcpu-200gb` | `eu-north1` |
| `gpu-h200-sxm` | H200 141 GB | `1gpu-16vcpu-200gb` | `eu-north1`, `eu-west1`, `us-central1` |
| `gpu-rtx6000` | RTX PRO 6000 96 GB | `1gpu-24vcpu-218gb` | `us-central1` (verified in console 29 October 2026) |

L40S (48 GB) is too small for this model.

**Console:**
1. Go to **Compute → Virtual machines → Create resource → Virtual machine**.
2. Choose **With GPUs**.
3. Set **VM type** to **Preemptible** and use a maximum-price policy. For the approved outdoor batch, the compute ceiling is **$1.79/hour** and the total usage budget is **$10**.
4. Select the **US `us-central1` project**, platform `gpu-rtx6000` and preset `1gpu-24vcpu-218gb`.
5. Boot disk: Ubuntu 24.04 GPU image available for that platform (the console currently offers CUDA 13), `network_ssd`, 200 GiB. `setup.sh` verifies the driver; its CUDA Python dependency set is selected with `COSMOS_CUDA_EXTRA`.
6. Add a public IP and the existing SSH public key. Use key-only SSH, a three-hour shutdown timer and provider-side deletion after outputs are collected.

The console's **View code → CLI** exports the exact command for the selected
US project, subnet, image and maximum-price policy. Save that configuration with
the run record before launch.

**On preemption:**
- Nebius sends SIGTERM 60 s before stopping the VM. `run.py` forwards it to Cosmos and doesn't count the cut-short jobs as failures.
- The VM is stopped, not deleted, and its volumes are kept.
- The dynamic public IP changes. Start the VM, reconnect at the new IP and rerun the same command.

## Provision: AWS (fallback)

| Instance | GPU | vCPU | Quota to raise (per region, counted in vCPUs) |
|---|---|---|---|
| `p5.4xlarge` | 1× H100 80 GB | 16 | Running On-Demand P instances `L-417A185B` (Spot: All P Spot Instance Requests `L-7212CCBC`) ≥ 16 |
| `g7e.2xlarge` | 1× RTX PRO 6000 Blackwell SE 96 GB | 8 | Running On-Demand G and VT instances `L-DB2E81BA` (Spot: All G and VT Spot Instance Requests `L-3819A6DF`) ≥ 8 |

- Both quotas default to 0 on new accounts ([EC2 instance type quotas](https://docs.aws.amazon.com/ec2/latest/instancetypes/ec2-instance-quotas.html)). Request the increase in **Service Quotas → Amazon EC2** in the region you will use. Check that region's availability first: AWS lists `p5.4xlarge` through EC2 Capacity Blocks in some regions.
- `g7e.2xlarge` has 64 GiB of host RAM. If model loading runs out of memory, move up a `g7e` size.
- AMI: Ubuntu 24.04 with an NVIDIA driver ≥ 570.124.06, e.g. AWS **Deep Learning Base OSS Nvidia Driver GPU AMI (Ubuntu 24.04)**. `setup.sh` verifies the driver.
- Storage: 200 GiB gp3 root volume.
- For Spot, set the interruption behaviour to **Stop** so the volume survives, and rerun after restart. Otherwise use On-Demand.

## Run

From your laptop, copy only the runner and the clean clips. Never copy `.env`:

```bash
VM=sitework@<vm-ip>
rsync -avR scripts/cosmos data/clips/clean "$VM:sitework/"
ssh "$VM"
```

On the VM:

```bash
bash sitework/scripts/cosmos/setup.sh
hf auth login                      # Read token; accept the license linked above
tmux new -s cosmos
cd sitework
python3 scripts/cosmos/run.py --cloud nebius --instance "us-central1 gpu-rtx6000 1gpu-24vcpu-218gb" --distilled --dry-run
python3 scripts/cosmos/run.py --cloud nebius --instance "us-central1 gpu-rtx6000 1gpu-24vcpu-218gb" --distilled
```

- On AWS, use `--cloud aws --instance p5.4xlarge`.
- `--dry-run` prepares the clips and specs and prints the Cosmos command without starting it.
- The real run loads the model once for every pending variant.
- Exit code 0 means every variant is done.
- Progress and logs are in `data/clips/.work/logs/`.

To resume after a preemption or a dropped SSH session, rerun the same command:
- Finished variants are kept.
- Partial ones are cleared and regenerated.
- A variant that fails twice is marked `failed`. Raise `--max-attempts` to retry it, and check the log first; for example, the Cosmos guardrail can reject an output.

Resume only with the same source clips, captions, settings and Cosmos revision.
The current ledger identifies work by clip name and condition, so it does not
detect changed inputs or a deleted/corrupted delivered video. Use a separate
`--work` and `--output` directory for a changed batch, keep a batch's work on the
same cloud, and check the delivered files before using them in evaluation.

## Copy results back

```bash
rsync -av "$VM:sitework/data/clips/" data/clips/ --exclude .work
```

This brings back `data/clips/{rain,mud,dusk_glare}/` and `RUN_INFO.md`. The videos are git-ignored; `RUN_INFO.md` is committed. Stop or delete the VM afterwards.

## Options

| Flag | Default | Purpose |
|---|---|---|
| `--distilled` | off | 4-step distilled edge model; cuts clips to 93 frames |
| `--conditions` | all in `prompts.json` | e.g. `--conditions rain` |
| `--fps` / `--max-frames` | 16 / 93 with `--distilled` | input normalisation |
| `--edge-weight` / `--edge-threshold` | 1.0 / medium | how tightly output follows the clean clip's edges |
| `--guidance` / `--seed` | 3 / 2025 | prompt adherence (0–7) and reproducibility |
| `--gpus` | 1 | more than 1 runs Cosmos under `torchrun` |
| `--cosmos` | `$COSMOS_DIR` or `~/cosmos-transfer2.5` | Cosmos checkout made by `setup.sh` |

## Notes

- The Cosmos Transfer 2.5 repo now points to Cosmos 3 and receives only limited maintenance. SiteWork stays on 2.5 because it is documented and stable enough for a 40-hour build. `setup.sh` pins commit `2ff49d0`.
- In the public `cosmos_transfer2/config.py`, the distilled edge checkpoint is registered only when `COSMOS_EXPERIMENTAL_CHECKPOINTS=1`. `run.py` sets this variable when `--distilled` is used; the Cosmos docs don't mention it.
- A completed sample is detected from Cosmos's own outputs: `<name>.txt` is written after `<name>.mp4`. Wall time is the gap between that file and `<name>.json`, which Cosmos writes when the sample starts.
