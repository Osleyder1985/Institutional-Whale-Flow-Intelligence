# Point-in-Time Dataset Protocol v1

Status: proposed logical contract for Issue #29. It defines what a historical model input is allowed to know. It does not authorize collection, backfill, or production persistence.

## 1. Four distinct clocks

IWFI must not collapse these timestamps:

- event_time: when the underlying market, chain, or news event occurred.
- known_at: when the fact was first publicly/provider-available to a consumer under the source's semantics.
- ingested_at: when IWFI actually received the record.
- available_at: earliest time IWFI could legitimately use the record; for this protocol it is no earlier than max(known_at, ingested_at).
- computed_at: when a derived feature was calculated.
- data_cutoff_time: latest available_at allowed in a particular FeatureSnapshot.

A future event may be a valid feature if it was announced and known before the cutoff (for example, a scheduled token unlock). Its event_time may therefore be later than the cutoff, while known_at and available_at must be at or before the cutoff. Conversely, a historical event corrected or disclosed after the cutoff is not eligible for the original snapshot.

All timestamps are UTC RFC 3339 values ending in Z. Source-specific time semantics and uncertainty must be documented.

## 2. As-of join semantics

For each source record used by a feature, require available_at <= data_cutoff_time. The effective availability time must account for both source knowledge time and actual ingestion time.

A point-in-time join must:
1. select only records eligible at the historical cutoff;
2. resolve revisions according to the revision state known at that cutoff;
3. retain the source reference and revision identifier;
4. avoid using current provider labels or corrected historical values as if they were known earlier;
5. record missing/late records rather than silently substituting a later revision.

Joining on event_time alone is insufficient. A record can describe yesterday but only become available today.

## 3. Feature definition and window contract

Every feature definition is versioned and specifies:
- stable feature ID and semantic description;
- formula, unit, numeric precision and implementation version;
- lookback window and exact boundary convention;
- input source types and source policy;
- observation resolution and aggregation;
- availability lag and freshness rule;
- missingness and bounded-gap policy;
- minimum coverage policy, justified by data/validation evidence;
- fallback behavior, if any;
- whether the feature is event-time, state-as-of, or future-known schedule information.

For historical aggregate features, the data window must not include observations outside the permitted lookback. Future-known calendar/event features may refer to future event_time, but their source record available_at must still be <= cutoff.

## 4. FeatureSnapshot v1

The schema is schemas/predictive/v1/feature-snapshot.schema.json.

A snapshot contains:
- snapshot ID and schema version;
- asset/network and exact market/instrument/venue identity;
- origin time and data cutoff;
- feature-set version;
- source observation references with event_time, known_at, ingested_at, available_at and revision identity;
- computed feature values, definition versions, input windows, source references, status and coverage;
- aggregate data quality;
- code/config/source-policy versions and a content hash.

Feature status semantics:
- AVAILABLE: value is valid and source/coverage policy is satisfied.
- MISSING: no valid value exists; value must be null and missing_reason supplied.
- STALE: value exists but is outside the declared freshness policy; it must not be used as an ordinary available feature.
- INVALID: source or transformation failed validation; value must be null.

A snapshot marked READY must contain only AVAILABLE features and PASS quality. DEGRADED snapshots may retain explicit MISSING/STALE/INVALID features, but the model's eligibility policy must decide whether to abstain. ABSTAINED means no eligible predictive input snapshot was produced.

The snapshot is immutable. Reprocessing or a newly received revision creates a new snapshot ID and hash. It never retroactively changes a prior forecast input.

## 5. DatasetSnapshot v1

The schema is schemas/predictive/v1/dataset-snapshot.schema.json.

The dataset manifest identifies:
- asset and target-definition version;
- feature-set version;
- source, feature and label snapshot references;
- code, environment, source-policy and evaluation-protocol versions;
- split strategy and chronological split manifests;
- purge/embargo method, durations and rationale;
- transformation artifacts and the split on which each was fitted;
- frozen holdout identity and lock timestamp.

Dataset manifests reference sample manifests rather than duplicating large feature matrices. The referenced sample manifest must preserve sample IDs, origin/cutoff times, target windows, labels, feature snapshot IDs, and split membership.

## 6. Feature/label separation

Features describe information eligible at the forecast cutoff. Labels describe future outcomes over the target horizon. They are distinct data products and must not share a mutable record.

The label builder may read post-cutoff observations solely to determine the outcome for that historical origin. It must not append those observations to the historical FeatureSnapshot.

For every sample, retain:
- origin_time and data_cutoff_time;
- feature_snapshot_id;
- target_definition_id/version;
- target horizon start/end;
- label snapshot/reference and censoring status;
- split membership.

A test should fail if any feature source available_at is later than the sample cutoff, even when its event_time is earlier.

## 7. Transformations and model fitting

- Fit imputers, scalers, normalizers, dimensionality reduction, feature selection and target-parameter estimators on TRAIN only.
- Fit probability calibrators only on the designated CALIBRATION split.
- Do not fit or tune any transform on VALIDATION or TEST.
- A model-selection procedure may use TRAIN and VALIDATION according to a frozen protocol, but not the final TEST holdout.
- The transform artifact records fit split, sample manifest, code version, parameters and content hash.
- A new training window or feature definition creates a new artifact/version.

A transform fitted on a combined train+validation set must be explicitly described and frozen by protocol; it must never include final holdout samples.

## 8. Walk-forward split policy

Split membership is chronological. The manifest records each split's start/end, sample count and sample-manifest reference. A split must not be inferred from shuffled row order.

For overlapping labels:
- purge training samples whose target intervals overlap the validation/test interval where this can leak outcome information;
- apply an embargo after the boundary when feature/label dependence can persist;
- derive purge/embargo lengths from the target horizon, feature lookback and sampling cadence;
- record the chosen method and rationale.

The final holdout is frozen before model selection. Its used_for_selection flag is always false. Any inspection that influences model/feature/target selection invalidates the holdout and requires a new untouched test period.

Walk-forward evaluation may use expanding or rolling training windows, but all folds and cutoff boundaries must be recorded. Metrics are reported per asset, horizon, regime and test period with sample counts.

## 9. Late-arriving data and revisions

If a record arrives after a historical cutoff:
- it is excluded from that origin's original FeatureSnapshot;
- it may be included in a newly versioned retrospective dataset only if the experiment explicitly studies revised data and does not claim point-in-time predictive performance;
- it must not silently replace the original value.

If a provider republishes a corrected value, retain revision lineage and the time the correction became available. A later correction can affect a newly created research dataset but cannot alter what was knowable at the historical forecast origin.

## 10. Missingness, gaps and quality

Missing is not zero. No unbounded forward fill. Any bounded fill/imputation is a versioned transform fitted on training data and the original missingness indicator remains available.

A gap may be accepted only under a documented feature-specific policy. Coverage ratios must use an explicit denominator and window. Stale/partial inputs remain visible to the model eligibility policy. If required inputs fail quality gates, abstain rather than silently downgrade the forecast.

## 11. Reproducibility and retention

A FeatureSnapshot must be reconstructable from permitted source references, revisions, feature definitions, code/config versions and source policy. Its hash is computed over a canonical serialization defined by implementation.

A DatasetSnapshot must additionally identify split manifests, label definitions, transforms, environment and evaluation protocol. Deterministic replay should reproduce feature values within documented numeric tolerances.

Retention of raw provider payloads is governed by each provider's terms. A content hash or source reference does not grant a right to retain prohibited data.

## 12. Readiness gates

No production dataset build is authorized by this document. Before real data is used:
- provider access and use/retention rights must be approved;
- the source's event/knowledge/ingestion timestamp semantics must be validated;
- asset, market and venue identity must be explicit;
- feature definitions and label definitions must be versioned;
- data quality and gap policies must be tested on authorized samples;
- temporal splits, purge/embargo and holdout freeze must be recorded.

See Issue #29 for implementation scope and acceptance criteria.
