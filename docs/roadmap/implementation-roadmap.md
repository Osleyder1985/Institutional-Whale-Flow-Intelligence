# IWFI Product and Implementation Roadmap

**Status:** dependency-driven plan aligned with the owner-approved predictive objective in Issue #23.  
**Pilot:** native BTC on Bitcoin mainnet and native ETH on Ethereum mainnet.  
**Operating model:** user-initiated research; no autonomous trading, scheduled forecasting, continuous polling, or unapproved backfill.

## 1. Product objective

IWFI is a **predictive crypto market-intelligence platform**. Its primary output is an auditable, horizon-specific Forecast for BTC or ETH, not a standalone wallet tracker.

A Forecast should estimate, when supported by evidence:

- direction (BULLISH, BEARISH, SIDEWAYS or UNDETERMINED);
- magnitude and plausible return/price ranges;
- target prices and probable support/resistance/reaction zones;
- time-to-target or time-to-zone;
- calibrated scenario probabilities only where calibration is demonstrated;
- uncertainty, coverage, data quality, evidence, counterevidence, alternatives and invalidation conditions.

Every forecast must be point-in-time reproducible and later evaluated through a separate ForecastOutcome. A result must abstain or explicitly report NOT_CALIBRATED, NOT_QUANTIFIED or NOT_ESTIMABLE when evidence is insufficient.

Institutional and whale activity is an important evidence family, not the sole input and not a substitute for predictive validation. Spot, derivatives, on-chain, ETF/institutional disclosures, technical structure, news/macro, sentiment and cross-market context must remain semantically distinct.

## 2. Delivery principles

1. **Evidence before interpretation:** observations, transfers, executions, holdings, balances, attribution claims and forecasts are different domain objects.
2. **Point-in-time correctness:** a feature may only use information available at the forecast cutoff.
3. **No invented certainty:** missing is not zero; unknown is not verified; correlation is not causation.
4. **Source permission before collection:** no endpoint is approved by a public feature page or synthetic test.
5. **Real samples before data claims:** fixtures validate software behavior, not provider accuracy or market coverage.
6. **Reproducible research:** freeze inputs, definitions, versions and evaluation protocols; preserve negative results.
7. **User control:** forecasts run only on explicit request. Alerts and background processes require separate authorization.
8. **Cost constraint:** external recurring and one-time spend remains 0 USD unless the owner explicitly changes this requirement.

## 3. Dependency-driven phases

### Phase 0 — Product governance and repository baseline (P0)

**Goal:** maintain one authoritative product definition, requirements register, backlog and merge process.

- [x] Initial repository baseline and architecture proposal — Issue #1 / PR #2.
- [x] Predictive product direction recorded — Issue #23.
- [x] Main ruleset `protect-main` activated with PR, linear-history, deletion and force-push controls — Issue #4.
- [ ] Verify the current ruleset/check configuration and document any classic/inherited protection that the integration cannot inspect.
- [ ] Align README, architecture, requirements register and roadmap with the current product objective.
- [ ] Review stale Issues against merged implementation evidence; close only after acceptance criteria are verified.

**Exit gate:** README and roadmap agree on the product objective; every active Issue has a unique outcome and explicit dependencies; no Issue is closed solely because a PR exists.

### Phase 1 — Forecast contract and statistical target definitions (P0)

**Goal:** define what IWFI predicts before training or comparing models.

- [x] Owner-approved predictive requirements — Issue #23.
- [ ] Review and integrate official product objective and architecture — PR #24.
- [ ] Versioned Forecast and ForecastOutcome contracts — Issue #25 / PR #26.
- [ ] Target, anchor, horizon, zone, first-passage and censoring semantics — Issue #27 / PR #28.
- [ ] Point-in-time FeatureSnapshot/DatasetSnapshot and leakage controls — Issue #29 / PR #30.
- [ ] Define baseline families, calibration protocol, walk-forward splits and frozen acceptance gates — Issue #36.

**Dependency order:** PR #24 → PR #26 → PR #28 → PR #30.  
**Exit gate:** forecast targets and outcomes have unambiguous, versioned semantics; historical inputs can be reconstructed as known at each forecast cutoff.

### Phase 2 — Canonical evidence and chain integrity (P0)

**Goal:** preserve what was observed without silently converting it into an unsupported identity, trade or conclusion.

Integrated contracts in `main`:

- [x] Source Observation — Issue #6 / PR #7.
- [x] Temporal address/entity Attribution Claims — Issue #8 / PR #9.
- [x] Native BTC/ETH Movement Ledger — Issue #10 / PR #11.
- [x] Deterministic observation resolution — Issue #12 / PR #13.
- [x] Actor Registry and Trade Execution v1 — Issue #41 / PR #52.
- [x] Execution-specific participant attribution v1 — Issue #43 / PR #55.
- [x] Integrated actor activity architecture and cross-domain boundary tests — Issue #50 / PRs #54 and #56.
- [x] BTC/ETH canonicality, finality and reorganization contract — Issue #18 / PR #117.

Remaining extensions:

- [ ] Multi-role execution participants — Issue #77 / PR #78.
- [ ] Temporal Actor Registry resolution — Issue #79 / PR #80.
- [ ] Evidence reference integrity — Issue #81 / PR #82.
- [ ] Immutable evidence snapshots and offline reconstruction — Issue #83 / PR #84.
- [ ] Per-artifact retention authorization — Issue #85 / PR #86.
- [ ] Policy source evidence and local documentary workflow — Issues #88, #90, #92, #94, #96 and #97 / PRs #87, #89, #91, #93, #95, #98 and #99.

**Exit gate:** every material claim and conclusion resolves to exact, admissible evidence with source, time, validity, version and counterevidence. No provider label or transfer alone establishes beneficial ownership or a trade participant.

### Phase 3 — Source approval and first real-data vertical slice (P0)

**Goal:** prove a narrow, permitted BTC/ETH path using real source data before expanding integrations.

- [x] Candidate-provider capability review and cost policy documented — Issue #3 and prior diligence PRs.
- [ ] Approve each exact source/endpoint/use separately — Issue #3.
- [ ] Complete local retention, storage location, backup/sync and deletion gates — Issue #71.
- [ ] Obtain small, reproducible BTC and ETH samples only after the above gates are met.
- [ ] Validate source checksum, schema, units, timestamps, revisions, gaps, quality and provenance.
- [ ] Record explicit source status: APPROVED, APPROVED_WITH_RESTRICTIONS or NOT_APPROVED.
- [ ] Build the first read-only historical spot slice for BTC and ETH using the approved source and existing local processing capability.
- [ ] Keep actor identity UNKNOWN unless a separate admissible claim supports attribution.

**Current source position:** no source is approved for production capture. Binance Vision historical Spot is a candidate for personal/non-production research, still gated by #71. Blockstream Esplora and PublicNode are documented candidates with material limitations, not approved dependencies. No paid source or recurring spend is permitted.

**Exit gate:** one reproducible, authorized real-data sample for each pilot asset passes validation. Synthetic fixtures are not accepted as provider evidence.

### Phase 4 — Signal families and market-participant intelligence (P1)

**Goal:** implement and compare complementary evidence families without assuming predictive value.

Signal specifications:

- [ ] Spot and microstructure — Issue #31.
- [ ] Derivatives, leverage and liquidations — Issue #32.
- [ ] On-chain, institutional flows and whale activity — Issue #33.
- [ ] News, events, regulation and macroeconomics — Issue #34.
- [ ] Technical structure, volatility and regimes — Issue #35.
- [ ] Social sentiment, attention and positioning — Issue #37.
- [ ] Cross-market relationships, liquidity and stablecoins — Issue #40.
- [ ] Maintain a master signal/source/tool catalog — Issue #38 / PR #39.

Actor and activity capabilities:

- [ ] Actor taxonomy and registry completeness — Issue #41.
- [ ] Address discovery and evidence-based clustering — Issue #42.
- [ ] Multi-role execution attribution — Issues #43, #77, #79 and #81.
- [ ] Institutional holdings and positions — Issue #44.
- [ ] Whale balances, cohorts and exposure changes — Issue #45.
- [ ] Exchanges, market makers, custodians and OTC — Issue #46.
- [ ] Canonical actor activity events — Issue #47.
- [ ] User-configurable alerts, opt-in only — Issue #48.
- [ ] Event/actor market impact and incremental predictive value — Issue #49.

Partial implementations under review:

- PR #106: local Binance Spot aggTrades processing for taker-side volume/CVD; this is not institutional identity.
- PR #107: address-level net flows; not a wallet balance or entity identity.
- PR #108: entity-attributed flows; must preserve Bitcoin UTXO limitations.
- PR #110: Bitcoin UTXO inputs/outputs and entity deltas; no real mainnet sample is integrated.
- PR #112: historical controlled-address exposure with completeness gates; no real balance snapshots are integrated.

**Exit gate:** each signal has operational semantics, coverage, availability time, licensing, quality and reproducible calculation. Each actor claim is evidence-backed and temporal. No feature is described as predictive until tested under Phase 6.

### Phase 5 — Persistence, offline-first operation and recovery (P0/P1)

**Goal:** preserve reproducible evidence and allow desktop, Android and iOS to work offline and synchronize safely.

- [ ] Accept offline-first protocol and complete integration scenarios — Issue #22 / PR #118.
- [ ] Accept persistence architecture only after operational requirements and security/retention gates are measured — Issue #16 / PR #17.
- [ ] Implement durable local outbox/server inbox, idempotent transactions, replay and conflict handling.
- [ ] Verify device lifecycle, key management, encryption, backup/restore and retention enforcement.
- [ ] Preserve immutable Forecasts, outcomes, source evidence and historical decisions.
- [ ] Do not select a physical database or production backend before ADR acceptance.

**Current state:** PR #118 validates contracts and an in-memory reference model; it does not demonstrate real transport or durable persistence. PR #17 remains a Draft ADR; no production backend is authorized.

**Exit gate:** real integration tests prove crash recovery, replay, concurrency, conflict preservation, restore integrity and security across supported clients.

### Phase 6 — Predictive research and scientific validation (P0/P1)

**Goal:** determine whether each signal or model improves forecasts beyond reproducible baselines.

- [ ] Build point-in-time datasets for BTC and ETH with permission-compliant historical coverage.
- [ ] Establish simple no-change and statistical baselines for each target/horizon.
- [ ] Evaluate feature families independently before testing interactions.
- [ ] Use chronological walk-forward evaluation and a frozen, untouched holdout.
- [ ] Prevent target leakage, look-ahead, survivorship bias, revision leakage and preprocessing leakage.
- [ ] Evaluate direction, magnitude, intervals, probability calibration, zones and time-to-target separately.
- [ ] Report sample sizes, uncertainty, missingness, regimes, failures and negative results.
- [ ] Evaluate strategy profitability separately from predictive accuracy, including fees, spread, slippage and funding where applicable.
- [ ] Promote a feature/model only when incremental value, stability, availability and cost are demonstrated.

**Exit gate:** reproducible out-of-sample evidence supports every predictive-performance claim. Otherwise the feature remains experimental or is rejected.

### Phase 7 — Forecast delivery, outcome tracking and user experience (P2)

**Goal:** deliver useful forecasts without overstating certainty.

- [ ] Generate a Forecast only when explicitly requested.
- [ ] Display direction, magnitude, target/range, zones, time estimate, uncertainty, evidence, counterevidence and invalidation.
- [ ] Show source coverage, data freshness, model version and limitations beside each result.
- [ ] Store each Forecast immutably and create a separate ForecastOutcome after its horizon.
- [ ] Compare historical forecasts and model versions without rewriting prior outputs.
- [ ] Add optional alerts only after explicit user authorization and validated event semantics.
- [ ] Support desktop, Android and iOS against the same authoritative research history after sync integration is verified.

**Exit gate:** users can reproduce, inspect and evaluate forecasts; unsupported or uncalibrated results are withheld or clearly marked.

## 4. Current critical path

1. **Align documentation and backlog:** PR #24, PR #39 and this roadmap must express one product objective.
2. **Finish forecast contracts:** #24 → #26 → #28 → #30.
3. **Unblock one real-data slice:** #3 + #71, starting with the narrowest permitted BTC/ETH historical spot sample.
4. **Keep evidence semantics correct:** merged contracts in Phase 2 plus the UTXO and multi-role extensions where needed.
5. **Build point-in-time datasets and baselines:** #29 + #36.
6. **Evaluate predictive value:** only after real samples, quality and temporal availability are established.
7. **Complete production platform:** #22 + #16 before promising durable multi-device operation.

Work on independent contracts and synthetic tests may continue in parallel, but no synthetic-only branch may be represented as a completed real-data or predictive capability.

## 5. Issue and PR status rules

- `OPEN` means the acceptance criteria are not yet fully demonstrated in `main`.
- A PR being open, mergeable or CI-green does not mean its change is integrated.
- A PR based on another PR must be reviewed and integrated in dependency order.
- A closed Issue must point to merged code/documentation or other verifiable acceptance evidence.
- A contract test validates software semantics, not source accuracy, legal rights, real-market coverage or forecast skill.
- Keep source authorization, retention activation, capture permission and data quality as separate states.
- Preserve `UNKNOWN`, `DISPUTED`, `PARTIAL`, `NOT_APPROVED`, `NOT_VERIFIED`, `NOT_ACTIVE`, `NOT_CALIBRATED` and abstention states.

## 6. Product scope and exclusions

Included in the long-term product scope: BTC/ETH price prediction, market microstructure, derivatives, on-chain flows, institutional disclosures, whale/entity activity, news/events/macro, technical structure, sentiment and cross-market/liquidity context.

Not authorized by this roadmap: automated trading, custody/private keys, paid APIs or services, unapproved scraping, unapproved data retention, continuous polling, broad historical backfills, autonomous forecasts or alerting. Additional assets/chains require independent data, permission and model validation.

## 7. Evidence of current limitations

At the 2026-11-14 audit:

- No provider is approved for production capture.
- No reproducible real BTC+ETH sample pair has been integrated and validated through the complete pipeline.
- The current `main` contains foundational contracts and local tooling, but not a validated predictive model.
- Forecast contracts and point-in-time dataset work are proposed in open PRs #24, #26, #28 and #30.
- Entity flow and historical exposure work is still under open PRs #107, #108, #110 and #112.
- Offline-first and persistence remain proposals/simulations in open PRs #118 and #17.
- The product objective does not imply a guarantee of predictive accuracy or investment performance.

This roadmap is a sequencing and acceptance document, not an authorization to collect data or claim capabilities that have not been verified.
