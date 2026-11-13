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

## Explicit exclusions for the initial pilot

- Automated trading, order placement, portfolio custody, or private-key handling.
- Claims that a wallet belongs to a named person without reliable evidence.
- Guaranteed predictions, uncalibrated probabilities, or unsupported buy/sell signals.
- Unapproved historical backfills or continuous provider polling.
- Broad altcoin coverage before BTC/ETH data quality is validated.
- Social-media sentiment and news-based causal claims in the first vertical slice.

## Decision gates

Before accepting a provider integration, record:
1. Official terms, license, permitted use, and redistribution constraints.
2. API access and authentication requirements.
3. Price, rate limits, quotas, and historical coverage.
4. Data freshness, timestamp semantics, and revision policy.
5. Retention, deletion, and raw-payload rights.
6. Known gaps, attribution quality, and independent validation options.

A requirement becomes `IMPLEMENTED` only after code exists; it becomes `VERIFIED` only after recorded tests or other objective acceptance evidence pass.
