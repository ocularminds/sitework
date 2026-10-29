# Setup observations

29 October 2026, P0. These are observed setup results, not evaluation metrics.

| Service | What was tried | Observed result | Improvement to request |
| --- | --- | --- | --- |
| Decionis AgentSafe | Add SiteWork using the already open workspace | The current gateway is Clasp. The deployed API source keeps a unique gateway reservation per organization, and the fleet provisioner rejects a second tenant with `WORKSPACE_ALREADY_DEPLOYED`. | Support explicit selection and creation of multiple gateways in one workspace, preserving separate credentials and ownership proofs. |
| Decionis AgentSafe operator CLI | Read the live tenant list | The local CLI refused because it expected one vault in `agentsafe-rg` and found two. Kubernetes ExternalSecrets listing was denied to the current identity. | Update operator discovery for dedicated enforcement vaults and document the required read/provisioning roles. |
| Decionis AgentSafe dci fallback | Use the existing gateway after the user's explicit selection | The existing local ingress key matched the active registry. Authenticated health returned HTTP 200 and `PASSTHROUGH`. Actual decisions still need a workspace API key. | Make the distinction between ingress keys, workspace keys, health, and policy verification clear in onboarding. |
| Nebius Token Factory | Enter the public hackathon activation code in the billing promo-code field | Rejected as an invalid promo code. The official promotion form accepted the activation code and confirmed that it will email a separate redemption code. | Clearly distinguish activation codes from redeemable billing promo codes on the event resources page. |
| Nebius Builders Program | Inspect the existing application | Email confirms review is pending and an update is expected within two business days. | Display application and credit-issuance status in the account console. |
| Nebius AI Cloud | Inspect available hackathon offers, the existing compute-grant application, and billing | The hackathon FAQ has no separate published AI Cloud credit grant. A separate compute-grant application is awaiting review. Billing setup would charge $25 to activate; it was not submitted. | Show the expected grant-review timeline and whether hackathon GPU workloads qualify. |

Time lost has not been measured. No performance figures or model capability claims have been inferred from these observations.
