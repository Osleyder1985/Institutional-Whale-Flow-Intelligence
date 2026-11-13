# IWFI Source Observation Contract v1.1.0

Status: proposed contract, not a production integration.

## Purpose and boundary

This contract represents an externally sourced observation without silently converting it into a market interpretation. It is provider-neutral and initially covers Bitcoin and Ethereum. It does not select a provider, database, framework, or retention policy.

A source observation is an immutable record of what a source reported at a point in time. Corrections or later provider revisions create a new observation/version; they do not overwrite historical evidence.

## Required envelope

| Field | Meaning | Rule |
|---|---|---|
| contract_version | Contract version | Exact semantic version string |
| observation_id | IWFI stable identifier | Unique within IWFI |
| source.provider | Provider identifier | Stable slug |
| source.endpoint | Endpoint/product identifier | No credentials or secret query parameters |
| source.record_id | Provider record identifier | Nullable when provider supplies none |
| source.payload_sha256 | SHA-256 of source representation | Lowercase 64-character hex; does not grant raw retention rights |
| source.schema_version | Provider schema version | Nullable if undocumented |
| asset | Asset and network identity | Symbol alone is insufficient |
| event_time_utc | Time the observation refers to | RFC 3339 UTC ending in Z; nullable only when unavailable |
| retrieved_at_utc | Time IWFI retrieved the record | RFC 3339 UTC ending in Z |
| observation_type | What was observed | Explicit enum; transfer is not trade |
| movement | Transfer facts, if applicable | Amount is decimal text; event locator identifies one transfer within a transaction |
| attributions | Claims about endpoints/entities | Each claim carries status and source |
| quality | Validation/freshness state | Missing, delayed, duplicate and invalid remain distinct |
| retention | Permitted storage classification | Raw payload retention is not presumed |

## Asset and network identifiers

- Bitcoin: asset_id=bitcoin:btc, network_id=bitcoin-mainnet.
- Ethereum: asset_id=ethereum:eth, network_id=eip155:1.

A token on Ethereum is not ETH. Token contracts and token identifiers require a later extension; do not overload ethereum:eth.

## Observation semantics

Version 1.1 retains ON_CHAIN_TRANSACTION, ADDRESS_LABEL, EXCHANGE_FLOW_METRIC, and ETF_FLOW_METRIC. Flow/ETF metrics use a separate measurement object (metric name, decimal-text value, unit, and direction); the type describes the source observation, not inferred intention.

A TRANSFER movement records observed on-chain movement between addresses. Version 1.1 adds an optional protocol-specific `event_locator`: Bitcoin `UTXO_VOUT`; Ethereum native ETH `EVM_TRACE_PATH` or `EVM_TX_VALUE`; contract `EVM_LOG_INDEX` is excluded until token assets have their own asset identity. A transaction hash without an event locator does not establish the identity of one transfer event. It does not establish an executed spot trade, beneficial ownership change, purchase, sale, accumulation, or distribution.

Exchange flow metrics are aggregate measurements reported by a source and are represented under measurement, not movement. Inflow is not a sale; outflow is not a purchase. Do not manufacture a trade record from either.

## Attribution model

Allowed statuses:

- VERIFIED: supported by evidence meeting a separately documented verification policy.
- PROVIDER_LABELLED: a provider's label, not independently verified legal identity.
- INFERRED: an explicit inference with method and evidence.
- UNKNOWN: no supported attribution.
- DISPUTED: conflicting evidence/claims exist.

Every attribution claim retains its own claim_source. Conflicting claims are represented as multiple claims; do not overwrite one with the other. Optional valid_from_utc and valid_to_utc delimit temporal scope. A current label must not be projected backwards without evidence.

## Missing values and quality

- Missing amount is not zero.
- Missing event time is not retrieval time.
- A duplicate is not silently discarded; it is marked and linked to the canonical observation when known.
- A delayed observation retains both event and retrieval timestamps.
- Partial or invalid records remain visible as partial/quarantined evidence rather than being silently normalized into complete records.

## Retention and integrity

payload_sha256 is an integrity reference, not a grant of rights. retention_classification must be RAW_ALLOWED, NORMALIZED_ONLY, HASH_ONLY, or UNKNOWN_PENDING_TERMS. Until source terms are reviewed, use UNKNOWN_PENDING_TERMS and do not store provider payloads.

## Non-goals

This contract does not define a trade ledger, buy/sell signals, wallet identity resolution, causal attribution, database schema, API polling, backfills, or provider adapters.

## Test coverage

The fixture set covers confirmed BTC and ETH transactions, provider-labelled exchange address, missing amount, duplicate, delayed retrieval, and conflicting attribution. The test suite uses Python unittest plus the pinned jsonschema Draft 2020-12 validator. It validates the schema definition and every fixture with format checking, and includes negative cases for asset/network mismatch, transfer-unit mismatch, exchange-flow-as-movement, non-UTC timestamps, and raw retention while terms are pending. These are contract tests, not production ingestion tests.
