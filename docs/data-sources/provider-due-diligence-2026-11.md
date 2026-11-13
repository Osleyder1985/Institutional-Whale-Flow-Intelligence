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
- Arkham real-time address-intelligence update (2026-09-08): https://arkm.com/announcements/arkham-api-upgrade-real-time-intel
- Nansen Smart Money labels and endpoint scope: https://docs.nansen.ai/api/smart-money
- Nansen Smart Money netflows: https://docs.nansen.ai/api/smart-money/netflows
- Nansen Smart Money holdings: https://docs.nansen.ai/api/smart-money/holdings
- Nansen endpoint credit overview: https://docs.nansen.ai/api/overview
- Nansen chain support by endpoint: https://docs.nansen.ai/reference/chains
- Glassnode current plan/API access: https://studio.glassnode.com/pricing

## 8. Audit status

Documentation review: **completed for the official pages cited above**.

Provider approval: **none**.

Sample-response validation: **not performed**.

Account-specific entitlement and terms verification: **pending**.

Paid access, continuous polling, production ingestion and historical backfill: **not authorized**.


## Revisión de cambios documentales — 2026-11-13

Se revalidaron las páginas oficiales consultadas. CryptoQuant mantiene los límites documentados de Basic/Advanced/Professional/Premium y el acceso on-chain desde Professional. Glassnode confirma la Light API de Advanced (14 días, diario, 50 llamadas/día, sin bulk) y el consumo de créditos por combinaciones en endpoints bulk. CoinGlass mantiene en su tabla oficial los precios mensuales y los derechos personales/comerciales ya registrados.

Se incorporan dos precisiones:
- Nansen: `Fund` sigue apareciendo como filtro temporalmente aceptado, pero está deprecado y ya no devuelve wallets en Smart Money; los fondos se consultan mediante Fund Holdings. Bitcoin sigue sin soporte en Smart Money, aunque determinados endpoints de Profiler sí lo cubren.
- Arkham: el feed de actualizaciones de inteligencia de direcciones pasó a tiempo real el 2026-09-08; además, se retiraron métricas de balance/volumen/transferencias y `orderBy` de ese endpoint. No se presume que esos campos existan en el feed actual.

La revisión documental no equivale a validar acceso de cuenta, muestras, términos particulares ni retención. Ningún proveedor queda aprobado.


## Revalidación de fuentes oficiales — 2026-11-13

- CryptoQuant: Professional incluye API on-chain a resolución diaria; Premium añade ventanas horarias y por bloque y acceso a historial completo. Basic y Advanced no incluyen endpoints on-chain.
- Glassnode: la página de precios actual describe API Light en Advanced y API profesional basada en créditos. La guía de créditos indica un crédito típico por llamada y consumo por combinación en bulk; no se conserva ninguna tarifa BTC/ETH fija sin evidencia pública vigente.
- Nansen: la documentación actual enumera `Fund` y `Smart Trader` como etiquetas de Smart Money. Se retira la afirmación anterior de que `Fund` fue eliminado el 2026-09-09 porque no está respaldada por las páginas oficiales vigentes consultadas. Bitcoin figura en la matriz general solo para determinados endpoints Profiler, no para Smart Money.
- CoinGlass: la tabla oficial mantiene las tarifas mensuales, límites, permisos personales/comerciales y endpoints por plan documentados en esta evaluación.
- Arkham: el anuncio del 2026-09-08 confirma el feed de inteligencia en tiempo real y la retirada del objeto metrics y de `orderBy` en ese endpoint.

Esta revalidación corrige afirmaciones que ya no estaban sustentadas. No sustituye el acceso de cuenta, la prueba de respuestas reales ni la revisión contractual y de retención. **Ningún proveedor queda aprobado.**
