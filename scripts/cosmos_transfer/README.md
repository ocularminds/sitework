# Cosmos Transfer runner

`run.py` in this directory forwards to the batch implementation in [`scripts/cosmos`](../cosmos/README.md).
That guide covers:
- GPU requirements and provisioning on Nebius AI Cloud (primary) or AWS (fallback);
- setup, the pinned Cosmos revision and Hugging Face access;
- running the batch, resuming and copying results back.

What SiteWork has already generated, and how it is used, is in
[Cosmos stress inputs](../../docs/cosmos.md). Per-variant timings are in
[RUN_INFO.md](../../data/clips/RUN_INFO.md).

## Quick start on a GPU VM

Copy both script directories and your clean clips to the VM, keeping the repository layout. Never copy
`.env`.

```bash
VM=sitework@<vm-ip>
rsync -avR scripts/cosmos scripts/cosmos_transfer data/clips/clean "$VM:sitework/"
ssh "$VM"
```

On the VM (use `COSMOS_CUDA_EXTRA=cu130` on Blackwell GPUs and CUDA 13 images):

```bash
COSMOS_CUDA_EXTRA=cu130 bash sitework/scripts/cosmos/setup.sh
export PATH="$HOME/.local/bin:$PATH"
hf auth login
cd sitework
python3 scripts/cosmos_transfer/run.py --cloud nebius --instance "<platform> <preset>" --distilled --dry-run
python3 scripts/cosmos_transfer/run.py --cloud nebius --instance "<platform> <preset>" --distilled --conditions rain
python3 scripts/cosmos_transfer/run.py --cloud nebius --instance "<platform> <preset>" --distilled
```

- **Rain first.** Running one condition first lets you check an output before generating the rest;
  the full run then resumes and skips finished variants.
- **AWS.** Use `--cloud aws` and the instance you actually launched.
- **Labels.** Review every generated clip's geometry and marker before it inherits any label. The runner
  records completion and timing; it doesn't validate measurements or decide an expected verdict.
- **Clean-up.** Copy the videos and `RUN_INFO.md` back, then delete the VM and its disk.
