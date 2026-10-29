# Cosmos GPU handoff

The batch implementation is in [scripts/cosmos](../cosmos/README.md). Its setup
guide covers Nebius AI Cloud first, AWS as fallback, the pinned Cosmos revision,
GPU requirements, upstream timing references, Hugging Face access and copying
results back. `run.py` in this directory forwards to that same implementation.

## Ready and pending

- **All GPU creation must be in the US**, as the user requested. The user
  selected the **AWS fallback**. The prepared plan uses `g7e.4xlarge` in
  `us-east-1c`; the latest Spot price returned was $1.3719/hour. Keep the
  $1.79/hour compute ceiling and $10 total usage budget, with cleanup after
  output collection.
- The US AWS quota requests below are `CASE_OPENED`; the applied quotas are
  still zero. Approval and capacity are required before launch. No GPU instance
  or Capacity Block was purchased. The Nebius VM form was not submitted.
- The [40 mm marker and worksheet](../../output/pdf/sitework-bench.pdf) and
  [bench checklist](../../docs/bench-rig.md) are ready. Printing, measuring the
  fixtures and recording measured clean clips remain physical tasks. Ten raw
  outdoor recordings are available, with no independent measurements.
- The [outdoor batch](../../docs/cosmos-outdoor-batch.md) is prepared with nine
  dry-run specs. Hugging Face gated-model access and its approved read token are
  ready. No actual Cosmos output or new accuracy metric exists yet.
- Cosmos inference has not run. [RUN_INFO.md](../../data/clips/RUN_INFO.md)
  currently records that fact; the runner replaces it with its actual ledger.

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

For the prepared outdoor batch on the planned `g7e.4xlarge`, copy `scripts/cosmos`
and `.local/cosmos-20261029` into `sitework/` on the VM, keeping that layout, and
run the batch's wrapper from there. Its `--cloud aws --instance "us-east-1 g7e.4xlarge"`
must match the instance actually launched:

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
