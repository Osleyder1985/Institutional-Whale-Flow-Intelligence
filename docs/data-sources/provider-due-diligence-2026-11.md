# Provider Due Diligence — BTC/ETH Pilot (reviewed 2026-11-13)

## 1. Executive decision

**No commercial data provider is approved for production ingestion yet.**

The documentation review is sufficient to identify meaningful product boundaries and reject several unsafe assumptions. It is not sufficient to approve a provider because account-level endpoint entitlements, current terms, retention rights, and real BTC/ETH sample quality have not been tested.

Recommended next step: implement and test only the provider-neutral observation contract and adapter test harness. In parallel, request/verify Arkham API access and evaluate CryptoQuant Professional economics. Do not activate polling, paid calls, or historical backfills.

## 2. Comparative matrix

| Provider | BTC coverage | ETH coverage | Relevant documented capabilities | Access / price evidence | Main limitation | Decision |
|---|---|---|---|---|---|---|
| Arkham Intel API | API announcement describes entity labels and fund-flow data; address-intelligence updates feed is documented as real-time since 2026-09-08; endpoint-level BTC coverage still requires account verification | Same | Entity labels, fund-flow data, intelligence API | New API announced 2026-04-15; access, price and quota not published in the announcement | Need API access, endpoint docs, attribution methodology, plan, terms and retention confirmation | CONDITIONAL_CANDIDATE |
| CryptoQuant | Explicitly lists BTC | Explicitly lists ETH | Exchange/miner/entity flows, market indicators, Fund & ETF data, network and flow indicators | Basic free: 10,000 credits/month, 10 req/min, 30 days, market data only. Professional: 500,000 credits/month, 120 req/min, one year, on-chain included at daily resolution. Premium: full history, 800 req/min and hourly/per-block on-chain resolution. Price must be checked in current account/pricing page | Core whale/on-chain metrics are not included in Basic or Advanced; validate exact BTC/ETH endpoint entitlements, credits and methodology | BEST_DOCUMENTED_ONCHAIN_CANDIDATE; NOT_APPROVED |
| Glassnode | Broad metric platform; confirm each metric's asset coverage | Broad metric platform; confirm each metric's asset coverage | On-chain and crypto-financial metrics, cohort and holder analysis | Current pricing page lists Advanced at $49/month billed annually with API Light (14 days, daily resolution, 50 calls/downloads per day); Professional API matches Studio access (up to 15+ years and 10-minute resolution) with credit-based usage. The API introduction page separately describes Professional API access as an add-on; account entitlement must be reconciled before purchase | Exact metric/asset entitlements and API add-on terms require account verification; credit cost depends on endpoint and bulk parameter combinations | CONDITIONAL_CANDIDATE |
| Nansen | Bitcoin is supported only by selected Profiler endpoints; no Smart Money netflow/holdings on Bitcoin | Smart Money endpoints support Ethereum | Smart Money netflows, DEX trades, holdings and historical holdings; current docs list both `Fund` and `Smart Trader` labels | Official endpoint overview lists 5 credits for Smart Money netflows/holdings and 1 credit for selected Profiler endpoints; confirm current account credit balance and any endpoint-specific changes | `Fund` is a provider label, not independently verified legal identity. Smart Money does not support Bitcoin; overall Bitcoin support is limited to selected Profiler endpoints (balance and transactions) | ETH_ONLY_CANDIDATE_FOR_SMART_MONEY; NOT_BTC_SMART_MONEY |
| CoinGlass | Bitcoin ETF flows, derivatives and market endpoints are documented; verify exact ETH endpoint permissions individually | Derivatives/market coverage; verify exact endpoint permissions | Open interest, funding, liquidations, ETF flows; Startup adds Spot CVD and Coin Flows; whale alerts/positions shown for Hyperliquid | Hobbyist $35/mo; Startup $95/mo; Standard $379/mo; Professional $879/mo (monthly rates shown in official docs, checked 2026-11-04). Hobbyist/Startup personal use; Standard+ commercial use | Hyperliquid whale endpoints do not equal BTC/ETH chain whale tracking. Hobbyist lacks Spot CVD. Plan terms and endpoint access must be checked before purchase | PERSONAL_MARKET_DATA_CANDIDATE; NOT_GENERAL_WHALE_SOURCE |

## 3. Provider-specific findings

### 3.1 Arkham

Arkham's 2026-04-15 announcement says its Intel API integrates entity labels and fund-flow data into workflows/products. A later 2026-09-08 update documents the address-intelligence updates feed as real-time: new, updated and deleted address intelligence is delivered within minutes rather than once per day. The update includes deposit-address detection, verified contract labels, token/NFT labels, deployer labels and analyst-curated labels. It also retires the metrics object (balance, volume, transfer counts) and `orderBy` options from that endpoint; these fields must not be assumed available there. Neither announcement establishes endpoint-level BTC/ETH coverage, pricing, quotas, attribution confidence, retention or redistribution rights for the user's account.

Required before approval:
- Obtain current API documentation and account access.
- Verify BTC and ETH entity/address coverage separately.
- Record label provenance, confidence/verification semantics, update timestamps, and label history.
- Confirm rate limits, price, permitted personal research, storage, retention, export, and derived-data rights.
- Test whether fund-flow data is based on independently observed transactions or vendor-level clustering/estimation.

### 3.2 CryptoQuant

The official Data API page documents:
- REST base URL: `https://api.cryptoquant.com/v1`.
- Bearer-token API key authentication.
- JSON time-series responses and a `window` parameter.
- Basic free tier: 10,000 credits/month, 10 requests/minute, 30 days of history; no on-chain data.
- Advanced: 300,000 credits/month, 60 requests/minute, one year; no on-chain data.
- Professional: 500,000 credits/month, 120 requests/minute, one year; on-chain data included.
- Premium: unlimited credits, 800 requests/minute, full history; on-chain data included.
- BTC and ETH are explicitly listed among covered assets.
- On-chain families include exchange flows, miner flows, entity/inter-entity flows, network/flow indicators, Fund & ETF data, and ETH2 staking.

The free Basic tier can support a low-cost API-contract experiment for market data but cannot validate the core on-chain whale-flow use case. Professional is the first tier that includes on-chain API data, at daily resolution; Premium adds hourly and per-block on-chain windows and full history. Exact price and endpoint-specific credit costs must be verified before approval.

### 3.3 Glassnode

The current official pricing page and API documentation indicate:
- Advanced is displayed at $49/month when billed annually and includes API Light: 14 days of history, daily resolution, and 50 calls/downloads per day.
- Professional provides API access matching Studio entitlements, up to 15+ years of history and 10-minute resolution, with credit-based usage. The API introduction page separately describes Professional API as an add-on, so the exact account entitlement and checkout terms must be confirmed.
- A standard API call typically consumes one credit. Bulk requests consume credits per asset/parameter combination; the current public credit guide does not establish a fixed BTC-versus-ETH credit multiplier. The prior assertion of BTC=1 and ETH=2 credits is therefore removed as unverified.

Advanced Light API may support a constrained evaluation if the required BTC/ETH metrics are included in the account's metric tiers. It is not a substitute for verifying the metric catalog, data finalization, timestamps, and historical availability.

### 3.4 Nansen

The current official Smart Money and chain-support pages state:
- Smart Money endpoints provide netflows, DEX trades and holdings, and the current docs list both `Fund` and `Smart Trader` labels. I found no current official evidence on those pages that the `Fund` label was removed on 2026-09-09; that earlier assertion is withdrawn.
- Smart Money supports Ethereum and selected other chains, but Bitcoin is not in its endpoint-specific support matrix.
- The general Nansen chain catalog does include Bitcoin for selected Profiler endpoints: current balance and transactions are listed, while PnL and related-wallet endpoints are not listed for Bitcoin.
- The endpoint overview lists 5 credits for Smart Money netflows/holdings and 1 credit for selected Profiler endpoints. The endpoint-specific catalog and account credit terms must still be checked before use.

Therefore, Nansen may be evaluated for Ethereum Smart Money flows, including provider-labelled `Fund` activity, but this label is not proof of legal identity or institutional status. Bitcoin Profiler support is not equivalent to Bitcoin Smart Money netflows or holdings. Do not describe Nansen as a unified BTC+ETH institutional-fund flow source.

### 3.5 CoinGlass

The official plan page currently documents:
- Hobbyist: $35 monthly; 83 public REST endpoints; 30 requests/minute; personal use; Bitcoin ETF flows and derivatives examples.
- Startup: $95 monthly; 134 endpoints; 80 requests/minute; personal use; adds Spot CVD, Coin Flows, and Hyperliquid whale alerts/positions.
- Standard: $379 monthly; 155 endpoints; 300 requests/minute; commercial use; adds WebSocket streams, liquidation orders, order-book heatmaps and large orders.
- Professional: $879 monthly; 168 endpoints; 1,200 requests/minute; commercial use and deeper history.

These prices were marked by CoinGlass as checked on 2026-11-04. Candle intervals and historical ranges differ by endpoint and must not be generalized to all datasets. Hyperliquid wallet/whale data must not be presented as proof of BTC or ETH on-chain whale activity.

## 4. Important semantic constraints

The following distinctions are mandatory in the data model and analysis:

1. **Transfer != trade.** An on-chain transfer between addresses does not establish that a purchase or sale occurred.
2. **Exchange inflow != sale.** Funds may be deposited for custody, collateral, internal reorganization, or other purposes.
3. **Exchange outflow != purchase.** It may represent custody changes, withdrawals, or internal wallet rotation.
4. **ETF flow != full institutional exposure.** It covers only the specified fund/vehicle and reporting methodology.
5. **Smart Trader != institution.** Profitability-based labels are not evidence of fund ownership or institutional status.
6. **Address label != legal identity.** Vendor attribution is a claim with provenance, confidence and temporal scope.
7. **Multiple vendors != independent confirmation.** Vendors may share upstream data or address-clustering sources.
8. **Missing != zero.** Unknown, unavailable, delayed and zero-valued observations remain distinct states.

## 5. Recommended first vertical slice

Do not build all five integrations.

**Slice A — Contract and evidence pipeline (provider-neutral):**
- BTC and ETH asset/network identifiers.
- Source observation envelope with provider, endpoint, source record ID, event time, retrieval time, raw payload hash, schema version, quality status, and retention classification.
- Explicit attribution status: VERIFIED, PROVIDER_LABELLED, INFERRED, UNKNOWN, DISPUTED.
- Fixtures representing a confirmed transaction, an exchange-labelled address transfer, a vendor label, a missing field, a duplicate, a delayed observation, and a conflicting label.
- Tests proving that transfers and exchange flows are not silently converted into buy/sell trades.

**Slice B — Access feasibility:**
- CryptoQuant Basic account-level sample for market-data API mechanics only; no claim that it validates whale/on-chain data.
- Request Arkham API access and current endpoint/terms documentation.
- Check whether Glassnode Advanced Light API gives required BTC/ETH metrics before considering Professional.
- Evaluate Nansen only for Ethereum Smart Money endpoints after separating provider-labelled `Fund` and `Smart Trader` cohorts; do not treat either label as independently verified institutional identity. Bitcoin Profiler support remains a separate, narrower capability.
- Consider CoinGlass Hobbyist only if Bitcoin ETF flow and derivatives data are required in the personal-research pilot; Startup is not justified until Spot CVD is a confirmed requirement.

No paid plan is approved by this document. No API calls, polling, or backfill are authorized.

## 6. Approval checklist per provider

- [ ] Official docs and terms archived or versioned with review date.
- [ ] Personal/non-commercial use explicitly permitted for the intended project.
- [ ] Raw response retention and derived data storage explicitly permitted.
- [ ] BTC and ETH support proven per endpoint with sample responses.
- [ ] Endpoint schema, units, timestamp semantics and revision policy recorded.
- [ ] Rate limit, quotas, credit cost and expected monthly cost calculated.
- [ ] Attribution labels and their confidence/provenance documented.
- [ ] Failure, pagination, partial response and stale-data behavior tested.
- [ ] Independent corroboration path identified.
- [ ] User authorization recorded before any paid subscription or production ingestion.

## 7. Official references

- CryptoQuant Data API: https://cryptoquant.com/apis
- Glassnode API setup: https://docs.glassnode.com/basic-api/api
- Glassnode API credits: https://docs.glassnode.com/basic-api/api-credits
- Nansen Smart Money: https://docs.nansen.ai/api/smart-money
- Nansen chain support: https://docs.nansen.ai/reference/chains
- Nansen Smart Money netflows: https://docs.nansen.ai/api/smart-money/netflows
- CoinGlass API plans and permissions: https://docs.coinglass.com/reference/plans-and-permissions
- Arkham API announcement (2026-04-15): https://arkm.com/announcements/the-new-arkham-api
- Arkham real-time address-intelligence update (2026-09-08): https://arkm.com/announcements/arkham-api-upgrade-real-time-intel
- Nansen Smart Money holdings: https://docs.nansen.ai/api/smart-money/holdings
- Nansen endpoint credit overview: https://docs.nansen.ai/api/overview
- Glassnode current plan/API access: https://studio.glassnode.com/pricing

## 8. Audit status

Documentation review: **completed for the official pages cited above**.

Provider approval: **none**.

Sample-response validation: **not performed**.

Account-specific entitlement and terms verification: **pending**.

Paid access, continuous polling, production ingestion and historical backfill: **not authorized**.


## Revalidación de fuentes oficiales — 2026-11-13

- CryptoQuant: Professional incluye API on-chain a resolución diaria; Premium añade ventanas horarias y por bloque y acceso a historial completo. Basic y Advanced no incluyen endpoints on-chain.
- Glassnode: la página de precios actual describe API Light en Advanced y API profesional basada en créditos. La guía de créditos indica un crédito típico por llamada y consumo por combinación en bulk; no se conserva ninguna tarifa BTC/ETH fija sin evidencia pública vigente.
- Nansen: la documentación actual enumera `Fund` y `Smart Trader` como etiquetas de Smart Money. Se retira la afirmación anterior de que `Fund` fue eliminado el 2026-09-09 porque no está respaldada por las páginas oficiales vigentes consultadas. Bitcoin figura en la matriz general solo para determinados endpoints Profiler, no para Smart Money.
- CoinGlass: la tabla oficial mantiene las tarifas mensuales, límites, permisos personales/comerciales y endpoints por plan documentados en esta evaluación.
- Arkham: el anuncio del 2026-09-08 confirma el feed de inteligencia en tiempo real y la retirada del objeto metrics y de `orderBy` en ese endpoint.

Esta revalidación corrige afirmaciones que ya no estaban sustentadas. No sustituye el acceso de cuenta, la prueba de respuestas reales ni la revisión contractual y de retención. **Ningún proveedor queda aprobado.**


## 9. Endpoint capability matrix — evidence-level distinctions (2026-11-13)

This matrix separates five capabilities that must not be conflated:

- **Flow/transfer measurement:** aggregate metric or on-chain movement.
- **Address/entity intelligence:** provider claim about an address or cluster.
- **Individual execution:** a venue trade/execution record, not merely an order or a flow metric.
- **Named participant in that execution:** evidence linking a named actor to that exact execution.
- **Institutional holdings/disclosure:** a position, holding, or fund-flow report with its own reporting period and publication delay.

| Provider / documented endpoint family | Flow or transfer measurement | Address/entity intelligence | Individual execution | Named participant in that execution | Institutional holdings / disclosure | BTC / ETH boundary |
|---|---|---|---|---|---|---|
| Arkham Intel API / address intelligence updates | Yes: fund-flow and address-intelligence capabilities are announced; exact endpoint semantics need account docs | Yes: address labels, entity intelligence and update feed; label is a vendor claim, not legal proof | Not established by the cited announcements | Not established | Not established by the cited API announcement; verify any separate fund product | Endpoint-specific BTC and ETH coverage, access and payload schema remain unverified |
| CryptoQuant on-chain metric catalog | Yes: exchange, miner, entity and inter-entity flow time series | Entity/address clustering is reflected in proprietary metrics; do not assume a named legal actor per row | No individual execution evidence established by the cited API overview | No | Fund & ETF metric family is documented; identify exact vehicle, reporting basis and delay per endpoint | BTC and ETH explicitly listed; on-chain access begins at Professional, daily resolution; Premium adds hourly/per-block |
| Glassnode exchange/entity metrics | Yes: exchange deposits, withdrawals, netflows, balances and cohort metrics | Yes: exchange labels and proprietary entity clustering; documentation says labels/metrics can be mutable | No individual execution evidence established by the cited metrics | No | Not established by the reviewed exchange/entity endpoints; assess fund products separately | Metric metadata and account tier must confirm each asset/metric. Point-in-Time variants exist for selected metrics |
| Nansen Smart Money | Yes: Smart Money netflows and aggregated holdings; DEX trade endpoint exists | Yes: curated wallet labels including Fund and Smart Trader; these remain provider classifications | DEX trades are described as trading activity for supported Smart Money wallets; validate exact records and semantics from authorized samples | Potentially wallet-level Smart Money attribution on supported chains; not proof of legal identity or beneficial owner | Fund-labelled holdings/flows are available as provider-classified data, not independently verified institutional filings | Smart Money support includes Ethereum, not Bitcoin. Bitcoin appears only in selected Profiler endpoint support |
| CoinGlass Spot / On-chain / ETF endpoints | Yes: Spot Coin Netflow exposes taker buy/sell volumes and net inflow; CVD is an aggregate taker buy-minus-sell measure; whale-transfer and ETF-flow endpoints are separate | Not established as named institutional address attribution by the cited endpoints | Spot/futures WebSocket trade streams and trade/order datasets may expose venue-level market events; inspect endpoint schema and venue coverage before treating a record as an individual fill | No named customer/beneficial owner demonstrated by the reviewed public endpoint docs | Yes: BTC/ETH ETF flow endpoints are listed; ETF flows are fund-level aggregates, not customer executions | BTC and ETH appear across relevant categories, but exact endpoint/plan/asset availability must be checked individually; Spot CVD requires Startup or higher, commercial use requires Standard+ |

### 9.1 What the official endpoint documentation actually proves

**CoinGlass — aggregated taker flow is not an identified actor.** The Spot Coin Netflow endpoint describes taker buy volume, taker sell volume and net inflow across selected exchanges and time windows. Spot CVD is calculated as taker buy minus taker sell and accumulated by interval; missing taker-side data can be counted as zero in the documented calculation. These are market-wide/venue-aggregated measures, not participant identities. CoinGlass separately documents spot/futures trade WebSocket channels; those can support market execution observation where the specific feed provides records, but the reviewed docs do not establish customer identity. Startup adds Spot CVD and Coin Flows; Standard is the first plan marked for commercial use and adds WebSocket channels.

**CryptoQuant — strong on-chain coverage, not a trade tape.** Its public API page documents exchange/miner/entity/inter-entity flow metrics and explicit BTC/ETH coverage. These metrics can support flow monitoring and hypotheses, but the public overview does not establish a per-execution participant identity. Professional is the first plan with on-chain API access; the public page describes daily on-chain resolution there, with hourly/per-block windows on Premium.

**Glassnode — useful entity/cohort context, mutable labels.** Its documentation defines entities as clusters estimated using proprietary heuristics and warns that entity-based metrics can change as statistical information is updated. Exchange metrics use labeled exchange addresses that are continuously updated and can also change. Selected Point-in-Time (PiT) metrics are append-only and preserve what was computed at the time, which is materially different from the latest revised series. Deposits to exchanges and net exchange flows remain transfers/aggregates, not executions.

**Nansen — best documented wallet-level Smart Money route for Ethereum, not unified BTC/ETH.** Smart Money exposes netflows, DEX trades and holdings for supported chains including Ethereum. The chain matrix does not include Bitcoin for Smart Money. The general chain catalog lists Bitcoin for selected Profiler endpoints, which must not be represented as BTC Smart Money. Holdings are explicitly aggregated rather than per-wallet breakdowns. A provider label such as Fund or Smart Trader is not independently verified legal identity.

**Arkham — address/entity intelligence candidate, execution attribution unproven.** Its API announcements document entity labels, fund-flow data and a real-time address-intelligence updates feed. The September 8 update says the feed includes new, updated and deleted intelligence, while retiring its metrics object and orderBy fields from that endpoint. Public announcements do not establish that the API identifies the customer or beneficial owner behind a specific exchange execution.

### 9.2 First-slice implications

1. There is no single publicly documented provider in this review that proves, for both BTC and ETH, the full chain **named institution → exact individual execution → participant BUY/SELL → beneficial owner**.
2. CryptoQuant is the strongest documented candidate for BTC+ETH on-chain flow coverage, but its Professional tier is paid and its flow metrics do not prove individual buys/sells.
3. Arkham is a candidate for entity/address intelligence, but it requires account-level endpoint docs and samples before any capability is accepted.
4. Nansen can be a separate Ethereum-only Smart Money evaluation; it cannot be the single BTC+ETH first source.
5. CoinGlass can support market microstructure, taker-side aggregates, trade feeds and ETF flow monitoring, but those capabilities do not name the customer behind a venue execution.
6. Glassnode can add exchange/entity cohort and Point-in-Time context, but current account entitlement and exact asset/metric access remain unverified.
7. Therefore, the first vertical slice must not be described as “institutional buy/sell detection” unless an authorized source sample actually links an identified participant to an individual execution. Until then, the valid outputs are separately typed: observed transfer, aggregate flow, venue execution with unknown participant, provider-labelled address/entity, or delayed holdings/disclosure.

## 10. Additional official references for the capability matrix

- CoinGlass API overview and endpoint categories: https://docs.coinglass.com/reference/getting-started-with-your-api
- CoinGlass endpoint overview and minimum plan by endpoint: https://docs.coinglass.com/reference/endpoint-overview
- CoinGlass Spot Coin Netflow semantics: https://docs.coinglass.com/reference/spot-coin-netflow
- CoinGlass Spot CVD calculation and plan access: https://docs.coinglass.com/reference/spot-cvd-history
- CoinGlass API authentication and key security: https://docs.coinglass.com/reference/authentication
- CryptoQuant Data API, asset coverage and plan gates: https://cryptoquant.com/apis
- Glassnode exchange deposit/netflow definitions and mutable labels: https://docs.glassnode.com/basic-api/endpoints/transactions
- Glassnode entity clustering description: https://docs.glassnode.com/basic-api/endpoints/entities
- Glassnode Point-in-Time exchange netflow variants: https://docs.glassnode.com/basic-api/endpoints/pit
- Glassnode exchange-label methodology and limitations: https://docs.glassnode.com/further-information/exchange-data-transparency-notice
- Nansen Smart Money endpoints and supported chains: https://docs.nansen.ai/api/smart-money
- Nansen holdings endpoint (aggregated balances): https://docs.nansen.ai/api/smart-money/holdings
- Nansen general chain support by endpoint: https://docs.nansen.ai/reference/chains
- Arkham real-time address intelligence update: https://arkm.com/announcements/arkham-api-upgrade-real-time-intel

## 11. Revised recommendation and approval state

**Recommendation:** do not approve a single provider yet. Treat provider selection as a capability-specific decision rather than choosing a vendor brand for the entire product. The most plausible eventual combination is a source for BTC+ETH on-chain flow metrics, a separate address/entity intelligence source, venue trade feeds for anonymous executions, and official fund/exchange disclosures. This is an architecture hypothesis, not an approved integration plan; every source still requires endpoint-level rights and samples.

**No approval change:** no API key, account entitlement, paid plan, provider sample, polling, backfill or raw-payload retention has been authorized or tested by this documentation update.


## 12. Binding zero-cost policy — Issue #59 (2026-11-14)

**User requirement: total external cash expenditure for IWFI must remain USD 0.** This is stricter than “has a free tier”. It applies to every runtime and development dependency: data/API access, credits, hosting, storage, CI, monitoring, notifications, licenses and support.

Disallowed:
- Paid subscriptions, pay-per-call, paid top-ups, add-ons or licenses.
- Trials that require payment details or can convert into a charge.
- A non-recurring starter-credit grant as a required operational dependency.
- Unbounded or unclear variable charges.
- Assuming a free web dashboard means free automated API access.

### 12.1 Reclassification of previously evaluated providers

| Provider | Free access documented | Does free access cover IWFI's required capability? | Zero-cost decision |
|---|---|---|---|
| CryptoQuant | Basic: 10,000 API credits/month, market data only, daily resolution and 30 days of history | No. On-chain exchange/miner/entity flows require Professional; the Basic tier explicitly excludes on-chain endpoints | **REJECT as on-chain source**. Optional market-data evaluation only if the recurring free entitlement and personal-use terms remain valid |
| Nansen | Free API allocation is documented; current vendor help page states 100 initial credits plus 10 daily refreshed credits, with purchased credits available | Not a sustainable core dependency without proving that the exact required endpoints fit the recurring free allocation indefinitely. Some Smart Money endpoints are credit-consuming; no paid top-ups permitted | **NOT APPROVED** as core dependency. May be considered only for strictly bounded free-tier experiments, no purchased credits |
| CoinGlass | API plans start at Hobbyist paid tier; no zero-cost recurring API tier established by reviewed official plan table | No | **REJECT** |
| Glassnode | Advanced/Light API is paid; Professional API is paid/add-on or credit-based | No | **REJECT** |
| Arkham | API access is application/trial or plan gated; no verified recurring free API entitlement for the required endpoints | No evidence of a durable, unrestricted zero-cost API for this project | **NOT APPROVED**. A free web UI, if available, is not an automated data API |
| Binance public market data | Official public market-data-only REST endpoints and public trade data are available without authenticated private-account access | Yes for public market executions, order book, ticker and candles; no participant identity | **APPROVED CANDIDATE**, subject to terms, rate limits and capture contract review |
| Public blockchain data | Bitcoin and Ethereum public ledgers can be independently read using open-source node/client software and/or genuinely free public endpoints | Yes for transactions, balances/state and transfers; no inherent real-world identity or CEX customer execution identity | **APPROVED SOURCE CLASS**, subject to a verified zero-cost access method and resource budget |

### 12.2 Zero-cost first vertical slice (revised)

Build the first usable slice from:
1. **Binance public Spot market data** for BTCUSDT and ETHUSDT: individual public trade records where available, plus order-book/ticker context. Treat buyer/seller as anonymous market participants; aggressor side is not a named actor.
2. **Public Bitcoin and Ethereum ledger observations**: blocks, transactions, address balances/state and token transfers, preserving address-level identity as UNKNOWN unless separately supported by verifiable public evidence.
3. **Official public disclosures**: issuer/fund filings and exchange notices with their actual publication timestamps and reporting periods. A filing is delayed holdings/disclosure evidence, not a live execution.
4. **Open-source processing and local persistence** only where they introduce no external subscription, license charge or paid hosted dependency.

No commercial label provider is required for the first slice. A source may be used only after checking its terms, request limits, data rights, and whether the method incurs any charge. If an apparently free service requires a card, paid credit purchase, paid tier, or chargeable cloud resource, it is excluded.

### 12.3 What this means for the product objective

A zero-cost design can detect:
- large observable on-chain transfers (with size calculated from source data, not interpreted as a trade);
- movements to/from known exchange addresses only when the address attribution is supported by a cited source and its validity interval;
- public BTC/ETH market executions and aggregate aggressor-side pressure on venues;
- ETF/fund holdings and flows when published by official sources, with reporting delay;
- candidate relationships between events and price moves, explicitly marked as hypotheses.

A zero-cost design **cannot promise**:
- complete identification of all banks, funds, institutions or whales;
- the legal beneficial owner behind arbitrary addresses;
- the identity of the buyer or seller behind an anonymous centralized-exchange execution;
- real-time institutional buy/sell detection from aggregate exchange inflows/outflows;
- commercial-provider-grade wallet labels without using a qualifying free source.

The system must represent the actor as UNKNOWN where evidence does not establish identity. Do not downgrade evidence standards to simulate paid-provider coverage.

### 12.4 Runtime cost guardrails

- No cloud resource may be provisioned if it can generate a charge.
- Prefer local execution and storage; document electricity, bandwidth and hardware as user-side operating requirements rather than pretending they are zero-resource.
- No API key with billing enabled may be configured for an IWFI adapter.
- No purchased credits, paid fallback or automatic plan upgrade.
- Every source adapter must declare `cost_model`, `recurring_free_quota`, `billing_risk`, `terms_reviewed_at`, and `zero_cost_eligible`.
- CI must reject `zero_cost_eligible=true` if the source is pay-per-call, trial-only, non-recurring-credit-only, requires paid entitlement, or has unresolved billing risk.
- If a free quota is exhausted, the adapter stops safely; it must not retry via paid endpoints or silently switch to a chargeable provider.

### 12.5 Official references for free-access boundaries

- Binance Spot REST API: https://developers.binance.com/en/docs/products/spot/rest-api
- Binance market-data-only FAQ: https://developers.binance.com/en/docs/products/spot/faqs/market_data_only
- Binance public historical data: https://data.binance.vision/
- CryptoQuant current API plans: https://cryptoquant.com/apis
- CryptoQuant current pricing: https://cryptoquant.com/pricing
- Nansen API free-credit terms: https://academy.nansen.ai/articles/0938495-get-started-with-api
- CoinGlass API plans: https://docs.coinglass.com/reference/plans-and-permissions
- Arkham API application/access: https://arkm.com/api/

**Decision:** this zero-cost policy supersedes any earlier suggestion to evaluate or use CryptoQuant Professional, paid CoinGlass tiers, Glassnode paid API, or any paid vendor plan. No provider API or account is approved by this document. No paid service, credit purchase, polling or backfill is authorized.



## 13. Binance public Spot source review — 2026-11-14

This section separates the historical Binance Vision archive from the public Spot market-data API. Their access methods and governing terms must not be conflated.

### 13.1 Historical archive: documented access and use boundary

Official Binance Public Data documentation states:
- Spot trade archives are sourced from the Spot historical-trades endpoint and contain trade ID, price, quantity, quote quantity, timestamp, `isBuyerMaker`, and `isBestMatch`.
- Spot aggregate-trade archives contain aggregate trade ID, price, quantity, first/last trade IDs, timestamp, `isBuyerMaker`, and `isBestMatch`.
- Daily files are published the next day; monthly files are published on the first Monday of the month.
- Spot archive timestamps from 2025-01-01 onward are in microseconds; older records use milliseconds. The ingestion contract must preserve source units and normalize only with explicit source-version rules.
- Archive files can be updated after publication; checksum files are provided. A checksum must be verified and archive revisions must not silently overwrite prior observations.

Official Vision Dataset Terms (version 1.0, updated 2026-08-26) state:
- Datasets are available free of charge.
- The stated license is CC BY-NC-SA 4.0, subject to the additional Vision Dataset Terms.
- Permitted non-commercial purposes include academic research, non-monetized open educational projects, personal non-production historical backtesting, and non-commercial open-source data-science evaluations.
- Commercial use requires a separate written enterprise data license.
- The terms prohibit attempts to de-anonymize users from transaction identifiers and prohibit circumventing rate limits or impairing platform operations.
- Derivative work redistribution must preserve attribution and the specified license conditions.

**Preliminary decision for the user's declared personal, non-commercial research:** the historical archive appears to fit the stated personal non-production research category, provided the project remains within all Vision Dataset Terms and the incorporated CC BY-NC-SA obligations. This is a source-specific preliminary assessment, not legal advice or authorization for a commercial/live product. No redistribution of raw data, de-anonymization, or commercial use is approved.

### 13.2 Endpoint clarification: do not classify data-api.binance.vision as a live feed

Binance Spot REST documentation and its market-data-only FAQ describe `https://data-api.binance.vision` as a public market-data-only base URL. However, a contributor response dated 2026-11-05 in the official `binance/binance-public-data` repository, Issue #502, explicitly states that `data-api.binance.vision` is not a live Binance endpoint for the Vision Dataset Terms question, and instructs users to rely only on `data.binance.vision` and the endpoints listed there.

IWFI adopts the conservative interpretation:
- Do not model `data-api.binance.vision` as a live streaming or real-time feed.
- Do not build or activate an adapter against that host under the Binance Vision historical-dataset approval.
- The source under evaluation is the downloadable archive service at `data.binance.vision`, with daily/monthly files and published checksums.
- Automated retrieval of those datasets, including via endpoints listed by the archive, is subject to the Vision Dataset Terms and Binance Terms of Use.
- The repository contributor response is useful source-specific clarification, but it is not a signed legal opinion or a substitute for written confirmation from Binance Legal/licensing if scope remains ambiguous.

The Binance Spot REST documentation may describe API behavior, timestamps, rate limits and public endpoints, but that documentation alone does not establish that a given endpoint is part of the Vision Dataset archive service or authorize IWFI to treat it as a live feed. Keep the REST API and archive source classes separate.

No live API adapter is approved. Any future request to use a different Binance endpoint must receive its own endpoint-specific cost, terms, retention and capability review before implementation or activation.

### 13.3 What the trade fields can and cannot establish

- A Spot trade record is evidence that a trade was executed on Binance's venue at the recorded price, quantity and time.
- `isBuyerMaker` indicates whether the buyer was the maker. When true, the seller was the taker/aggressor; when false, the buyer was the taker/aggressor. This is venue-side aggressor direction, not the legal identity of either counterparty.
- The public trade record does not disclose the customer identity, beneficial owner, bank, fund, institution, or whale behind either side.
- Binance defines an aggregate trade as one or more individual trades from the same taker order filled at the same time and price. Therefore, aggTrades must not be represented as a one-row-per-individual-fill feed.
- Neither the individual trade feed nor aggressor-side inference identifies the institution that initiated the order. Participant attribution remains UNKNOWN unless separate evidence establishes the participant for that specific execution.

### 13.4 Source decision

| Source | Capability decision | Cost decision | Terms decision | IWFI activation |
|---|---|---|---|---|
| Binance Vision historical Spot trade archive | Candidate for historical venue-execution observations for BTCUSDT and ETHUSDT | Free of charge under published Vision Dataset Terms | Preliminary fit for personal non-production research only; comply with CC BY-NC-SA 4.0 and additional terms | NOT YET APPROVED; sample validation and retention design remain pending |
| `data-api.binance.vision` | Not approved or classified as a live feed for IWFI; keep distinct from downloadable Vision archives | Cost/entitlement not approved for IWFI use | Repository contributor clarification in Issue #502 says rely on `data.binance.vision` and its listed endpoints for Vision Datasets | NOT APPROVED; no adapter |

### 13.5 Official references

- Spot REST API: https://developers.binance.com/en/docs/products/spot/rest-api
- Market Data Only FAQ: https://github.com/binance/binance-spot-api-docs/blob/master/faqs/market_data_only.md
- Spot API Glossary (`isBuyerMaker`, `aggTrade`): https://developers.binance.com/en/docs/products/spot/faqs/spot_glossary
- Binance Public Data archive documentation: https://github.com/binance/binance-public-data/blob/master/README.md
- Binance Vision Dataset Terms: https://github.com/binance/binance-public-data/blob/master/TERMS_AND_CONDITIONS.md

**Decision:** Binance Vision historical Spot trades are the strongest documented zero-price historical market-execution candidate found so far for the personal non-production research scope. This does not identify institutions and does not approve live API polling. Do not treat `data-api.binance.vision` as an IWFI live feed. Issue #3 remains open until BTC/ETH archive samples, checksums, timestamp transitions, archive revisions, applicable terms and retention handling are tested and recorded.
