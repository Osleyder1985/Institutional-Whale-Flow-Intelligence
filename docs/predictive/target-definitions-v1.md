# IWFI Target Definitions v1 — Proposed Protocol

Status: protocol specification for Issue #27. This document separates invariant definitions from parameters that remain unselected pending data-quality and validation evidence. It does not declare production horizons, model performance, or predictive thresholds.

## 1. Forecast unit and market identity

A target is defined for one asset, one network identity where applicable, one market type, one instrument, one venue/reference market, one quote currency, one observation resolution, and one forecast horizon.

A target definition is versioned. Its version must identify the anchor policy, observation resolution, horizon, label rules, sideways-band parameterization, price-target construction, zone algorithm, and event-time semantics. Results from different target versions are not directly pooled without a documented compatibility study.

Pilot assets are native BTC and native ETH. Spot, perpetual, futures, index, and on-chain measurements remain distinct instruments/evidence types.

## 2. Point-in-time anchor

The anchor price P0 is the reference price available at the forecast as-of instant under a declared market-data policy.

The selected anchor policy must specify:
- instrument, venue, quote currency, and price source;
- observation type (completed candle close, eligible last trade, or another explicit measure);
- observation resolution and aggregation rules;
- event timestamp and knowledge/availability timestamp;
- freshness and completeness eligibility;
- fallback source, if any, with explicit mapping and basis.

A fallback must never silently switch instrument, venue, quote currency, or observation type. If no eligible anchor exists, the forecast is abstained or the relevant target is marked not estimable.

The default candidate for historical label construction is the close of the last fully completed bar at the declared resolution. It is not adopted as a production default until source coverage, latency, and market-hours behavior are validated. Partial bars are not used as completed closes.

The anchor record must preserve value, currency, source reference, event time, knowledge time, observation resolution, and policy version. The data cutoff cannot precede the knowledge time of any input.

## 3. Horizon and observation resolution

A horizon is a forward interval [t0, t1] relative to the anchor time. The target definition stores exact UTC start and end instants, not only a display label such as "1 day".

Candidate research horizons (not approved production defaults):

| Candidate horizon | Candidate bar resolutions | Notes |
|---|---|---|
| 5 minutes | 1 second / 1 minute | Requires high-quality intraday trades or bars |
| 15 minutes | 1 minute | Short intraday movement |
| 1 hour | 1 minute / 5 minutes | Intraday |
| 4 hours | 5 minutes / 15 minutes | Intraday |
| 1 day | 1 hour | Daily terminal target |
| 7 days | 1 hour / 4 hours | Weekly target |
| 30 days | 4 hours / 1 day | Longer horizon |

This is a research candidate matrix only. A horizon/resolution pair is enabled only after verifying source availability, timestamp semantics, gap rate, market coverage, sample count, and cost/retention terms. No model is assumed to transfer across horizons or assets.

Overlapping horizons create dependent labels. Walk-forward validation must use purging/embargo or an equivalent method justified by the label window and sampling scheme.

## 4. Terminal direction target

Let P0 be the declared anchor and P1 the eligible reference price at the terminal horizon time. The terminal simple return is:

r_terminal = (P1 / P0) - 1

The terminal log return may also be retained as a distinct target:

r_log = ln(P1 / P0)

The target definition must identify which return convention drives the label. Percentage return is expressed in percent units when serialized as RETURN_PCT; formula implementations must avoid mixing decimal fractions and percentage points.

Direction describes the terminal price relative to the anchor. It does not describe the path taken between t0 and t1.

Three classes are defined:
- BULLISH: terminal return is above the positive sideways boundary;
- BEARISH: terminal return is below the negative sideways boundary;
- SIDEWAYS: terminal return lies within the inclusive sideways band.

The sideways boundary is a versioned parameter, not a universal hard-coded percentage. It must be selected using training/calibration data only, with a documented rationale, asset/horizon scope, estimation window, and freeze date. The selected value is frozen before the final holdout. Until this parameter is defined and justified, the target status is NOT_CONFIGURED and no directional classification is emitted as a production label.

If P1 or the required observations are unavailable or invalid, the label is missing/unassessable; it is never set to zero or inferred from a partial path.

## 5. Magnitude and path excursion targets

Magnitude and path risk are separate target families:

- Terminal percentage return: r_terminal.
- Terminal absolute price change: delta_P = P1 - P0 in quote currency.
- Maximum favorable excursion (MFE): maximum direction-adjusted favorable movement from P0 during the horizon.
- Maximum adverse excursion (MAE): maximum direction-adjusted adverse movement from P0 during the horizon.
- Realized path volatility: a separately versioned statistic over eligible observations.

MFE and MAE describe the path, not terminal direction. A forecast may finish lower after a large favorable excursion, or finish higher after a large adverse excursion. These outcomes must not be collapsed into one label.

Point estimates, intervals, and predictive distributions are separate outputs. Interval coverage is evaluated against realized outcomes using a predeclared calibration procedure. An interval is not a subjective confidence score.

## 6. Terminal price targets versus first-passage targets

Two distinct target concepts are supported:

### Terminal price distribution
The distribution of price at t1. Price ranges are generated from a versioned model/calibration procedure and assessed by empirical coverage and interval width.

### First-passage target
A declared price interval or boundary expected to be reached at any time in [t0, t1]. Each first-passage target has:
- target ID and inclusive lower/upper bounds;
- quote currency and reference market;
- event definition;
- horizon and validity interval;
- source resolution and price-observation policy;
- model/calibration provenance when a probability is provided.

A first-passage target is not a trade instruction and does not imply that an order could have been filled at the boundary.

## 7. Price-zone taxonomy

Zones have distinct semantics and must not be conflated:

1. STRUCTURAL_SUPPORT / STRUCTURAL_RESISTANCE: intervals derived only from observations known at or before the forecast cutoff. Candidate algorithms may use swing pivots, repeated reactions, volume profile, or liquidity data, but the algorithm, parameters, lookback, and evidence must be versioned.
2. PROJECTED_PATH: future price corridor or interval generated by the predictive distribution for a declared time bucket.
3. SCENARIO_INVALIDATION: price interval or boundary whose breach invalidates a named scenario under an explicit rule.

Structural zones are historical/contextual candidates; they do not automatically carry a probability of future reaction. A probability of zone touch is a separate forecast target and requires a formally defined event and calibration on out-of-sample observations.

All zone boundaries are inclusive. Zone construction must use only information available by data_cutoff_time. A structural zone cannot be retrospectively moved to better fit the realized path.

## 8. Time-to-target and event definitions

Time-to-target is a first-passage/survival target, not a simple regression target over only successful examples.

Supported event definitions:
- FIRST_TOUCH: first eligible observed price enters or crosses the inclusive target interval.
- CLOSE_BEYOND: first completed bar closes beyond the specified boundary.
- CONFIRMED_BREAKOUT: first time a separately versioned confirmation rule is satisfied.
- OTHER: only with a complete versioned event definition.

Time is measured from horizon_start and is stored in seconds or a declared higher-resolution unit. The source observation resolution limits temporal precision. Do not report finer precision than the data supports.

Observation outcomes:
- Event observed at a known sample: exact observed event time at the source's resolution.
- Event occurs between the last known non-event sample and the first event sample: interval-censored event time; preserve both bounds.
- Event not observed by a fully covered horizon end: right-censored at horizon_end for survival/time-to-event analysis, while the binary within-horizon outcome is NOT_REACHED.
- Observation ends before the forecast horizon or coverage is insufficient: outcome record is PARTIAL/CENSORED/UNASSESSABLE as appropriate; do not classify the target as definitively NOT_REACHED.
- A data gap spans a target boundary: record CROSSED_BY_GAP with the last observed pre-gap sample and first observed post-gap sample. Do not invent the crossing time or price and do not infer execution.

For time-to-event model evaluation, retain censoring information and use survival-aware metrics/methods. Ordinary MAE on reached events alone creates selection bias and is not an acceptable sole metric.

## 9. Probability semantics

A probability always refers to a defined event, asset/instrument, venue, horizon, and target version.

- Direction probabilities refer to the terminal direction classes.
- Zone-touch probabilities refer to at least one eligible observed price entering/crossing the specified zone within the horizon.
- First-passage probabilities refer to reaching the declared target under its event definition.
- Interval coverage refers to the proportion of realized target values inside a predictive interval over a defined evaluation sample.

Probabilities are calibrated only after a separate calibration procedure and out-of-sample reliability evaluation. Raw scores, logits, model confidence fields, and heuristic weights are not probabilities. Uncalibrated/not-quantified states use null numeric values.

## 10. Leakage and target construction

For a forecast issued at cutoff C:
- Features may use only records whose knowledge/availability time is <= C.
- Labels may use future observations only for the outcome associated with that historical forecast origin; those future observations must never enter its feature vector.
- Data revisions, late disclosures, and backfilled provider records retain their actual knowledge time. A later correction cannot be treated as known earlier.
- All fitted target parameters (sideways bands, normalization, quantiles, zone parameters, calibrators) are learned from training/calibration windows only.
- Final holdout data cannot select targets, parameters, feature definitions, model versions, or acceptance thresholds.
- Overlapping target windows must be accounted for in split design through purging/embargo or a documented equivalent.

## 11. Readiness and abstention

A target configuration is not ready for model training until its asset, market identity, anchor, horizon, resolution, label formula, parameter-fitting procedure, missing-data policy, and version are all specified.

If the anchor is stale, source coverage is inadequate, the horizon is unsupported, or label construction is ambiguous, emit an explicit missing/unassessable state or abstain. Never silently shorten a horizon, substitute another venue, forward-fill across an unbounded gap, or convert missing values to zero.

## 12. Contract mapping

The Forecast v1 record carries:
- target_definition.target_id/version and reference_price;
- time.as_of_time, data_cutoff_time, horizon_start and horizon_end;
- prediction.direction and magnitude;
- prediction.price_targets and price_zones;
- prediction.time_to_target and scenario_probabilities;
- evidence, data_quality and provenance.

ForecastOutcome v1 carries:
- forecast_id and observation_window;
- observed_path and source provenance;
- target_events and zone_events;
- evaluation metrics, data quality, and evaluator version.

If the outcome contract cannot represent an interval-censored event bracket or distinguish event-level right-censoring from an incomplete observation window, it must be extended before target labels are generated at scale.

## 13. Open parameters

The following remain intentionally unselected until authorized data samples and validation evidence exist:
- primary venue/source and anchor observation type;
- observation resolution per horizon;
- exact production horizon matrix;
- freshness, coverage, and minimum sample gates;
- sideways-band estimator and fitted parameter;
- predictive quantile levels and calibration method;
- structural-zone algorithms and their parameters;
- probability calibration method and acceptance gates.

These are not omissions to fill with arbitrary constants. Each requires evidence and a versioned decision before use.

See Issue #27 for the implementation and acceptance criteria.
