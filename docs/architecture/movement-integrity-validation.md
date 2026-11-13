# Movement integrity validation

Status: first deterministic validator; synthetic fixtures only.

## Input contract

`validate_movement_integrity(movement, observations, claims, known_claim_ids=())` receives one normalized movement, source-observation records and attribution claims. It returns a list of integrity errors and does not mutate inputs. It validates the claim collection before using claims; `known_claim_ids` resolves predecessor IDs already present in persistent history for partial batches.

This component is deliberately provider-neutral. It consumes the canonical contracts; it does not call providers, query a blockchain, infer labels, or persist data.

## Source-observation checks

For every referenced `source_observation_id`, the validator requires:
- The observation exists in the supplied evidence set.
- Its type is `ON_CHAIN_TRANSACTION`.
- Its quality is not `INVALID`, `QUARANTINED`, or `DUPLICATE`. A duplicate must be resolved to its canonical observation before ledger construction.
- Asset ID, symbol and network match the movement.
- It contains a `TRANSFER` movement.
- Any source facts that are present (amount, unit, addresses, transaction ID, confirmation status, event locator and event time) do not conflict with the normalized movement.
- A known source fact cannot be dropped, and a movement fact cannot be populated when all referenced sources lack that fact.
- Source quality states `VALID`, `PARTIAL` and `DELAYED` are admissible for historical reconstruction. `DELAYED` remains `DELAYED` and does not prove real-time availability. `INVALID`, `QUARANTINED`, `DUPLICATE` and unrecognized states fail closed.
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

All timestamps must use canonical UTC `YYYY-MM-DDTHH:MM:SSZ` with valid calendar dates. Both validity bounds are required for `VALID_AT_EVENT_TIME`. A known start can still prove `NOT_YET_VALID`; a known end can still prove `EXPIRED_AT_EVENT_TIME`. A missing bound is not interpreted as infinite. Reversed, malformed or non-UTC intervals resolve to `TIME_UNRESOLVED`.

Temporal validity does not upgrade epistemic status. A provider-labelled claim remains provider-labelled. Collection validation rejects invalid and duplicate claim IDs, unresolved or ambiguous supersession references, invalid `known_claim_ids` collections, self-supersession, cycles in the supplied batch and successors recorded before included predecessors. Duplicate IDs are excluded from graph construction so input order cannot select an arbitrary version; cycle detection is iterative.

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

Cross-contract tests use isolated synthetic source observations plus the existing synthetic attribution claims. They cover missing references, aggregate metrics used as transfers, source mismatches, unsupported values, inadmissible quality states, attribution mismatch and temporal interval resolution.


## Event identity and normalization

The ledger's transfer identity is `network_id + transaction_id + event_locator`. Transaction IDs are validated for the supported network and compared case-insensitively; Ethereum addresses are compared case-insensitively; numeric locator components are restricted to ASCII digits and normalized by removing leading zeroes. A malformed or network-incompatible locator does not compare as equal.

The resolver may retain `DELAYED` observations as historical evidence without changing their source-quality status. The validator uses the same admissible historical set. Real-time freshness remains outside this contract.
