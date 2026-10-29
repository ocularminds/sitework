# Cosmos Transfer 2.5 run

No SiteWork Cosmos inference has run as of 29 October 2026. No generated weather
variants or measured GPU runtimes are available from this setup work.

The user selected the AWS fallback and requires US placement. The prepared
`g7e.4xlarge` plan is for `us-east-1`; G/VT On-Demand and Spot quota requests are
`CASE_OPENED`, but applied quotas remain zero. No GPU instance has launched.
The earlier Stockholm requests must not be used for this run.

The [outdoor batch](../../docs/cosmos-outdoor-batch.md) contains nine dry-run
specs for three unmeasured source segments, with rain, mud and dusk-glare
conditions. Each prepared input has 93 frames at 16 fps. Dry-run preparation
does not supply generated videos, measured GPU timings or accuracy metrics.

After real GPU execution of the [batch](../../scripts/cosmos_transfer/README.md), the
runner replaces this file with its ledger: actual cloud, instance, GPU, Cosmos
revision and per-variant status and timing. Review generated geometry and marker
visibility before copying any source ground-truth labels.
