# Live demo readiness — 30 October 2026

The user requested rejection of proposal `0a7c4022`, one named human release,
measured bench captures, and a real webcam test. The camera and human-release
checks used `p6-gaps` code at `3058306` and the local app at
`http://127.0.0.1:8000/`. After recording the proposal rejection, the app was
restarted to load the latest backend alongside its UI assets.

## Policy review

Proposal `0a7c4022-ccc7-4863-bc72-2df802402844` was rejected through the
dashboard's Policy review at **02:28:13 UTC / 03:28:13 Stockholm** under the
exact requested name, **Festus Jejelowo**. The API returned HTTP 200 and the
saved proposal reports `status: rejected` and `resolved_by: Festus Jejelowo`.

This was the earlier proposal whose enforced request failed with HTTP 403.
Rejecting it records the review; it does not create a Decionis verdict or apply
a policy change. The earlier rejection of `b07aff06` remains separate.

## Named human release

A fresh plumbing inspection used the real, unmeasured outdoor recording
`data/clips/outdoor/sw-rig05.mp4`, condition `outdoor`, and the US pack.
The request and response both report **ENFORCEMENT** through the real dci
gateway. Decionis returned **ESCALATE**, with no execution grant claimed or
finalized. The evidence retained the missing-marker errors and the absence of
approved plumbing thresholds.

- Dossier: `3cf72cca-08f1-4432-aecb-4eccd8c2b1b0`.
- Decision / approval request: `52e1c622-6983-4a17-94cc-dfb714e727ee`.
- Named release: **Festus Jejelowo**, **02:33:10 UTC / 03:33:10 Stockholm**.
- The dashboard changed to **Human release recorded**.
- An already connected stack-light page changed from amber **ESCALATE** to
  blue **RELEASED BY FESTUS JEJELOWO** over its live WebSocket connection.
- The original Decionis verdict remained **ESCALATE**.

The resolution note identifies this as a user-authorized pre-filming rehearsal
on uncalibrated footage, not certification of the work. The named resolution
is stored in SiteWork's local, unsigned record alongside the Decionis approval
request; it is not an added signature in the original Decionis dossier.

The original Decionis dossier passed offline signature and artifact-coverage
verification. Verification against the official published key also passed:
`trust: DECIONIS_OFFICIAL`, `issuer_authentic: true`. This verifies the gate's
original signed artifacts, not the separate human-resolution JSON.

## Real webcam

The **FaceTime HD Camera**, `camera:0`, passed both checks:

1. `CameraSource.sample(5)` returned five distinct **1920 × 1080** frames.
2. Selecting camera 0 through the dashboard opened the device, displayed
   **CAMERA FEED**, and rendered a **1920 × 1080** preview. Five further MJPEG
   frames from `/api/stream` decoded successfully with distinct hashes.

The first dashboard attempt failed because OpenCV tried to request macOS
camera access from a worker thread. Opening the same camera once on Python's
main thread succeeded; the dashboard retry then succeeded. No authorization
bypass or privacy-setting reset was used. A new macOS installation may need
camera permission before selecting the camera from the running app.

The camera was closed and the recorded source restored before the release
rehearsal. This validates camera capture and browser preview, not microphone
capture, physical measurement accuracy, or calibration of the seating detector.

## Bench captures still pending

The user requested preparation instructions and then confirmed they were still
preparing the physical stage.
The [marker worksheet](../output/pdf/sitework-bench.pdf) and
[capture matrix](bench-rig.md) were provided. Start with two parallel boards,
the checked 40 mm marker, and independently measured narrowest/widest gaps and
angle. Then prepare the model trench and unpressurized push-fit fixture.

There are no new clean-bench recordings or independent measurements from this
session. No clean labels or evaluation figures were added. Record and label
the real captures before running `scripts/eval.py` for the clean-bench column.

Private check reports and screenshots are retained under the ignored
`.local/live-readiness-20261030/` directory. The saved inspection and proposal
records remain under ignored `data/dossiers/` and `data/proposals/`.
