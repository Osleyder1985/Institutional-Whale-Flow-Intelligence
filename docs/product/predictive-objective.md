# IWFI Predictive Product Objective

Status: product objective approved by the project owner; detailed requirements tracked in GitHub Issue #23.

## Official objective

Institutional & Whale Flow Intelligence (IWFI) is a cryptocurrency predictive market-intelligence platform designed to estimate future price behavior from historical and current market evidence.

Its primary purpose is to generate auditable, probabilistic forecasts for a selected cryptoasset and horizon. Each forecast must estimate:

1. **Direction:** bullish, bearish, sideways, or undetermined.
2. **Magnitude:** expected absolute and relative price movement, represented as a range or distribution where supportable.
3. **Price objective:** target price and plausible predictive interval.
4. **Price zones:** probable support, resistance, reaction, and path zones, with method, evidence, and validity window.
5. **Time:** estimated time-to-target or time-to-zone, represented as an interval/distribution when estimable.
6. **Uncertainty:** calibrated scenario probabilities where evidence supports calibration, data coverage, limitations, and explicit abstention states.
7. **Rationale:** supporting evidence, counterevidence, alternative scenarios, and invalidation conditions.

A point estimate alone is insufficient. A forecast must communicate what is estimated, for which horizon, using information available at the forecast cutoff, and with what uncertainty.

## Initial product scope

- Pilot assets: native BTC on Bitcoin mainnet and native ETH on Ethereum mainnet.
- The logical architecture must permit future assets, but every asset/model/horizon combination requires independent data and out-of-sample validation.
- Market instruments and venues must be explicit. Spot, perpetual swaps, futures, index prices, and on-chain transfer measurements are distinct evidence types and must not be silently mixed.
- The product is research and decision support. It does not execute trades, custody funds, or guarantee investment outcomes.

## Evidence inputs

When authorized, available, and quality-checked, candidate evidence includes:

- spot prices, OHLCV, trades, volume, spreads, and order-book liquidity;
- derivatives positioning, open interest, funding, basis, and liquidations;
- on-chain transactions, transfer events, address activity, and network conditions;
- exchange flows/reserves and institutional or ETF disclosures;
- evidence-backed wallet/entity attribution and whale/institutional behavior;
- news, official announcements, event calendars, and macroeconomic context.

No single evidence family is presumed predictive. Incremental predictive value must be measured against baselines. A transfer is not a trade; exchange inflow/outflow does not prove a buy/sell; provider labels do not establish legal identity; temporal association does not establish causality.

## Forecast lifecycle

1. User explicitly requests an evaluation for an asset and horizon.
2. System freezes the as-of time and data cutoff.
3. Input quality, coverage, freshness, provenance, and licensing constraints are checked.
4. Versioned features and candidate models produce scenario estimates.
5. Forecast contract records estimates, intervals, uncertainty, evidence, alternatives, and limitations.
6. Immutable forecast snapshot is stored with model, feature, data, code, and protocol versions.
7. After the horizon expires, a separate outcome evaluation compares forecast with observed market path without mutating the original forecast.
8. Results feed a versioned evaluation report and future model research.

No background polling, scheduled forecasts, autonomous market analysis, or provider backfills are enabled by this objective.

## Scientific validation requirements

- Use chronological walk-forward and out-of-sample evaluation.
- Prevent look-ahead, target, survivorship, and preprocessing leakage.
- Compare candidates with simple, reproducible baselines before claiming predictive value.
- Evaluate direction, magnitude, predictive intervals, scenario probabilities, and time-to-target with metrics appropriate to each target.
- Report results by asset, horizon, regime, and test period, including sample sizes and uncertainty.
- Freeze acceptance thresholds and evaluation protocol before the final holdout test; do not invent performance targets in advance.
- Separate predictive performance from the profitability of any hypothetical trading strategy. Strategy evaluation must include fees, spread, slippage, funding, and execution constraints.
- If data quality or model calibration is inadequate, abstain or explicitly mark the output as unquantified/uncalibrated rather than fabricate precision.

## Architectural implications

IWFI must preserve clear boundaries between:

- source acquisition and licensing/retention controls;
- immutable source observations and canonical event resolution;
- market/flow metric computation;
- point-in-time feature generation;
- model training, calibration, inference, and registry;
- Forecast and ForecastOutcome contracts;
- temporal validation and model-performance monitoring;
- user interface and optional user-authorized notifications.

Forecasts are immutable research records. Re-evaluations create new linked records. Their input snapshots must preserve what was knowable at the time and remain compatible with offline-first synchronization.

## Delivery sequence

1. Complete evidence contracts, source due diligence, and authorization.
2. Establish reproducible, permission-compliant data access and persistence.
3. Define forecast targets, horizons, zones, and time-to-target semantics.
4. Build point-in-time feature datasets and simple baselines.
5. Implement walk-forward evaluation and leakage controls.
6. Compare candidate statistical and machine-learning models.
7. Introduce calibrated scenarios, uncertainty, abstention, and drift controls.
8. Build forecast presentation and outcome tracking after the predictive contract is stable.

Detailed functional and non-functional requirements, validation metrics, acceptance criteria, dependencies, and exclusions are tracked in [Issue #23](https://github.com/Osleyder1985/Institutional-Whale-Flow-Intelligence/issues/23).
