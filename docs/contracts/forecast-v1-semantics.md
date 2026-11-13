# Forecast and ForecastOutcome v1 — Semantics

Status: proposed versioned data contracts for Issue #25. These schemas define record shape; a semantic validator is also required for cross-field and temporal invariants.

## 1. Forecast is the prediction; Outcome is the later measurement

A `Forecast` is an immutable statement of what the system estimated using information available at its cutoff. A `ForecastOutcome` is a separate record describing what was subsequently observed. Outcome processing must never rewrite a forecast.

A corrected/re-issued forecast receives a new `forecast_id` and may reference the prior record through `supersedes_forecast_id`. A corrected outcome similarly creates a new outcome record.

## 2. Time semantics

All timestamps are RFC 3339 timestamps normalized to UTC and serialized with the `Z` suffix. JSON Schema's `date-time` format alone does not guarantee UTC; the semantic validator must reject non-UTC offsets if the contract policy requires UTC.

- `issued_at`: when IWFI created the record.
- `as_of_time`: the market/evaluation instant the forecast describes.
- `data_cutoff_time`: latest knowledge timestamp allowed in model inputs.
- `horizon_start`, `horizon_end`: interval over which the forecast targets are evaluated.
- Evidence `observed_at`: when the underlying event occurred.
- Evidence `known_at`: when that evidence became available to the system.

Required ordering: `issued_at >= as_of_time >= data_cutoff_time` is not universally valid because the as-of instant and cutoff have distinct meanings. The invariant that must hold is that no feature has `known_at > data_cutoff_time`; the forecast issuance must not predate its data cutoff. The target horizon must start no earlier than the declared as-of instant and end after it. Implementations must document any deliberate latency between as-of and issuance.

Do not backdate `known_at` to the event time. Delayed disclosures and retrospective labels must retain their actual knowledge time.

## 3. Asset and market identity

Asset, network, instrument, market type, venue and quote currency are explicit. A BTC spot forecast on one venue is not interchangeable with a BTC perpetual forecast or a composite index. On-chain transfer quantities are not market prices.

The pilot scope is native BTC and native ETH. Asset identifiers must be canonical and network-qualified; symbols alone are not unique identifiers.

## 4. Direction and magnitude

Direction is one of:
- `BULLISH`
- `BEARISH`
- `SIDEWAYS`
- `UNDETERMINED` (used for abstention)

Direction labels must be generated from a versioned target definition. A sideways band must be explicitly defined in return terms; it must not be inferred from a model's indecision. The threshold defining sideways is not fixed in this schema and must be justified and versioned before model evaluation.

Magnitude uses either:
- `RETURN_PCT`: percentage return relative to the declared reference price; or
- `PRICE_DELTA`: absolute quote-currency price change relative to that reference.

Intervals are inclusive numeric bounds and must satisfy lower <= estimate <= upper when an estimate is present. A null interval or estimate means not supplied, not zero. `coverage_level` is a nominal predictive interval coverage only when supported by a defined calibration/evaluation method; it is not a generic confidence score.

## 5. Price targets and zones

A target is a forecast objective range. A zone is a price interval with a semantic role:
- support/resistance: candidate market reaction areas;
- reaction: a broader expected reaction interval;
- path: a projected price corridor;
- invalidation: an interval/condition that invalidates a scenario.

Zone/target bounds are inclusive and must satisfy lower_price <= upper_price. `valid_from` and `valid_until` define the period during which the estimate applies. Evidence references must resolve to immutable evidence/metric/feature records.

A target or zone does not imply an executable order, fill, or guaranteed touch. If observed prices jump across a target between samples, Outcome must record `CROSSED_BY_GAP`; it must not claim a fill at the target price.

Probability attached to a zone is optional and must be null unless its meaning and calibration method are explicit. A calibrated zone probability requires a non-empty `calibration_ref`; uncalibrated or unquantified zone probabilities and calibration references must both be null. The schema carries `probability_status` to distinguish calibrated, uncalibrated and unquantified values.

## 6. Scenario probabilities

Bullish, bearish and sideways probabilities are a mutually exclusive, collectively exhaustive distribution for the declared direction target and horizon. If status is `CALIBRATED`, all three values must be present and sum to 1 within a documented numerical tolerance (recommended validator tolerance: 1e-6). A schema validator cannot enforce arithmetic sum; a semantic validator must.

If status is `NOT_CALIBRATED` or `NOT_QUANTIFIED`, values must be null. Do not publish model scores or softmax outputs as calibrated probabilities without calibration evidence. Do not treat the uncertainty summary as a probability.

## 7. Time-to-target and censoring

Every time estimate identifies both a target and an event definition:
- `FIRST_TOUCH`: first observed trade/price sample enters or crosses the target interval.
- `CLOSE_BEYOND`: first completed bar closes beyond a boundary.
- `CONFIRMED_BREAKOUT`: a separately versioned confirmation rule is satisfied.
- `OTHER`: a documented event definition is supplied.

Time-to-target bounds are seconds from the forecast horizon start and must satisfy lower <= upper. A point estimate is not required. When no defensible estimate exists, use `NOT_ESTIMABLE` with null bounds and explain why. A target not reached before horizon end is right-censored; it is not a zero-time event and must not be scored as an ordinary exact time.

Outcome records distinguish:
- reached/touched within observed data;
- not reached by the end of a fully observed horizon;
- censored because observation ended early or coverage is incomplete;
- crossed by a data gap, where exact first-touch time/price is unknown;
- unassessable due to invalid or insufficient reference data.

## 8. Outcome price path

Outcome prices must use the same instrument/venue/quote currency as the forecast reference, unless a documented mapping/benchmark is part of the evaluation protocol. Record source references and gaps.

- `max_favorable_excursion_pct` and `max_adverse_excursion_pct` are computed relative to the forecast's direction and declared reference price; the evaluator version must define the exact formula.
- A gap crossing a target/zone is not a trade execution.
- If coverage is incomplete, use `PARTIAL` or `CENSORED`; do not fill missing observations with fabricated values.
- Metrics are versioned and carry explicit units.

## 9. Data quality, abstention and uncertainty

A forecast may be `ABSTAINED` when input quality, coverage, model validity, asset/horizon support or distributional assumptions are inadequate. Abstention is a valid system result, not a model failure to conceal.

A forecast may be `ISSUED` with some components explicitly `NOT_QUANTIFIED` or `NOT_ESTIMABLE`; however, it must not present those fields as numerical estimates. Data quality `FAIL` should normally trigger abstention; any exception requires a documented policy.

Coverage ratio is null when it cannot be computed. Missing inputs are listed explicitly. Missing does not mean zero.

## 10. Provenance and reproducibility

A Forecast references model, feature set, calibration, code, configuration, dataset snapshot and evaluation protocol versions. Source references and evidence links must resolve to retained, permission-compliant records. The record must be reproducible from the permitted input snapshot.

The contract is provider-neutral. It does not authorize data acquisition, raw payload retention, polling, backfills, or paid services.

## 11. Semantic validation rules beyond JSON Schema

A production validator must additionally enforce:
1. All timestamps are UTC `Z` values and chronologically coherent.
2. Evidence `known_at` is no later than data cutoff.
3. Target horizon starts at/after as-of time and ends after start.
4. All price/zone intervals have lower <= upper and compatible currencies.
5. Magnitude interval contains estimate when both are present.
6. Scenario probabilities are all present and sum to 1 only when calibrated; otherwise all are null.
7. Calibrated zone probabilities have a calibration reference and a defined event/horizon semantics.
8. Estimated time-to-target has valid ordered bounds; NOT_ESTIMABLE has null bounds.
9. Issued forecasts have no abstention object and an abstained forecast has a reason and UNDETERMINED direction.
10. ForecastOutcome references an existing immutable Forecast and uses its target/horizon.
11. COMPLETE outcomes have full horizon coverage; PARTIAL/CENSORED/UNASSESSABLE states explain missing observations.
12. A target/zone crossed by a data gap is not recorded as a confirmed exact touch or execution.
13. No absent numeric field is silently coerced to zero.
14. A re-evaluation creates a new record rather than mutating an existing record.

## 12. Versioning policy

The JSON Schema files are versioned under `schemas/forecast/v1/`. Breaking semantic or structural changes require a new major schema version and migration notes. Additive optional fields may be introduced only if compatibility rules and consumers are tested. Existing historical records remain interpretable under their original schema version.

See Issue #25 for acceptance criteria and dependencies.
