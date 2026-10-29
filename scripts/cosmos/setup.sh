#!/usr/bin/env bash
# Bootstrap a GPU VM (Nebius AI Cloud or AWS) for Cosmos Transfer 2.5. Safe to re-run.
# Requirements come from the Cosmos repo's docs/setup.md and docs/inference.md.
set -euo pipefail

COSMOS_DIR="${COSMOS_DIR:-$HOME/cosmos-transfer2.5}"
COSMOS_REF="${COSMOS_REF:-2ff49d0717af02057ae79bc75c00fbff9da1b4e7}"  # main as of 2026-06-07
COSMOS_CUDA_EXTRA="${COSMOS_CUDA_EXTRA:-cu128}"                        # cu130 for CUDA 13 images
MIN_DRIVER="570.124.06"   # CUDA 12.8.1
MIN_VRAM_MIB=62400        # 65.4 GB for Cosmos-Transfer2.5-2B on one GPU

fail() { echo "setup: $*" >&2; exit 1; }
version_ge() { [ "$(printf '%s\n%s\n' "$1" "$2" | sort -V | head -1)" = "$2" ]; }

# 1. Host checks.
[ "$(uname -s)" = "Linux" ] && [ "$(uname -m)" = "x86_64" ] \
  || fail "Cosmos Transfer 2.5 targets Linux x86-64; this host is $(uname -sm)"
glibc="$(ldd --version | head -1 | grep -oE '[0-9]+\.[0-9]+$')"
version_ge "$glibc" 2.35 || fail "glibc $glibc < 2.35; use Ubuntu 22.04 or newer"
command -v nvidia-smi >/dev/null || fail "nvidia-smi not found; use a GPU image with NVIDIA drivers"
read -r driver vram name <<<"$(nvidia-smi --query-gpu=driver_version,memory.total,name \
  --format=csv,noheader,nounits | head -1 | tr -d ',')"
version_ge "$driver" "$MIN_DRIVER" || fail "NVIDIA driver $driver < $MIN_DRIVER (needed for CUDA 12.8.1)"
if [ "$vram" -lt "$MIN_VRAM_MIB" ] && [ -z "${COSMOS_SKIP_VRAM_CHECK:-}" ]; then
  fail "$name has $vram MiB; Cosmos-Transfer2.5-2B needs 65.4 GB on one GPU"
fi
echo "setup: $name, ${vram} MiB, driver $driver, glibc $glibc"

# 2. System packages (tmux keeps the run alive if SSH drops).
sudo apt-get update -q
sudo apt-get install -y -q git-lfs curl ffmpeg libx11-dev tree wget tmux
git lfs install

# 3. uv.
if ! command -v uv >/dev/null; then
  curl -LsSf https://astral.sh/uv/install.sh | sh
fi
export PATH="$HOME/.local/bin:$PATH"

# 4. Cosmos checkout pinned to a known commit, plus its environment.
if [ ! -d "$COSMOS_DIR/.git" ]; then
  git clone https://github.com/nvidia-cosmos/cosmos-transfer2.5.git "$COSMOS_DIR"
fi
cd "$COSMOS_DIR"
git fetch -q origin
git checkout -q "$COSMOS_REF"
git lfs pull
uv python install
uv sync --extra="$COSMOS_CUDA_EXTRA"

# 5. Hugging Face CLI. Checkpoints download on the first inference into $HF_HOME.
uv tool install -U "huggingface_hub[cli]"
if hf auth whoami >/dev/null 2>&1; then
  echo "setup: Hugging Face login found"
else
  echo "setup: next, run 'hf auth login' with a Read token and accept the NVIDIA Open Model"
  echo "       License at https://huggingface.co/nvidia/Cosmos-Guardrail1"
fi
echo "setup: Cosmos ready at $COSMOS_DIR ($(git rev-parse --short HEAD))"
