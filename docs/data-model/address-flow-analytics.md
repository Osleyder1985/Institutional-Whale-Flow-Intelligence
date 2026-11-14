# Point-in-time address flow analytics v1

Status: implemented as an offline analytical function over supplied Movement Ledger records and synthetic fixtures. No provider access, capture, polling, backfill, persistence, or wallet clustering is enabled.

## Purpose

`summarize_address_flows` calculates gross confirmed transfer inflows, gross confirmed transfer outflows, and their net difference for each supplied BTC or ETH address during a caller-selected event-time window. It applies a separate `known_at_utc` cutoff using each movement's `recorded_at_utc`, so records added later do not leak into an earlier as-of result.

The event-time interval is half-open: `[start_time_utc, end_time_utc)`. The knowledge cutoff is inclusive: a record with `recorded_at_utc == known_at_utc` is visible.

## Eligibility and exclusions

- Movement quality must be `VALID` or `PARTIAL`; `QUARANTINED` is excluded.
- Confirmation must be exactly `CONFIRMED`; `PENDING` and `UNKNOWN` are excluded.
- Amount must be present as a canonical decimal string. Missing amount is excluded, never treated as zero.
- A missing endpoint contributes only to the known endpoint and increments an explicit coverage-gap counter. A movement with both endpoints missing contributes to no address.
- Duplicate `movement_id` values fail closed rather than double-count.
- Ethereum addresses are normalized to lowercase because EVM address comparison is case-insensitive. Bitcoin address strings are preserved because Base58 is case-sensitive.

## Output semantics

For each address and asset:
- `incoming_amount`: sum of confirmed amounts where the address is the recipient.
- `outgoing_amount`: sum of confirmed amounts where the address is the sender.
- `net_flow_delta`: incoming minus outgoing within the supplied records and time window.
- Incoming/outgoing movement counts count each eligible movement endpoint.

The output is **not a wallet balance**. It is only the net transfer flow visible in the supplied Movement Ledger records. It does not subtract transfers between addresses under common control, because no verified wallet-cluster/control input is consumed. A self-transfer therefore preserves gross in/out and has zero net flow.

## Epistemic and operational limits

- A transfer is not a buy, sell, executed trade, or proof of beneficial ownership.
- Address-level flow does not identify an institution or whale.
- No whale threshold, cohort, accumulation/distribution label, confidence score, or price-impact claim is generated.
- The function does not query a blockchain node or external provider.
- Coverage is bounded by the supplied movement records; absence of a movement is not evidence of no activity.
- The function is deterministic and uses `Decimal` arithmetic; it does not write files or mutate input records.

## Verification

Run:

```powershell
python -m unittest tests.test_address_flow_analytics -v
```

The tests cover exact arithmetic, BTC/ETH address handling, half-open event windows, point-in-time knowledge cutoffs, confirmation and quality exclusions, missing values/endpoints, duplicate IDs, and invalid input.
