# Zero-Cost Adapter Runtime Policy

Status: contract implementation for Issue #61. This policy is a guardrail, not approval to activate any provider.

## Required source policy

Every adapter must carry a versioned policy conforming to `schemas/source-cost-policy.schema.json`:

- `cost_model=ZERO_EXTERNAL_COST`
- A documented recurring quota with a positive limit and explicit period.
- `billing_risk=NONE`
- `payment_method_required=false`
- `paid_fallback_enabled=false`
- Official HTTPS terms URL and UTC review timestamp.
- `zero_cost_eligible=true` only after all evidence is verified.

Unknown or missing cost, quota, billing, or terms evidence is a denial, not an implicit approval. This contract intentionally does not model unlimited quota: an unlimited entitlement must not be assumed from silence.

## Request gate

Call `authorize_source_request(policy, quota_state, remaining_requests)` before opening a network connection or invoking an HTTP client.

- `AVAILABLE` with a positive integer remaining request count may pass.
- `EXHAUSTED`, `UNKNOWN`, missing quota state, zero remaining requests, and invalid counts block.
- A blocked decision must stop the adapter. It must not retry through another paid endpoint, purchase credits, change plans, or use a billing-enabled fallback.

The guard is deterministic and side-effect free. It does not itself perform HTTP requests, track quota counters, store secrets, verify legal terms, or prove provider accuracy. The caller remains responsible for obtaining and maintaining truthful policy evidence and an authoritative quota count.

## Separation of approvals

Passing this guard establishes only that the supplied configuration satisfies the structural zero-cost policy. It does not approve:
- the legal right to access, store, retain, or redistribute source data;
- a provider's account-specific entitlement;
- continuous polling or historical backfill;
- participant identity or attribution;
- data quality, completeness, or market interpretation.

Those decisions remain subject to Issue #3 and the relevant data-governance requirements.

## Safe failure

Any exception, missing field, unknown state, or invalid value must be treated as a denial before transport. Do not log credentials or payment details. The CI suite tests both positive and negative paths.
