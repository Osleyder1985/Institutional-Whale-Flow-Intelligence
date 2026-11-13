# Provider Due Diligence — BTC/ETH Pilot (2026-11-12)

## 1. Executive decision

**No commercial data provider is approved for production ingestion yet.**

The documentation review is sufficient to identify meaningful product boundaries and reject several unsafe assumptions. It is not sufficient to approve a provider because account-level endpoint entitlements, current terms, retention rights, and real BTC/ETH sample quality have not been tested.

Recommended next step: implement and test only the provider-neutral observation contract and adapter test harness. In parallel, request/verify Arkham API access and evaluate CryptoQuant Professional economics. Do not activate polling, paid calls, or historical backfills.

## 2. Comparative matrix

| Provider | BTC coverage | ETH coverage | Relevant documented capabilities | Access / price evidence | Main limitation | Decision |
|---|---|---|---|---|---|---|
| Arkham Intel API | API announcement describes entity labels and fund-flow data; endpoint-level BTC coverage not independently verified | Same | Entity labels, fund-flow data, intelligence API | New API announced 2026-04-15; access, price and quota not published in the announcement | Need API access, endpoint docs, attribution methodology, plan, terms and retention confirmation | CONDITIONAL_CANDIDATE |
| CryptoQuant | Explicitly lists BTC | Explicitly lists ETH | Exchange/miner/entity flows, market indicators, Fund & ETF data, network and flow indicators | Basic free: 10,000 credits/month, 10 req/min, 30 days, market data only. Professional: 500,000 credits/month, 120 req/min, one year, on-chain included. Premium: full history and unlimited credits. Price must be checked in current account/pricing page | Core whale/on-chain metrics are not included in free Basic; must validate exact BTC/ETH endpoint entitlements and methodology | BEST_DOCUMENTED_ONCHAIN_CANDIDATE; NOT_APPROVED |
| Glassnode | Broad metric platform; confirm each metric's asset coverage | Broad metric platform; confirm each metric's asset coverage | On-chain and crypto-financial metrics, cohort and holder analysis | Advanced Light API: 14 days, daily resolution, 50 calls/day. Full API requires Professional subscription. Data credits consumed per request | Higher access barrier; exact plan price and each needed metric/asset must be confirmed | CONDITIONAL_CANDIDATE |
| Nansen | Bitcoin is supported only by selected Profiler endpoints; no Smart Money netflow/holdings on Bitcoin | Smart Money endpoints support Ethereum | Smart Trader netflows, DEX trades, holdings, historical holdings; separate Fund Holdings API | Current official API help says credits are purchased; current credit prices/plan entitlements must be reconciled against account and docs | Smart Money is not an institutional-fund proxy; funds were removed from Smart Money on 2026-09-09. Bitcoin is not supported by Smart Money endpoints | ETH_ONLY_CANDIDATE_FOR_SMART_TRADER; NOT_BTC_SMART_MONEY |
| CoinGlass | Bitcoin ETF flows, derivatives and market endpoints are documented; verify exact ETH endpoint permissions individually | Derivatives/market coverage; verify exact endpoint permissions | Open interest, funding, liquidations, ETF flows; Startup adds Spot CVD and Coin Flows; whale alerts/positions shown for Hyperliquid | Hobbyist $35/mo; Startup $95/mo; Standard $379/mo; Professional $879/mo (monthly rates shown in official docs, checked 2026-11-04). Hobbyist/Startup personal use; Standard+ commercial use | Hyperliquid whale endpoints do not equal BTC/ETH chain whale tracking. Hobbyist lacks Spot CVD. Plan terms and endpoint access must be checked before purchase | PERSONAL_MARKET_DATA_CANDIDATE; NOT_GENERAL_WHALE_SOURCE |

## 3. Provider-specific findings

### 3.1 Arkham

Arkham's 2026-04-15 announcement says its Intel API integrates entity labels and fund-flow data into workflows/products. The announcement links to API access, but does not itself provide sufficient detail to establish endpoint-level coverage, pricing, quotas, attribution confidence, retention, or redistribution rights.

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

The free tier can support a low-cost API-contract experiment for market data but cannot validate the core on-chain whale-flow use case. Professional is the first documented tier that includes on-chain data. Exact price and endpoint-specific credit costs must be verified before approval.

### 3.3 Glassnode

The current API setup documentation is more nuanced than a simple Professional-only statement:
- Professional subscribers have access to the full API within their plan.
- Advanced subscribers have a Light API limited to 14 days, daily resolution, 50 calls/day, and no bulk endpoints.
- API usage consumes data credits.
- The credit documentation currently lists BTC at 1 credit/request and other assets, including ETH, at 2 credits/request.

This makes Advanced Light API a possible constrained evaluation route if the account's metric entitlements include the required BTC/ETH metrics. It is not a substitute for verifying the metric catalog, data finalization, timestamps, and historical availability. Exact subscription cost remains unverified here.

### 3.4 Nansen

The current Smart Money documentation states:
- Smart Money is based on historically profitable traders (Smart Traders), not institutional funds.
- Fund wallets stopped being part of Smart Money on 2026-09-09. The `Fund` label is deprecated for Smart Money filters.
- Netflow, DEX Trades, and Holdings support Ethereum and selected EVM chains.
- Bitcoin is not listed among Smart Money-supported chains.
- Bitcoin support is limited to selected Profiler endpoints; this is not Smart Money netflow/holdings.
- Fund Holdings is a separate product/API area and must be evaluated independently.

Therefore, Nansen must not be described as a unified BTC+ETH institutional-fund flow source. It may be considered for Ethereum Smart Trader activity, with the label methodology and API credit costs validated separately.

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
- Evaluate Nansen only for Ethereum Smart Trader, and Fund Holdings separately.
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

## 8. Audit status

Documentation review: **completed for the official pages cited above**.

Provider approval: **none**.

Sample-response validation: **not performed**.

Account-specific entitlement and terms verification: **pending**.

Paid access, continuous polling, production ingestion and historical backfill: **not authorized**.
