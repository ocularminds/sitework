# Cosmos outdoor batch — 29 October 2026

Status: **nine variants completed, collected and verified; the temporary Nebius
VM and managed disk were deleted after collection**. See the actual
[run ledger](../data/clips/RUN_INFO.md).

This batch uses three of the user's raw outdoor recordings. The user confirmed
that there are no independent measurements. The outputs can demonstrate weather
and lighting variation and support missing-evidence checks; they cannot establish
gap, angle, slope, depth or seating accuracy.

| Original | Selected interval | Visible subject | Generated variants |
|---|---|---|---|
| `sw-rig02.mp4` | 8–14 s | Roof/eaves, metal support brackets and guardrail | rain, mud, dusk_glare |
| `sw-rig05.mp4` | 0–6 s | Exterior vertical pipe beside a wall and window | rain, mud, dusk_glare |
| `sw-rig08.mp4` | 0–6 s | Exterior downpipe elbow beside a wall | rain, mud, dusk_glare |

The original files remain unchanged in `data/clips/outdoor/`. Their SHA-256 values
match [the outdoor intake](../eval/outdoor-intake.json). The staged six-second
segments and their hashes are recorded in the ignored local batch manifest at
`.local/cosmos-20261029/manifest.json`.

The runner prepared **nine specs**, using three portrait inputs at
**576 × 1024, 16 fps and 93 frames each**. All nine generated files have those
same dimensions, rate and frame count, with no audio.
It uses the distilled edge model, four steps, guidance 3, seed 2025, edge weight
1.0 and the medium edge threshold. Cosmos Transfer 2.5 is pinned to
`2ff49d0717af02057ae79bc75c00fbff9da1b4e7`.

[Outdoor prompts](../scripts/cosmos/prompts.outdoor.json) preserve the source
camera motion and request no invented components or markers. They replace the
bench-specific prompts, because these clips have no established calibration
marker or measured fixture. Generated geometry still requires visual review;
prompt instructions do not guarantee geometric preservation.

## Nebius GPU execution

Billing was activated on 30 October (Europe/Stockholm). The approved
`sitework-cosmos` VM was in **US `us-central1`**, with platform `gpu-rtx6000`
and preset `1gpu-24vcpu-218gb`: one RTX PRO 6000 Blackwell Server Edition
96 GB GPU, 24 vCPUs, 218 GiB host RAM and a 200 GiB encrypted SSD. It used
the Ubuntu 24.04 CUDA 13.0 image and was preemptible.

The attached pricing policy capped compute at **$1.79/GPU-hour**; the creation
form quoted another $0.02/hour for storage. The total usage budget was
**$10**. The verified guest shutdown timer was scheduled for **30 October 02:25:17 UTC**
(03:25:17 Stockholm); the VM was stopped and deleted before that deadline.
Provider-side cleanup was verified: **zero standalone VMs and zero disks** in
the US project. The private receipt records a $1.70 compute-plus-disk estimate
at the quoted maximum rates over the entire provisioning-to-cleanup interval,
including time stopped. This is not an invoice and excludes taxes.

Setup completed with CUDA 13.0, PyTorch `2.9.1+cu130`, NVIDIA driver
`580.173.02` and 97,887 MiB reported VRAM. A GPU matrix calculation passed.
SSH uses the existing key, the server host key was checked against serial logs,
and the guest firewall permits inbound SSH only from the current client IP.
The private resource receipt is `.local/setup/nebius-cosmos-resource.json`.

Hugging Face access to **Cosmos-Transfer2.5-2B**, **Cosmos-Predict2.5-2B** and
**Cosmos-Guardrail1** is granted under the approved NVIDIA license. Checkpoint
access was verified from the VM. Only the approved read token was transferred,
over SSH into a mode-0600 token file; SiteWork's full `.env` was not copied.
The source segment hashes match, and the VM's dry run produced nine valid specs
with 93 frames at 16 fps. The non-interactive batch adds `~/.local/bin` to `PATH`
so Cosmos can invoke its `uvx` checkpoint downloader.

The three rain jobs completed first; the six mud/glare jobs followed after
checking the rain output. Both batches exited successfully. All nine prompts
and generated videos passed Cosmos guardrails. Per-sample wall time totals
**453.2 seconds**, ranging from **48.7 to 57.0 seconds**, excluding setup,
checkpoint downloads and model loading.

The complete private archive contains 95 files (144.6 MiB): inputs, prepared
videos, raw outputs, control videos, logs and ledger. It is retained under
`.local/cosmos-20261029/collected/`. The nine delivered MP4s are in
`data/clips/{rain,mud,dusk_glare}/`; every local SHA-256 matches the VM.
All **837 frames** decode, and no calibration marker was detected. Frame samples
0, 46 and 92 were reviewed for each variant. The requested appearance changes
are visible, alongside changes to labels, textures and fine details; the mud
roof clip has a pink edge artifact at its start. No geometric truth is inherited.

No new rows have been added to `eval/labels.csv`, and no new evaluation metric is
claimed. These unmeasured sources cannot establish dimensional or seating
accuracy. The AWS requests remain a fallback; no AWS VM was launched.

The deleted GPU performed offline generation only. SiteWork's FastAPI app,
Token Factory calls and dci gateway are separate. Judges need a configured local
app or a separately hosted web app; retaining this GPU would not host the demo.
