# IWFI Target Architecture (Proposed)

## 1. Architectural intent

Build a provider-independent, evidence-first research platform for BTC and ETH. Begin with the smallest vertical slice that can be validated. Do not create all modules or select infrastructure before the requirements and source constraints are understood.

This document is a proposal, not an implementation record.

## 2. Logical boundaries

```text
External providers
  |-- Blockchain / entity intelligence
  |-- Exchange flows and reserves
  |-- ETF issuer / fund flow disclosures
  |-- Spot market trades and order-book data
  |-- Derivatives and liquidations
          |
          v
Provider adapters
          |
          v
Immutable source observations
          |
          v
Validation and normalization
          |
          +----> Data quality and coverage
          |
          v
Metric and feature computation
          |
          v
Evidence correlation and hypothesis assessment
          |
          v
Research snapshots, comparisons, alerts (opt-in)
          |
          v
User interface / export
```

Cross-cutting concerns: provenance, UTC time handling, access control, secrets, audit logging, observability, reproducibility, provider terms, and retention controls.

## 3. Component responsibilities

### Provider adapters
Translate provider-specific responses into source observations. Each adapter documents endpoint, product tier, authentication, rate limits, coverage, timestamp semantics, attribution quality, terms, and failure modes. Adapters must not silently replace missing data with estimates.

### Source observation store
Preserve the provider payload or the maximum legally permitted source representation, together with provider, endpoint, asset, chain or market, source event time, retrieval time, schema version, content hash, and licensing/retention classification. If raw retention is prohibited, preserve a compliant normalized record and an explicit reason.

### Validation and normalization
Validate schema, units, asset identifiers, chain/network, direction, quantity, currency, timestamp, duplicate identity, and completeness. Invalid or ambiguous records are quarantined with machine-readable quality notes rather than silently discarded.

### Metric computation
Compute only metrics with documented formulas, units, windows, coverage requirements, and tests. Examples include exchange netflows, entity-attributed flows, spot CVD, ETF net flows, and derivatives positioning. Metric names must not imply more certainty than the underlying data supports.

### Evidence and hypothesis engine
Combine observations without conflating them. Store supporting evidence, counterevidence, alternative explanations, confidence limitations, and causality status. Wallet-to-entity attribution must carry provenance and validity intervals where available.

### Research snapshots
Persist each user-requested evaluation with its exact input window, source versions, data coverage, metric definitions, software version, and output. Re-running an evaluation must not overwrite its prior result.

### Presentation and alerts
Present evidence, uncertainty, missing coverage, and source timestamps. Alerts are opt-in and separately authorized; this baseline enables no background market analysis or polling.

## 4. Canonical data concepts

Initial conceptual entities:
- `Asset`: BTC or ETH, including chain/network identifiers.
- `Provider`: data supplier and terms metadata.
- `SourceObservation`: source-specific event or measurement.
- `Entity`: attributed organization, exchange, fund, custodian, or unknown party.
- `Address`: chain-specific public address, not presumed to identify a person.
- `Attribution`: evidence-backed relationship between an address and entity, including source and validity.
- `FlowEvent`: normalized movement with direction, quantity, asset, endpoints, and event time.
- `MarketObservation`: trade, quote, candle, order-book, or derivatives observation.
- `MetricDefinition` and `MetricValue`: formula/version and computed value.
- `EvidenceLink`: relationship between observations, metrics, and hypotheses.
- `ResearchRun`: user-requested evaluation and reproducibility metadata.
- `HypothesisAssessment`: conclusion, alternatives, counterevidence, and uncertainty.
- `DataQualityRecord`: validation result, coverage gap, or quarantine reason.

These are logical concepts only; no database schema has been selected.

## 5. Data contracts: minimum metadata

Every normalized observation should carry:
- stable internal identifier;
- provider and provider record identifier when available;
- asset and chain/market identifiers;
- event time in UTC and ingestion time in UTC;
- quantity and unit, with explicit precision;
- direction or measurement semantics;
- source endpoint/product and source version where available;
- attribution status: verified, provider-labelled, inferred, unknown, or disputed;
- quality status and explanatory notes;
- retention/licensing classification;
- source payload hash or equivalent integrity reference.

Do not convert a missing value to zero. Do not aggregate incompatible units, chains, venues, or time windows.

## 6. Market interpretation safeguards

- Exchange outflow is not proof of spot buying.
- Exchange inflow is not proof of a sale.
- ETF flow is not a complete view of all institutional exposure.
- A large transfer is not proof of a whale trade.
- Open interest does not identify position direction by itself.
- CVD describes aggressor-side executed volume under a provider's methodology; it does not identify the buyer as an institution.
- Wallet clustering and entity labels are probabilistic or provider-dependent unless independently verified.
- OTC activity, internal custody movements, omnibus wallets, and cross-chain bridges can create incomplete or misleading views.

The engine must report these caveats alongside any interpretation they materially affect.

## 7. Proposed implementation sequence

1. Requirements and provider due diligence.
2. One end-to-end, read-only BTC/ETH data slice using an approved source.
3. Normalization, provenance, and quality validation.
4. Reproducible metric calculation.
5. Evidence/hypothesis assessment.
6. Historical evaluation and error analysis.
7. Optional presentation and user-authorized alerts.

No language, framework, database, hosting service, or provider is mandated by this proposal.
