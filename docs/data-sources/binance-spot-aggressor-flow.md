# Binance Spot aggressor-flow metrics

Status: implementation candidate for Issue #100. This module is an offline analytics step; it does not approve a source, download data, or authorize retention.

## Purpose and input

`iwfi.binance_spot_flow_metrics` processes one locally available Binance Vision Spot `aggTrades` ZIP and its `.CHECKSUM` file. It calls the Issue #65 archive validator before calculating metrics, streams the CSV from the ZIP, and emits a deterministic JSON document to stdout. It does not extract files, write payloads/results, access the network, poll, or backfill.

## Aggressor-side convention

The Binance Spot `aggTrades` record includes `isBuyerMaker`:

- `false`: the buyer was not the maker; the buyer was the taker/aggressor. Add quantity and price × quantity to taker-buy volume.
- `true`: the buyer was the maker; the seller was the taker/aggressor. Add quantity and price × quantity to taker-sell volume.

Price, quantity, notional, and signed deltas use `Decimal`. JSON numeric measures are emitted as decimal strings. `aggregate_trade_count` counts aggTrades records, not individual fills.

## Metrics

For the full archive day, and optionally for caller-selected UTC buckets:

- taker buy/sell base quantity;
- taker buy/sell quote notional;
- signed base/quote volume delta (buy minus sell);
- cumulative signed volume across observed buckets;
- aggregate record count and first/last event timestamps.

The interval must be a positive integer number of seconds that divides 86,400. No optimal interval, threshold, or predictive weight is selected by the implementation.

Buckets with no records are not silently assigned zero flow. The output reports `unobserved_interval_count` and labels those intervals `ZERO_ACTIVITY_NOT_PROVEN`; absence of records alone does not establish zero activity or complete coverage.

## Run

```powershell
python -m iwfi.binance_spot_flow_metrics `
  --zip BTCUSDT-aggTrades-2026-11-13.zip `
  --checksum BTCUSDT-aggTrades-2026-11-13.zip.CHECKSUM `
  --symbol BTCUSDT `
  --date 2026-11-13 `
  --interval-seconds 300
```

Omit `--interval-seconds` to produce one full-day bucket. Output is stdout only.

## Interpretation limits

- These metrics describe observed aggressor-side activity on one Binance Spot market only.
- aggTrades are aggregated trade records, not guaranteed individual fills.
- They do not identify a customer, institution, fund, whale, beneficial owner, or counterparty.
- They are not on-chain transfers, exchange reserve flows, ETF flows, or proof of institutional buying/selling.
- They do not establish intent, accumulation, distribution, causality, or predictive value.
- Data gaps and unobserved intervals remain explicit; they are not converted to zero.

## Source and authorization boundary

The implementation performs no acquisition. A local input file must already have been obtained and retained under the applicable source-use and retention approvals. Issue #3 and Issue #71 remain open until real BTCUSDT and ETHUSDT samples are verified and the operational retention gate is satisfied.

Official references:
- https://github.com/binance/binance-public-data/blob/master/README.md
- https://github.com/binance/binance-public-data/blob/master/TERMS_AND_CONDITIONS.md
