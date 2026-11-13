# IWFI Target Architecture (Proposed)

## 1. Architectural intent

Build a provider-independent, evidence-first research platform for BTC and ETH. Begin with the smallest vertical slice that can be validated. Do not create all modules or select infrastructure before the requirements and source constraints are understood.

This document is a proposal, not an implementation record.

**Product objective:** IWFI is a predictive market-intelligence platform. Its central output is an auditable Forecast that estimates future price direction, magnitude, target range, probable price zones, and time-to-target, together with uncertainty and supporting/counter evidence. Whale and institutional flows are candidate evidence inputs, not the product's final output and not automatically predictive.

## 2. Logical boundaries

```text
External providers
  |-- Blockchain / entity intelligence
  |-- Exchange flows and reserves
  |-- ETF issuer / fund flow disclosures
  |-- Spot market trades and order-book data
  |-- Derivatives and liquidations
  |-- News, official events and macro context
          |
          v
Provider adapters and permission controls
          |
          v
Immutable source observations
          |
          v
Validation, normalization and quality/coverage
          |
          v
Canonical events, metrics and point-in-time features
          |
          v
Forecast models / calibration / uncertainty
          |
          v
Forecast snapshots and later outcome evaluation
          |
          v
User interface / export / optional user-authorized alerts
```

Cross-cutting concerns: provenance, UTC time handling, access control, secrets, audit logging, observability, reproducibility, provider terms, retention controls, offline-first synchronization, and model/version governance.

## 3. Component responsibilities

### Provider adapters

Translate provider-specific responses into source observations. Each adapter documents endpoint, product tier, authentication, rate limits, coverage, timestamp semantics, attribution quality, terms, and failure modes. Adapters must not silently replace missing data with estimates.

### Source observation store

Preserve the provider payload or the maximum legally permitted source representation, together with provider, endpoint, asset, chain or market, source event time, retrieval time, schema version, content hash, and licensing/retention classification. If raw retention is prohibited, preserve a compliant normalized record and an explicit reason.

### Validation and normalization

Validate schema, units, asset identifiers, chain/network, direction, quantity, currency, timestamp, duplicate identity, and completeness. Invalid or ambiguous records are quarantined with machine-readable quality notes rather than silently discarded.

### Metric and feature computation

Compute only metrics and features with documented formulas, units, windows, availability time, coverage requirements, versions, and tests. Features used for a forecast must be point-in-time correct: only information available at the forecast cutoff may contribute.

### Evidence and hypothesis engine

Combine observations without conflating them. Store supporting evidence, counterevidence, alternative explanations, confidence limitations, and causality status. Wallet-to-entity attribution must carry provenance and validity intervals where available. Correlation must not be presented as causation.

### Predictive engine

Generate versioned, horizon-specific scenarios for direction, magnitude, price targets/ranges, probable price zones, and time-to-target. Outputs must include uncertainty, coverage, model/feature versions, supporting and contrary evidence, alternatives, and invalidation conditions. The engine must support abstention when data quality or model validity is insufficient.

### Forecast and outcome records

Persist each user-requested Forecast with its exact as-of time, data cutoff, input/feature snapshot references, source versions, model/calibrator versions, protocol, output distributions, and limitations. After the forecast horizon, store a separate ForecastOutcome with observed price path and evaluation metrics. Never overwrite the original forecast.

### Temporal validation and model governance

Use chronological walk-forward and out-of-sample evaluation, leakage controls, simple baselines, calibration checks, regime-specific reporting, and versioned acceptance protocols. No predictive performance claim is valid without reproducible test evidence.

### Research snapshots

Persist each user-requested evaluation with its exact input window, source versions, data coverage, metric definitions, software version, and output. Re-running an evaluation must not overwrite its prior result.

### Presentation and alerts

Present forecasts alongside evidence, uncertainty, missing coverage, source timestamps, and evaluation history. Alerts are opt-in and separately authorized; this baseline enables no background market analysis or polling.

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
- `FeatureDefinition` and `FeatureValue`: point-in-time feature formula/version and value.
- `ModelVersion`: model artifact, training window, parameters, code and environment references.
- `CalibrationVersion`: calibration method, training/calibration window and version.
- `Forecast`: immutable, horizon-specific predictive output and complete reproducibility metadata.
- `ForecastOutcome`: later observed path and independent evaluation of a Forecast.
- `EvidenceLink`: relationship between observations, metrics, features, and forecast rationale.
- `ResearchRun`: user-requested evaluation and reproducibility metadata.
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

Every Forecast should additionally carry:
- forecast ID, asset/instrument/venue, as-of time and data cutoff;
- target definition and horizon;
- model, feature, calibration, code, configuration and evaluation-protocol versions;
- direction probabilities only when calibrated, otherwise an explicit uncalibrated/unknown state;
- magnitude and price predictive intervals/distributions;
- target price/range and zone definitions with methods and validity;
- time-to-target estimate/interval or an explicit not-estimable state;
- data coverage, uncertainty, evidence, counterevidence, alternatives and invalidation conditions.

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
- Model explanations and feature contributions do not establish causality.
- A forecast is not an investment guarantee or an order instruction.

The engine must report these caveats alongside any interpretation they materially affect.

## 7. Predictive validation requirements

- Prevent look-ahead, target, survivorship, and preprocessing leakage.
- Use chronological walk-forward/out-of-sample evaluation; preserve a final holdout not used for model selection.
- Compare candidate models against simple reproducible baselines.
- Evaluate direction, magnitude, predictive intervals, scenario probabilities, and time-to-target with appropriate metrics.
- Report results by asset, horizon, regime, and test period, including sample sizes and uncertainty.
- Freeze acceptance thresholds and evaluation protocol before final holdout evaluation; do not invent performance targets.
- Separate predictive quality from the profitability of a hypothetical trading strategy. Any strategy test must include fees, spread, slippage, funding and execution constraints.
- Abstain or mark outputs uncalibrated/unquantified when data or validation is insufficient.

## 8. Proposed implementation sequence

1. Requirements and provider due diligence.
2. Canonical evidence contracts and integrity rules.
3. Authorized read-only BTC/ETH data slice.
4. Auditable persistence and reproducible snapshots.
5. Point-in-time metrics/features and forecast target definitions.
6. Baselines, leakage controls and walk-forward evaluation.
7. Candidate predictive models, calibration, uncertainty and abstention.
8. Forecast outcome tracking, drift monitoring and model governance.
9. User-facing presentation and separately authorized notifications.

No language, framework, database, hosting service, or provider is mandated by this proposal.

## 9. Versioned forecast contracts

The first versioned data contracts are maintained under `schemas/forecast/v1/`:

- `forecast.schema.json`: immutable prediction record, including direction, magnitude, targets, zones, time-to-target, uncertainty, evidence and provenance.
- `forecast-outcome.schema.json`: separate append-only observation/evaluation record.
- `examples/`: synthetic fixtures only; never treat them as market evidence or model results.
- `docs/contracts/forecast-v1-semantics.md`: cross-field, temporal, probability, interval, gap and censoring semantics that JSON Schema alone cannot enforce.

A JSON Schema pass is necessary but not sufficient. Runtime validation must enforce UTC timestamps, temporal cutoffs, ordered ranges, calibrated probability sums, estimability states, references and forecast/outcome consistency. These contracts do not imply that production persistence or inference has been implemented.

## 10. Product specification and roadmap

The official product objective is maintained in [Predictive Product Objective](../product/predictive-objective.md). Detailed functional, non-functional, validation, and acceptance requirements are tracked in [Issue #23](https://github.com/Osleyder1985/Institutional-Whale-Flow-Intelligence/issues/23). Forecast data contracts and their acceptance criteria are tracked in [Issue #25](https://github.com/Osleyder1985/Institutional-Whale-Flow-Intelligence/issues/25). The dependency-driven delivery sequence and current engineering work register remain in [the IWFI implementation roadmap](../roadmap/implementation-roadmap.md).

Target and horizon semantics are specified in [Target Definitions v1](../predictive/target-definitions-v1.md) and tracked in [Issue #27](https://github.com/Osleyder1985/Institutional-Whale-Flow-Intelligence/issues/27). The objective does not authorize provider access, polling, backfill, persistence, scheduled forecasts, or automatic market analysis.
