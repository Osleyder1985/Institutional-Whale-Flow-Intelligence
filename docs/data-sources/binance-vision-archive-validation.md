# Binance Vision Spot aggTrades archive validation

Status: local validation utility implemented under Issue #65. This is not approval to download, retain, redistribute, or activate a source adapter.

## Scope

The utility validates one already-obtained Spot `aggTrades` ZIP archive and its published SHA-256 checksum. It uses Python standard library only. It performs no network access, polling, backfill, extraction to disk, or payload persistence.

Expected archive names:
- `{SYMBOL}-aggTrades-{YYYY-MM-DD}.zip`
- The ZIP must contain exactly `{SYMBOL}-aggTrades-{YYYY-MM-DD}.csv`

The CSV is headerless and must contain the eight fields documented by Binance Public Data:
1. Aggregate trade ID
2. Price
3. Quantity
4. First trade ID
5. Last trade ID
6. Timestamp
7. Whether buyer was maker
8. Whether trade was best price match

## Timestamp unit

For Binance Spot archive records:
- Dates before 2025-01-01 are interpreted as milliseconds.
- Dates on or after 2025-01-01 are interpreted as microseconds.

Every timestamp must fall within the UTC calendar day encoded in the archive filename. The validator does not infer timezone from the local machine.

## Run locally

```powershell
python -m iwfi.binance_vision_archive_validator --zip BTCUSDT-aggTrades-2026-11-12.zip --checksum BTCUSDT-aggTrades-2026-11-12.zip.CHECKSUM --symbol BTCUSDT --date 2026-11-12
```

The command prints a JSON summary and exits with code 0 only when checksum, ZIP member, and every CSV row pass validation. It does not write an output file.

## Safety and epistemic limits

- Price and quantity are validated as decimal strings; they are never converted to binary floating point.
- The ZIP member is read in streaming mode and never extracted to disk.
- A valid checksum proves file integrity against the supplied checksum, not authenticity of the source by itself.
- The utility does not prove legal rights, account entitlement, or source availability.
- It does not identify a customer, institution, fund, bank, whale, beneficial owner, or either counterparty.
- AggTrades are aggregate records, not a guaranteed one-row-per-individual-fill representation.
- The output explicitly leaves actor attribution UNKNOWN.
- Tests use synthetic fixtures only. They do not constitute validation of real BTCUSDT or ETHUSDT Binance files.

## Remaining evidence

Issue #3 remains open until real BTCUSDT and ETHUSDT sample archives are obtained through the approved Binance Vision route, their published checksums are verified, the utility passes them, and source terms/retention conditions are recorded for the exact use.
