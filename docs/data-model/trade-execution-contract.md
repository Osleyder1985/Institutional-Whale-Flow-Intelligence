# IWFI Trade Execution Contract v1

Status: proposed contract; synthetic BTC/ETH fixtures only.

## What qualifies

A TradeExecution is an individual execution supported by a venue execution record or an official disclosure that explicitly describes an individual execution. The evidence type and granularity are mandatory. Orders, quotes, RFQs, on-chain transfers, deposits, withdrawals, internal transfers, holdings changes, ETF creations/redemptions, exchange/ETF flow metrics and aggregate disclosures are not individual executions.

The schema fixes event_type to TRADE_EXECUTION and aggregation_level to INDIVIDUAL_EXECUTION. The application validator independently checks evidence type, granularity and references. It does not convert rejected inputs into executions.

## Execution and participant are independent

Execution status describes whether an execution occurred or was later corrected/cancelled/busted. Participant attribution status describes whether a participant can be named. An EXECUTED trade may have participant attribution UNKNOWN.

aggressor_side describes the side consuming liquidity under the venue's documented semantics. participant_side describes the side of an identified participant. They are separate fields and must never be copied from one another. If the participant is unknown or disputed, participant_side remains UNKNOWN.

A participant actor_id is accepted only if it exists in the Actor Registry and a separate attribution claim supports the specific execution. A provider label or wallet deposit alone is insufficient.

## Quantities and time

Quantities, price and fees use canonical decimal strings; null means unavailable, never zero. event_time, published_at, available_at, ingested_at and computed_at are preserved in UTC. Their chronological ordering is validated; event time is not replaced by publication or ingestion time.

## Evidence and limitations

source_observation_ids refer to the execution-evidence records supplied to the validator. Each source_evidence item must identify an individual execution record or official disclosure. This contract does not assert that every venue exposes customer identity, nor that public trade feeds identify the aggressor's beneficial owner.

No provider integration, API credentials, polling, backfill, order placement, investment recommendation or price-impact inference is included.
