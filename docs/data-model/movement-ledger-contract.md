# IWFI Movement Ledger Contract v1.1

Status: proposed domain contract; synthetic fixtures only.

## Purpose and boundary

The ledger represents a normalized **on-chain transfer observation** for BTC or ETH. It does not represent a trade, order, purchase, sale, beneficial ownership event, or causal explanation for a market move.

Each record links back to one or more canonical source observation IDs. Source observations remain the provenance layer; this ledger does not copy provider payloads or transform aggregate metrics into transaction records.

## Transfer semantics

- `movement_type` is fixed to `TRANSFER`.
- Amounts are decimal strings to avoid binary floating-point loss. A missing amount is `null`, never zero.
- From/to addresses and transaction ID may be null when the source does not provide them.
- Asset, symbol, network and unit must agree for the supported BTC and Ethereum mainnet records.
- Confirmation state is descriptive; pending or unknown confirmation is not silently treated as final.
- `event_locator` is required and identifies the individual transfer within its transaction: Bitcoin output index, or Ethereum log index, trace path, or transaction native-value event.

A transfer alone does not prove a trade, exchange deposit/withdrawal, common control, ownership, or intent.

## Source observations

`source_observation_ids` is a non-empty, unique list of canonical observation IDs. Ingestion must verify that every referenced observation exists, has type `ON_CHAIN_TRANSACTION`, describes a transfer, and agrees on asset/network, transaction identity, protocol event locator and event time where those values are available.

`EXCHANGE_FLOW_METRIC` and `ETF_FLOW_METRIC` observations are aggregate measurements. They must remain in a separate measurement series and must never be materialized as individual ledger transfers.

## Attribution resolution

Attribution entries are references to existing append-only claims, not new claims. They identify the address and predicate being evaluated and preserve the claim's epistemic status.

Temporal status is resolved against the transfer's `event_time_utc` and the claim's `valid_from_utc` / `valid_to_utc`:
- `VALID_AT_EVENT_TIME`: event time and both interval boundaries are known, and the event falls within the inclusive interval.
- `NOT_YET_VALID`: event time precedes a known valid-from time.
- `EXPIRED_AT_EVENT_TIME`: event time is after a known valid-to time.
- `TIME_UNRESOLVED`: event time or required validity boundary cannot be resolved safely.
- `CLAIM_NOT_FOUND`: referenced claim is absent from the available claim set.

Interval boundaries are inclusive. A null validity boundary is treated as unresolved by this first implementation; it is not silently interpreted as an infinite/open interval. This is a conservative resolution status, not a claim that the attribution is true. A `VALID_AT_EVENT_TIME` result does not upgrade `PROVIDER_LABELLED` or `INFERRED` to `VERIFIED`. Conflicting claims remain separate.

## Quality and limitations

- `VALID`: required provenance and transfer semantics are complete enough for the contract.
- `PARTIAL`: a transfer is represented but one or more non-critical source values are missing.
- `QUARANTINED`: integrity, provenance or semantic contradictions prevent safe use; at least one limitation must explain why.

Missing data is not zero. Unknown attribution is not a negative attribution. No numeric confidence, wallet clustering, entity merging, causal inference, buy/sell signal, provider integration, polling or backfill is defined here.

## Temporal validation

The schema validates UTC timestamp notation. Application-level validation must additionally verify chronological ordering of claim intervals and evaluate event-time inclusion; JSON Schema is not used as a substitute for temporal comparison logic.

## Event identity

A transaction hash identifies a transaction, not necessarily one transfer within it. The canonical event identity is network ID + transaction ID + protocol-specific event locator. Records without a valid locator remain candidates and must not be merged into a canonical movement.
