# IWFI Signal, Source and Tool Coverage Catalog

- Catalog ID: `IWFI-CATALOG-SIGNALS-001`
- Version: `0.1.0-draft`
- Status: Draft / audit baseline; not an approval of any source or feature
- Scope: BTC and ETH pilot
- Governing product requirement: [Issue #23](https://github.com/Osleyder1985/Institutional-Whale-Flow-Intelligence/issues/23)
- Master tracking: [Issue #38](https://github.com/Osleyder1985/Institutional-Whale-Flow-Intelligence/issues/38)
- Last repository audit: 2026-11-13

## 1. Purpose and interpretation

This document is the cross-family index for candidate predictive inputs, source/tool candidates, their responsible Issues and evidence status. It does not replace the detailed specifications in Issues #31–#37 or provider diligence in Issue #3.

**A listed signal is a research candidate, not a proven predictor. A listed provider is a candidate, not an approved source.** No connector, polling, backfill, paid plan, scraping or live capture is authorized by this catalog.

The intended Forecast output is defined in Issue #23: direction, magnitude, price ranges/targets, zones, time-to-target, uncertainty, evidence, counterevidence, alternatives and invalidation. Signals must only use information available at the forecast cutoff (Issue #29) and must earn promotion through the experimental protocol (Issue #36).

## 2. Status vocabulary

| Status | Meaning |
|---|---|
| NOT_RESEARCHED | Candidate recorded; operational definition or evidence review incomplete |
| SPECIFIED | Signal semantics and requirements documented in its responsible Issue |
| SOURCE_UNVERIFIED | Candidate source named, but endpoint coverage/terms/entitlement not verified |
| SOURCE_APPROVED | Specific endpoint and intended use approved from current evidence and permissions |
| IMPLEMENTED | Connector or deterministic feature implementation exists in reviewed code |
| DATA_QUALITY_VERIFIED | Coverage, freshness, completeness, consistency and provenance checks passed for a defined sample |
| EXPERIMENTAL | Feature is eligible for a preregistered experiment, not yet validated |
| VALIDATED_OOS | Incremental predictive value demonstrated under frozen walk-forward and untouched holdout protocol |
| REJECTED | Evidence shows unsuitable, invalid, unavailable or not worth its cost for the defined use |
| DEPRECATED | Previously used definition/source retired with reason and migration history |

Statuses are per **signal + endpoint + asset/instrument + intended use**, not global provider labels. Do not skip stages or infer a later status from an earlier one.

## 3. Family-to-Issue coverage map

| Family | Required signal inventory | Responsible Issue(s) | Initial status |
|---|---|---|---|
| Spot and microstructure | OHLCV; trades; aggressor-side volume where observable; CVD; order-book depth/imbalance; spread; liquidity; realized spread/slippage proxies; venue dispersion | [#31](https://github.com/Osleyder1985/Institutional-Whale-Flow-Intelligence/issues/31), #3, #23, #29, #36 | SPECIFIED at family level; individual endpoints/features not approved |
| Derivatives and leverage | OI by venue/contract; OI change; funding (observed vs predicted); basis; futures/perpetual spreads; liquidations by side; long/short population ratios; options IV/skew/term structure/OI by strike and expiry; expiry calendar | [#32](https://github.com/Osleyder1985/Institutional-Whale-Flow-Intelligence/issues/32), #3, #29, #36, #37 | SPECIFIED at family level; source/feature verification pending |
| On-chain and institutional flows | Native/token transfers with separate semantics; exchange inflows/outflows/reserves; holder cohorts; concentration; whale accumulation/distribution hypotheses; entity labels; miner/validator flows; treasury disclosures; ETF flows/holdings/filings; internal/OTC observability limits; stablecoin supply/flows | [#33](https://github.com/Osleyder1985/Institutional-Whale-Flow-Intelligence/issues/33), #3, #6, #8, #10, #12, #14, #15, #16, #18, #19, #29, #36 | SPECIFIED at family level; no assumption that transfer = trade or intent |
| News, events, regulation and macro | Primary announcements; secondary reporting; rumors/leaks; listings/delistings; outages/incidents; upgrades; unlocks; regulatory stages/effective dates; rates, inflation, employment, USD, liquidity; vintage/revisions | [#34](https://github.com/Osleyder1985/Institutional-Whale-Flow-Intelligence/issues/34), #3, #29, #36 | SPECIFIED at family level; source licensing and historical availability pending |
| Technical structure and regimes | Trend/swings; confirmed pivots; HH/HL/LH/LL; support/resistance zones; breakouts/retests/false breaks; gaps; momentum/returns; realized/historical volatility; ATR; trend/range/volatility/liquidity/stress regimes | [#35](https://github.com/Osleyder1985/Institutional-Whale-Flow-Intelligence/issues/35), #23, #27, #29, #36 | SPECIFIED at family level; definitions must remain causal in time |
| Social sentiment, attention and positioning | Sentiment by asset/topic; mentions/authors; search/attention; bot/spam/coordinated activity; social/news divergence; surveys; aggregate positioning; source population and bias | [#37](https://github.com/Osleyder1985/Institutional-Whale-Flow-Intelligence/issues/37), #32, #34, #29, #36 | SPECIFIED at family level; not a universal market sentiment measure |
| Cross-market and liquidity context | BTC/ETH relative strength and correlation; cross-asset/market relationships; stablecoin supply/flows; cross-venue/cross-chain liquidity; event calendar and regime interactions | #23, #29, #36; gap review tracked by #38 | NOT_RESEARCHED as a complete standalone feature family; overlapping parts are candidates in #31–#35 |

### Important boundary distinctions

- Exchange inflow/outflow is not an executed buy/sell.
- A wallet label is not verified identity unless its evidence supports that status and validity interval.
- Aggregate provider metrics are not individual transactions.
- Long/short ratios may describe different populations and must not be combined without semantic normalization.
- News sentiment and social sentiment are distinct populations; syndicated copies must not multiply one event's weight.
- A technical level calculated retrospectively is not necessarily available at the historical forecast cutoff.
- Cross-market correlations are candidates, not causal explanations.
- Stablecoin issuance, transfer, exchange balance and available market liquidity are different measures; do not conflate them.

## 4. Candidate source/tool map

This is a diligence queue, not a provider selection. Issue #3 and `docs/data-sources/provider-due-diligence-2026-11.md` remain authoritative for current provider research.

| Candidate | Candidate coverage to investigate | Important known boundary / verification requirement | Initial status |
|---|---|---|---|
| Arkham Intelligence | Entity/address intelligence, tagged wallet activity and fund-flow intelligence | Verify endpoint-level BTC/ETH coverage, API access, latency, terms, retention and actual entity-label evidence; do not assume all features are available to the account | SOURCE_UNVERIFIED |
| CryptoQuant | Exchange/miner/entity/on-chain flows and market metrics | Coverage depends on plan, endpoint, asset and resolution; confirm current entitlement and permitted retention | SOURCE_UNVERIFIED |
| Glassnode | On-chain metrics, holder/cohort and market indicators | API depth, history, resolution and request limits differ by plan; verify endpoint-level BTC/ETH access | SOURCE_UNVERIFIED |
| Nansen | Smart Money, wallet/entity profiling and fund holdings | Smart Money is not a Bitcoin feature; BTC support in selected Profiler endpoints is limited; Fund Holdings is separate from Smart Money | SOURCE_UNVERIFIED |
| CoinGlass | Derivatives, OI, funding, liquidations and selected market/flow metrics | Plan-specific endpoint/history/usage rights; a specialized whale feed does not imply broad BTC/ETH whale coverage | SOURCE_UNVERIFIED |
| Exchange primary APIs | Spot trades, OHLCV, order book, derivatives where offered, venue-specific liquidations/positions | Each venue/instrument needs separate semantics, timestamp, history, rate-limit and licensing review | NOT_RESEARCHED per endpoint |
| Blockchain nodes/explorers | Canonical chain data, transaction and transfer events | Network-specific identity, finality/reorg, event locator and token/native asset separation required | NOT_RESEARCHED per endpoint |
| ETF issuers/administrators and official filings | Published flows, holdings, disclosures | Distinguish event/effective date from publication/known time; coverage and publication cadence differ | NOT_RESEARCHED per source |
| Regulators, central banks and statistical agencies | Official regulatory and macro releases | Preserve jurisdiction, publication calendar, revisions/vintages and source terms | NOT_RESEARCHED per source |
| News providers and official announcement channels | News, events, corrections, rumor/leak claims | Preserve first-known time, corrections, syndication/dependency and redistribution rights | NOT_RESEARCHED per source |
| Social/search platforms | Attention, sentiment and public positioning proxies | Platform access, deleted/edited content, population bias, bot detection, privacy and retention terms | NOT_RESEARCHED per platform |

No source in this table is SOURCE_APPROVED. The provider due-diligence document must be updated with evidence before any promotion.

## 5. Cross-cutting data and research contracts

Every signal record must link to the applicable contracts and preserve, where relevant:

- `event_time`, `published_at`, `known_at`/`available_at`, `ingested_at` and `computed_at`; never substitute event time for knowledge time.
- Asset, network, venue, instrument, unit, aggregation method, source endpoint and schema version.
- Source coverage, history, resolution, latency, revisions, missingness, quality and license/retention classification.
- Feature definition/version, lookback window, cutoff semantics and point-in-time join behavior.
- Overlap/dependency and double-counting risk across providers and families.
- Tests/fixtures and experiment ID, including null/negative findings.

Relevant foundations: [#6 observation contract](https://github.com/Osleyder1985/Institutional-Whale-Flow-Intelligence/issues/6), [#8 attribution](https://github.com/Osleyder1985/Institutional-Whale-Flow-Intelligence/issues/8), [#12 resolution](https://github.com/Osleyder1985/Institutional-Whale-Flow-Intelligence/issues/12), [#23 forecast requirements](https://github.com/Osleyder1985/Institutional-Whale-Flow-Intelligence/issues/23), [#25 Forecast/Outcome contracts](https://github.com/Osleyder1985/Institutional-Whale-Flow-Intelligence/issues/25), [#27 targets](https://github.com/Osleyder1985/Institutional-Whale-Flow-Intelligence/issues/27), [#29 point-in-time datasets](https://github.com/Osleyder1985/Institutional-Whale-Flow-Intelligence/issues/29) and [#36 experimental protocol](https://github.com/Osleyder1985/Institutional-Whale-Flow-Intelligence/issues/36).

## 6. BTC vs ETH coverage rules

Do not mark a signal as covering BTC and ETH merely because a provider markets a general crypto product. Maintain separate evidence for each asset, network, instrument, venue and endpoint.

At minimum, the follow-up audit must distinguish:

- BTC native chain vs exchange-market BTC instruments.
- ETH mainnet native transfers vs ERC-20 token events.
- Spot vs perpetuals vs dated futures vs options.
- Venue-level data vs provider aggregates.
- Observed vs estimated vs modeled metrics.
- Current endpoint coverage vs historical backfill coverage.

A missing asset/endpoint is recorded as unavailable or unverified, never zero and never silently substituted.

## 7. Initial gap register

| Gap ID | Gap | Existing owner | Next action |
|---|---|---|---|
| GAP-001 | No single cross-family signal/source/Issue/feature/test/experiment index | #38 | Build the versioned catalog and validate links/IDs |
| GAP-002 | Cross-market relationships and stablecoin liquidity are not yet a dedicated, fully specified family | #38; related inputs in #31–#35 | Determine scope and incremental value before proposing a new Issue |
| GAP-003 | Individual endpoint-to-feature mappings and BTC/ETH coverage are not yet evidenced for every candidate provider | #3 | Complete endpoint-level due diligence and permission review |
| GAP-004 | Social/news/derivatives positioning overlap can double-count similar populations | #32, #34, #37 | Define semantic boundaries and overlap controls in feature specs |
| GAP-005 | A family being specified does not establish implemented or validated features | #29, #36 | Track each signal through implementation, data-quality tests and preregistered OOS experiments |

This gap register is preliminary and may be changed only with evidence and traceable review. It does not authorize new connectors or collection.

## 8. Promotion and governance

1. Specify the signal and its semantics in the responsible Issue.
2. Verify source endpoint coverage, access, terms, retention and cost under #3.
3. Implement provider-neutral contracts and point-in-time behavior under #6/#29 and relevant foundations.
4. Verify data quality for a defined BTC/ETH sample without hiding gaps or revisions.
5. Preregister an experiment under #36, compare against baselines and run ablations.
6. Promote to VALIDATED_OOS only after the frozen walk-forward/holdout protocol supports the claim.
7. Preserve negative results, source changes, deprecations and prior catalog versions.

No ranking, weights, thresholds or predictive claims are assigned in this draft.

## 9. Change log

- 2026-11-13 — Initial cross-family coverage audit created from repository Issues #3, #6, #8, #12, #23, #25, #27, #29 and #31–#37. Added preliminary cross-market/stablecoin gap and endpoint-level verification requirements. No source approvals or predictive validation claimed.
