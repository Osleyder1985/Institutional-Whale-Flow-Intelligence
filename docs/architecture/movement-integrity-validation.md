# Movement integrity validation

Status: first deterministic validator; synthetic fixtures only.

The repository contract-test workflow runs for every pull request without path-based filtering. A change to shared contracts or validation code must therefore be checked even when it does not modify a schema or test directory.

## Input contract

`validate_movement_integrity(movement, observations, claims, known_claim_ids=())` receives one normalized movement, a collection of source-observation records and a collection of attribution claims. It returns a list of integrity errors and does not mutate any input. Claims are checked with `validate_claim_collection` before their attribution data is used. For a partial claim batch, `known_claim_ids` identifies superseded claims already resolved in persistent history.

This component is deliberately provider-neutral. It consumes the canonical contracts; it does not call providers, query a blockchain, infer labels, or persist data.

## Source-observation checks

For every referenced `source_observation_id`, the validator requires:
- The observation exists in the supplied evidence set.
- Its type is `ON_CHAIN_TRANSACTION`.
- Its quality is not `INVALID`, `QUARANTINED`, or `DUPLICATE`. A duplicate must be resolved to its canonical observation before ledger construction.
- Asset ID, symbol and network match the movement.
- It contains a `TRANSFER` movement.
- Any source facts that are present (amount, unit, addresses, transaction ID, confirmation status and event time) do not conflict with the normalized movement.
- A known source fact cannot be dropped, and a movement fact cannot be populated when all referenced sources lack that fact.
- Source quality states `VALID`, `PARTIAL` and `DELAYED` are admissible for historical integrity/reconstruction; `INVALID`, `QUARANTINED`, `DUPLICATE` and unrecognized states fail closed. `DELAYED` remains `DELAYED` and is not evidence of real-time availability. This validator does not evaluate freshness or real-time eligibility.
- A non-null movement event time must be supported by at least one referenced observation with a matching event time.

Amounts must be canonical non-negative decimal strings; exponent notation, signs, leading zeroes and non-string numeric values are rejected. Valid amounts are compared with decimal arithmetic, never binary floating point. Different canonical textual decimal representations with equal numeric value are accepted; the stored source and ledger strings remain unchanged.

Aggregate `EXCHANGE_FLOW_METRIC` and `ETF_FLOW_METRIC` observations are rejected as transfer provenance. They are measurements, not individual transfers.

## Attribution checks

For each attribution resolution:
- The referenced claim must exist, unless the resolution explicitly says `CLAIM_NOT_FOUND`.
- The claim subject must be an ADDRESS and match the resolution address.
- The address must be one of the transfer endpoints and the claim network must match the movement network.
- Predicate, object type, object ID and epistemic status must match the canonical claim exactly.
- Temporal status is recomputed from the claim's validity interval and the movement's event time.

All timestamps are accepted only in the canonical UTC form `YYYY-MM-DDTHH:MM:SSZ`, including valid calendar dates; offsets and abbreviated timestamps are rejected. Both validity bounds are required for `VALID_AT_EVENT_TIME`. A known start can still prove `NOT_YET_VALID`; a known end can still prove `EXPIRED_AT_EVENT_TIME`. A missing bound is not interpreted as infinite. Reversed, malformed or non-UTC intervals resolve to `TIME_UNRESOLVED`.

Temporal validity does not upgrade epistemic status. A provider-labelled claim remains provider-labelled. Collection validation also rejects duplicate claim IDs, unresolved supersession references, self-supersession, cycles in the supplied claim batch, and a successor recorded before its included predecessor. Duplicate claim IDs are excluded from attribution lookup; no record is selected by input order. Partial batches must explicitly resolve external predecessor IDs with `known_claim_ids`.

## Error semantics and limitations

Errors are returned as deterministic strings suitable for tests and later structured error codes. Malformed top-level movement/collection inputs and non-object evidence records return validation errors rather than raising attribute/type errors. The component does not auto-correct, discard, merge, or quarantine records; callers must decide how to handle a failed validation without erasing evidence.

The first version does not:
- Resolve duplicate transactions across providers.
- Prove that a provider's transfer observation is truthful.
- Infer exchange ownership or beneficial ownership.
- Reconstruct internal transfers, trades, deposits, withdrawals, or user intent.
- Treat missing values as zero or fill them from heuristics.
- Validate chain-specific transaction finality or reorg depth.

## Tests

Cross-contract tests use isolated synthetic source observations plus the existing synthetic attribution claims. They cover missing references, aggregate metrics used as transfers, source mismatches, unsupported values, admissible historical `DELAYED` evidence without quality promotion, inadmissible quality states, attribution mismatch and temporal interval resolution.
