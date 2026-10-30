# Cosmos GPU handoff

The batch implementation is in [scripts/cosmos](../cosmos/README.md). Its setup
guide covers Nebius AI Cloud first, AWS as fallback, the pinned Cosmos revision,
GPU requirements, upstream timing references, Hugging Face access and copying
results back. `run.py` in this directory forwards to that same implementation.

## Ready and pending

- **The US Nebius run is complete; the VM and disk are deleted.** Billing activation was verified on
  30 October (Europe/Stockholm). `sitework-cosmos` used `gpu-rtx6000`
  `1gpu-24vcpu-218gb` in `us-central1`, with a 200 GiB encrypted SSD.
  CUDA 13.0, PyTorch `2.9.1+cu130`, GPU computation and SSH were verified.
  The $1.79/hour compute ceiling, $10 total usage budget and three-hour guest
  shutdown timer were applied. All outputs were collected before deletion;
  the US project then showed zero standalone VMs and zero disks.
- The US AWS quota requests below remain a fallback, last observed
  `CASE_OPENED` with applied quotas zero. No AWS instance or Capacity Block was
  purchased.
- The [40 mm marker and worksheet](../../output/pdf/sitework-bench.pdf) and
  [bench checklist](../../docs/bench-rig.md) are ready. Printing, measuring the
  fixtures and recording measured clean clips remain physical tasks. Ten raw
  outdoor recordings are available, with no independent measurements.
- The [outdoor batch](../../docs/cosmos-outdoor-batch.md) produced **nine variants**.
  All 837 frames decode, local hashes match the VM, and every sample passed
  prompt and video guardrails. Total per-sample processing time was 453.2 s,
  excluding setup and model loading. Fine details also changed, so no measured
  truth or accuracy metric is inherited from these unmeasured source videos.
- [RUN_INFO.md](../../data/clips/RUN_INFO.md) contains the actual completion
  ledger and media checks. The private archive is in
  `.local/cosmos-20261029/collected/`; delivered videos are under `data/clips/`.
- The GPU did not host the web app. Replaying generated videos requires the
  separately running SiteWork app and its configured APIs, not this VM.

## US AWS quota requests

Submitted 29 October 2026 at 17:38 UTC in **`us-east-1`**. Applied quotas were
zero and neither quota had an existing request. Both are now `CASE_OPENED`, with
applied quotas still zero.

| Quota | Code | Requested vCPUs | Request ID | Support case |
|---|---|---|---|---|
| All G and VT Spot Instance Requests | `L-3819A6DF` | 16 | `e9fcdb377dc74ff58a29a3f3ee82b5f9zD19HmAt` | `179329553700701` |
| Running On-Demand G and VT instances | `L-DB2E81BA` | 16 | `5c1aff6682544d3ca453edff94c46f89pQtpyn40` | `179329553700779` |

EC2 confirms `g7e.4xlarge` is offered in this region: 16 vCPUs, 128 GiB host RAM
and one RTX PRO Server 6000 with 96 GiB VRAM. These requests do not launch an
instance or reserve capacity. Do not submit duplicate requests.

Rechecked 29 October at 18:49 UTC: both still `CASE_OPENED`, applied quotas 0.
Check again:

```bash
for id in e9fcdb377dc74ff58a29a3f3ee82b5f9zD19HmAt 5c1aff6682544d3ca453edff94c46f89pQtpyn40; do
  aws service-quotas get-requested-service-quota-change --request-id "$id" --region us-east-1 \
    --query 'RequestedQuota.{Quota:QuotaName,Value:DesiredValue,Status:Status,Case:CaseId}'
done
for code in L-3819A6DF L-DB2E81BA; do
  aws service-quotas get-service-quota --service-code ec2 --quota-code "$code" --region us-east-1 \
    --query 'Quota.{Quota:QuotaName,Applied:Value}'
done
```

## Historical Stockholm requests — do not launch in this region

Submitted 29 October 2026 at 03:20 Europe/Stockholm in **eu-north-1**. Last checked
04:01. Applied quota was zero for both before submission.

| Quota | Code | Requested vCPUs | Status | Support case |
|---|---|---|---|---|
| Running On-Demand P instances | `L-417A185B` | 16 | `CASE_OPENED` | `179324063100392` |
| All P Spot Instance Requests | `L-7212CCBC` | 16 | `CASE_OPENED` | `179324063000039` |

EC2 confirms `p5.4xlarge` is offered in this region: 16 vCPUs, one NVIDIA H100
with 81,920 MiB (80 GiB) VRAM, and support for On-Demand, Spot and Capacity Block
usage. The quota requests target one instance using either On-Demand or Spot.
Quota approval does not reserve capacity.

## Run after a GPU and clean clips are available

Follow the [setup and transfer instructions](../cosmos/README.md#run). Copy both
script directories if using this forwarding entry point; never copy `.env`.

For the prepared outdoor batch, copy `scripts/cosmos` and
`.local/cosmos-20261029` into `sitework/` on the VM, keeping that layout, and
run the batch's wrapper from there. It now records `--cloud nebius` and
`--instance "us-central1 gpu-rtx6000 1gpu-24vcpu-218gb"`, matching the actual VM.
Add `~/.local/bin` to the batch shell's `PATH` so `uvx` is available:

```bash
.local/cosmos-20261029/run-batch.sh --dry-run
.local/cosmos-20261029/run-batch.sh --conditions rain
.local/cosmos-20261029/run-batch.sh
```

The `rain` run is three jobs. Check its log and one output before paying for the
other six; the full run then resumes and skips them. `g7e` is a **Blackwell**
GPU: see [the Blackwell note](../cosmos/README.md#run) before setup.

On Nebius, set `--cloud nebius` and `--instance` to the platform and preset
actually provisioned. The distilled option uses 93 frames at 16 fps; capture
8–10 seconds so there is enough material. Review the trimmed segment against
its measured ground truth.

Rerun the same command on the same preserved disk after interruption. Keep
source clips, captions, settings and the Cosmos revision unchanged for a
resumed batch. For a new batch use new `--work` and `--output` directories.
Review every generated clip's geometry and marker before inheriting labels.
The runner records completion and timing; it does not validate construction
measurements or establish an expected verdict.

Copy the generated videos and `RUN_INFO.md` back as the setup guide describes.
If AWS actually runs Cosmos, the submission must identify AWS for that offline
generation. Live SiteWork inference still belongs on Nebius Token Factory.
