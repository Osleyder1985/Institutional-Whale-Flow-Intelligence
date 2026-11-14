# Source policy intake status v1.0

## Purpose and boundary

This inventory seeds the retention-policy registry with source scopes already named in Issues #3 and #38. Every entry is deliberately `PENDING_EVIDENCE` and has an empty `policies` array. It is an intake queue only: it grants no right to access, capture, store, retain, reconstruct, export, or distribute data.

The registry is intentionally endpoint- and asset-specific for Binance Spot. BTC and ETH are separate scopes. The historical Binance Vision archive and the live public Spot API are separate source products and must never inherit terms from one another.

## Registered source scopes

| Source ID | Exact scope | Assessment |
|---|---|---|
| `binance_vision_spot_trades_btcusdt` | Binance Vision — Spot historical trades — BTCUSDT | PENDING_EVIDENCE |
| `binance_vision_spot_trades_ethusdt` | Binance Vision — Spot historical trades — ETHUSDT | PENDING_EVIDENCE |
| `binance_vision_spot_aggtrades_btcusdt` | Binance Vision — Spot historical aggregate trades — BTCUSDT | PENDING_EVIDENCE |
| `binance_vision_spot_aggtrades_ethusdt` | Binance Vision — Spot historical aggregate trades — ETHUSDT | PENDING_EVIDENCE |
| `binance_spot_api_trades_btcusdt` | Binance Spot public API /api/v3/trades — BTCUSDT | PENDING_EVIDENCE |
| `binance_spot_api_trades_ethusdt` | Binance Spot public API /api/v3/trades — ETHUSDT | PENDING_EVIDENCE |
| `binance_spot_api_aggtrades_btcusdt` | Binance Spot public API /api/v3/aggtrades — BTCUSDT | PENDING_EVIDENCE |
| `binance_spot_api_aggtrades_ethusdt` | Binance Spot public API /api/v3/aggtrades — ETHUSDT | PENDING_EVIDENCE |
| `binance_spot_api_depth_btcusdt` | Binance Spot public API /api/v3/depth — BTCUSDT | PENDING_EVIDENCE |
| `binance_spot_api_depth_ethusdt` | Binance Spot public API /api/v3/depth — ETHUSDT | PENDING_EVIDENCE |
| `binance_spot_api_ticker_btcusdt` | Binance Spot public API /api/v3/ticker — BTCUSDT | PENDING_EVIDENCE |
| `binance_spot_api_ticker_ethusdt` | Binance Spot public API /api/v3/ticker — ETHUSDT | PENDING_EVIDENCE |
| `binance_spot_api_klines_btcusdt` | Binance Spot public API /api/v3/klines — BTCUSDT | PENDING_EVIDENCE |
| `binance_spot_api_klines_ethusdt` | Binance Spot public API /api/v3/klines — ETHUSDT | PENDING_EVIDENCE |
| `bitcoin_mainnet_local_node` | Bitcoin mainnet — locally operated node — native BTC ledger | PENDING_EVIDENCE |
| `ethereum_mainnet_local_node_native_eth` | Ethereum mainnet — locally operated execution/consensus clients — native ETH ledger | PENDING_EVIDENCE |

## Evidence still required

### Binance Vision historical archive

For each BTCUSDT/ETHUSDT trades and aggregate-trades scope:
- Preserve the exact official Vision Dataset Terms version and its incorporated license text.
- Preserve the official archive documentation describing the relevant file format, publication schedule, timestamp units, checksums, and revision behavior.
- Hash the exact preserved original bytes; record retrieval time and review scope.
- Review personal non-commercial research, local retention, historical snapshots, derived artifacts, reconstruction, attribution, and any redistribution restrictions separately.
- Confirm whether the actual intended artefact type and retention duration fit the terms. A preliminary documentary assessment is not a verified authorization.

### Binance live public Spot API

For each asset and endpoint (`trades`, `aggTrades`, `depth`, `ticker`, `klines`):
- Preserve the applicable official API documentation and the terms governing automated API access and local retention.
- Do not apply Binance Vision Dataset Terms to live API responses unless the issuer explicitly establishes that scope.
- Review rate limits, timestamp units, endpoint semantics, personal research, local retention, and derived-data rights.
- No polling or live capture is enabled by this inventory.

### Public blockchain ledgers

- Define the exact Bitcoin and Ethereum client/software versions and the method of local acquisition.
- Preserve the applicable software licenses and any terms for optional public endpoints if those are ever used.
- Separate software licensing from rights/constraints affecting third-party datasets or hosted services.
- Measure local disk, CPU, RAM, bandwidth, and synchronization requirements before selecting an operational method.
- Ethereum scope here is native ETH and mainnet ledger data only; ERC-20/token events are not included.

## Deliberately not instantiated

- ETF/fund disclosures: no specific issuer, administrator, filing series, or source document has yet been selected. Each must become its own source record once identified.
- Arkham, CryptoQuant, Glassnode, Nansen, and CoinGlass: the zero-cost and endpoint diligence in Issue #3 does not establish an approved recurring free source for the intended operational scope. They are not enabled or represented as approved retention sources here.
- News, social/search platforms, regulators, and macroeconomic agencies: remain candidates in the signal catalog; no specific source/endpoint has been selected for retention review.

## Fail-closed rule

No source may move to `APPROVED` until its exact primary policy document is preserved and hashed, its issuer and applicable scope are verified, and all required uses are explicitly reviewed. Missing, ambiguous, contradictory, expired, or unverified evidence leaves the source blocked. The empty `policies` arrays are intentional and must not be interpreted as unrestricted rights.

No external synchronization, distribution, publication, upload, polling, backfill, or production capture is authorized by this inventory.
