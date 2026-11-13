# Data Source Evaluation Register

## Purpose

Track candidate sources for the BTC/ETH pilot without treating a product description or marketing claim as evidence of coverage, accuracy, or permitted use.

No source is approved for production ingestion by this register. Provider terms, exact plans, prices, endpoints, quotas, retention rights, and redistribution rights must be checked against current official documentation and the user's actual subscription before activation.

## Candidate source categories

| Candidate | Intended evidence | Key validation questions | Status |
|---|---|---|---|
| Arkham Intelligence | Address/entity labels and transfer intelligence | Label provenance, entity attribution confidence, API availability, permitted retention/export, cost | PENDING_DUE_DILIGENCE |
| CryptoQuant | Exchange reserves, netflows, whale-related metrics | Exact metric definitions, exchange coverage, entity methodology, history, API plan, retention | PENDING_DUE_DILIGENCE |
| Glassnode | Holder cohorts and on-chain metrics | Cohort definitions, address clustering, asset/network coverage, metric revisions, API access | PENDING_DUE_DILIGENCE |
| Nansen | Wallet labels and Smart Money classifications | Classification methodology, chain coverage, plan/API restrictions, historical depth, retention | PENDING_DUE_DILIGENCE |
| CoinGlass | Open interest, funding, liquidations, derivatives data | Venue/instrument coverage, aggregation methodology, latency, API limits, license | PENDING_DUE_DILIGENCE |
| Official ETF issuers / fund disclosures | Fund holdings, creations/redemptions, published flows | Primary-source availability, reporting lag, share/cash flow semantics, reconciliation | PENDING_DUE_DILIGENCE |
| Exchange market-data APIs | Trades, order books, spot volume | Venue coverage, trade-side semantics, sequence gaps, historical depth, rate limits | PENDING_DUE_DILIGENCE |
| Blockchain nodes / explorers | Public on-chain transactions and blocks | Network coverage, archival access, fees/hosting, reorg handling, attribution limits | PENDING_DUE_DILIGENCE |

## Selection policy

Prefer primary sources for facts that they directly publish. Use analytics vendors for derived classifications only when their methodology and limitations can be documented. For important conclusions, seek independent corroboration from a distinct source rather than counting multiple dashboards that may rely on the same upstream dataset.

A provider is not selected merely because it appears in this candidate list. Selection requires a documented decision and evidence for the due-diligence questions above.

## Cost and access

All prices and plan entitlements are **unknown until verified**. Do not assume a free API, unlimited history, commercial rights, or availability of a particular endpoint. Do not put API keys or other credentials in this repository.

## Minimum provider record

- Provider legal/product name and official documentation URL.
- Product/API version and plan used.
- Terms/license URL and review date.
- Allowed purpose, storage, retention, and redistribution.
- Authentication and secret-management method.
- Endpoint inventory, quota, rate limit, and cost.
- Assets, networks, venues, and history covered.
- Timestamp meaning, update cadence, and revision behavior.
- Known data-quality limitations and attribution methodology.
- Decision owner, decision date, and approval status.
