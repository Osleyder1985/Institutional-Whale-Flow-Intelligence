# Evidence-gated entity flow analytics v1

Status: implemented analytical function; not yet validated against real blockchain samples.

## Purpose

`iwfi.entity_flow_analytics.aggregate_entity_flows` converts eligible BTC/ETH Movement Ledger transfers into entity-level external flow only when an existing Attribution Claim explicitly and temporally supports the address-to-entity relationship.

The function consumes Movement Ledger records and the canonical append-only claim collection. It does not create claims, discover clusters, merge entities, query a chain, or persist results. The current directed-flow implementation is restricted to Ethereum native transfers; Bitcoin UTXO_VOUT records are explicitly excluded until transaction-level input/output accounting is implemented under Issue #109.

## Attribution admission policy

An address is attributed only when a claim satisfies all of the following:

- subject is the exact address on the movement's network;
- predicate is `CONTROLLED_BY`;
- object is an `ENTITY`;
- epistemic status is `VERIFIED`;
- review status is `REVIEWED`;
- supporting evidence is present and counterevidence is empty;
- both `recorded_at_utc <= known_at_utc` and `review.reviewed_at_utc <= known_at_utc`;
- both validity boundaries are present and the movement event time falls within the inclusive interval.

The strict policy deliberately abstains on open-ended validity intervals because the existing contract defines null boundaries as unresolved, not infinite. `OPERATED_BY` is also excluded from this address-control metric because operational responsibility is not proof of control of address keys. `LABELLED_AS`, `ASSOCIATED_WITH`, `MEMBER_OF` and `CUSTODIED_BY` are likewise excluded. Provider labels, inferences and unknown claims remain visible in the source claim ledger but do not contribute entity flows.

If applicable verified claims point to more than one entity, the address is `CONFLICT` and is not attributed. A disputed claim blocks attribution. The function never resolves conflicts by input order, provider ranking, transfer proximity or label similarity.

## Transfer accounting

- Event window: half-open `[start_time_utc, end_time_utc)`.
- Knowledge cutoff: movement and claim `recorded_at_utc <= known_at_utc`.
- Claim validity: inclusive `[valid_from_utc, valid_to_utc]`.
- Only `VALID/PARTIAL`, confirmed transfers with a known positive decimal amount are included.
- Ethereum native transfers are supported in this first directed-flow implementation. Bitcoin UTXO_VOUT is excluded with `unsupported_utxo_accounting`; a UTXO output has a recipient but no unique sender, so treating it as a directed transfer would fabricate input-to-output pairing. See Issue #109.
- EVM addresses are compared case-insensitively; Bitcoin address strings remain case-sensitive.
- An attributed source and destination resolving to the same entity form an internal transfer. The amount is reported in `internal_transfer_volume` and is excluded from external incoming, outgoing and net flow.
- Transfers between different attributed entities count once as outgoing for the source entity and once as incoming for the destination entity. This is two entity-side views of one transfer, not two distinct chain transfers.
- When only one endpoint is attributed, its external flow is recorded and the other side is explicitly counted as an unknown counterparty.
- Conflicted or unknown endpoints are never assigned to an entity.

## Output interpretation

`external_net` is net external transfer flow over the supplied movement set. It is not an absolute balance, beneficial ownership estimate, executed trade, or proof of accumulation/distribution.

Absolute historical exposure requires independently evidenced opening balances or point-in-time balance snapshots plus complete movement coverage, chain-specific accounting (including Bitcoin UTXO change handling), and attribution history. This module does not derive balances by cumulatively summing an incomplete movement feed.

## Test boundary

Unit tests use constructed records only to verify deterministic accounting rules. They are synthetic software tests, not blockchain samples and not evidence of market activity.

Real-data acceptance remains blocked until an approved source path supplies a reproducible sample with:
- network, block height/hash and canonicality/finality evidence;
- transaction hash and event locator (Bitcoin output index or Ethereum trace/value semantics);
- event timestamp and retrieval/recording timestamp;
- raw source references or retained artifacts permitted by the applicable source terms;
- normalized movements reconciled to the source sample;
- pre-existing claims with admissible evidence, or explicit UNKNOWN attribution where no qualifying claim exists.

No real-data success, provider approval, or production readiness is claimed by this implementation.
