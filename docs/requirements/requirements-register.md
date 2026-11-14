# IWFI Initial Requirements Register

Status values: `PROPOSED`, `PENDING_EVIDENCE`, `ACCEPTED`, `REJECTED`, `IMPLEMENTED`, `VERIFIED`. No requirement in this initial register is represented as implemented.

| ID | Requirement | Initial acceptance evidence | Priority | Status |
|---|---|---|---|---|
| FR-001 | Support BTC and ETH as pilot assets | Asset identifiers and test fixtures cover both assets and relevant networks | P0 | PROPOSED |
| FR-002 | Ingest source observations through isolated provider adapters | Contract tests prove provider payloads map to normalized records | P0 | PROPOSED |
| FR-003 | Preserve source provenance and UTC event/ingestion timestamps | Persisted records can be traced to provider and source event | P0 | PROPOSED |
| FR-004 | Distinguish verified entity attribution from labels and inference | Attribution status and provenance are mandatory where identity is presented | P0 | PROPOSED |
| FR-005 | Measure exchange flows without treating them as executed trades | Metric definition and tests document limitations | P0 | PROPOSED |
| FR-006 | Record ETF/fund flows with fund, reporting period, publication time, and source | Reconciliation against source disclosures | P1 | PROPOSED |
| FR-007 | Calculate spot aggressor-side volume delta where source data supports it | Formula, trade-side semantics, unit tests, and sample reconciliation | P1 | PROPOSED |
| FR-008 | Capture derivatives metrics separately from spot metrics | Instrument, venue, contract, unit, and timestamp are explicit | P1 | PROPOSED |
| FR-009 | Assess accumulation/distribution hypotheses with counterevidence | Assessment includes evidence, alternatives, coverage, and uncertainty | P0 | PROPOSED |
| FR-010 | Persist immutable research-run history | Re-run creates a new version and preserves prior result | P0 | PROPOSED |
| FR-011 | Expose data coverage, gaps, stale data, and quality warnings | Incomplete fixture produces explicit partial/undetermined result | P0 | PROPOSED |
| FR-012 | Run market evaluations only on explicit user request | No scheduled analysis is active by default; tests verify invocation path | P0 | PROPOSED |
| FR-013 | Keep alerts and background polling disabled until separately authorized | Configuration defaults off and authorization is auditable | P0 | PROPOSED |
| FR-014 | Support export of an evidence-backed research snapshot | Export contains provenance, metric versions, caveats, and timestamps | P2 | PROPOSED |

## Non-functional requirements

| ID | Requirement | Acceptance evidence | Priority | Status |
|---|---|---|---|---|
| NFR-001 | Reproducibility | Same immutable inputs, definitions, and software version reproduce equivalent outputs | P0 | PROPOSED |
| NFR-002 | Data integrity | Hashes or equivalent integrity controls detect source-record alteration | P0 | PROPOSED |
| NFR-003 | Security | Secrets are not committed; least-privilege access and rotation are documented | P0 | PROPOSED |
| NFR-004 | Resilience | Provider errors, rate limits, partial responses, and schema changes are observable | P0 | PROPOSED |
| NFR-005 | Maintainability | Provider adapters and metric definitions are independently testable | P1 | PROPOSED |
| NFR-006 | Auditability | Every conclusion links to its inputs, formulas, versions, and decision history | P0 | PROPOSED |
| NFR-007 | Compliance | Collection and retention respect source terms, licenses, and applicable law | P0 | PROPOSED |
| NFR-008 | Performance | Targets are defined only after expected workload and source limits are measured | P2 | PENDING_EVIDENCE |

## Scope interpretation: product coverage vs first vertical slice

The product scope is governed by [Issue #23](https://github.com/Osleyder1985/Institutional-Whale-Flow-Intelligence/issues/23) and the signal-family specifications in [Issues #31–#37](https://github.com/Osleyder1985/Institutional-Whale-Flow-Intelligence/issues/31). These define research candidates across spot/microstructure, derivatives, on-chain/institutional flows, news/events/macro, technical structure/regimes, and social sentiment/attention/positioning.

Being in the product's research catalog does **not** mean a signal belongs in the first implementation slice, is approved for collection, or has predictive value. Execution order is governed by dependency readiness, provider diligence (#3), point-in-time data requirements (#29), and experimental evidence (#36).

The first vertical slice remains deliberately narrower: provider-neutral observation/evidence contracts, BTC/ETH identifiers, provenance and attribution semantics, data-quality handling, and deterministic tests. News and social signals remain in the broader product research scope but are deferred from that first vertical slice until their source access, historical availability, knowledge-time semantics, licensing, and incremental value can be evaluated. News/event observations may later be evaluated as timestamped candidate inputs; they must not be described as causal drivers without separate evidence.

## Explicit exclusions and safeguards for the first vertical slice

- Automated trading, order placement, portfolio custody, or private-key handling.
- Claims that a wallet belongs to a named person without reliable evidence.
- Guaranteed predictions, uncalibrated probabilities, or unsupported buy/sell signals.
- Unapproved historical backfills or continuous provider polling.
- Broad altcoin coverage before BTC/ETH data quality is validated.
- Production ingestion of news/social feeds or news-based causal claims in the first vertical slice. This is a sequencing exclusion, not a permanent exclusion from the product's research scope.

## Decision gates

Before accepting a provider integration, record:
1. Official terms, license, permitted use, and redistribution constraints.
2. API access and authentication requirements.
3. Price, rate limits, quotas, and historical coverage.
4. Data freshness, timestamp semantics, and revision policy.
5. Retention, deletion, and raw-payload rights.
6. Known gaps, attribution quality, and independent validation options.

A requirement becomes `IMPLEMENTED` only after code exists; it becomes `VERIFIED` only after recorded tests or other objective acceptance evidence pass.

## Change log

- 2026-11-13 — Clarified the distinction between overall product research coverage and the narrower first vertical slice. News and social remain candidate families under Issues #34 and #37; they are deferred from first-slice production ingestion, not permanently excluded. No source approval or collection authorization is implied.
