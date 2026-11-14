# IWFI Execution Participant Role Claim v1.1

Status: proposed contract on Issue #77 branch; synthetic fixtures only. This contract supplements the v1 buyer/seller attribution claim and does not silently reinterpret v1 records.

## Purpose and cardinality

A `TradeExecution` represents one observed execution. An `ExecutionParticipantRoleClaim` represents one evidence-backed assertion about one actor's role in that execution.

- One trade may have zero, one, or many role claims.
- Claims for different roles coexist independently: for example BUYER, BROKER, EXECUTING_VENUE and CUSTODIAN.
- A trade's `aggressor_side` remains a venue/microstructure property. It does not identify a participant.
- Participant claims are not collapsed into one authoritative actor or side on the TradeExecution record.
- A trade with no participant claims remains a valid observed execution; no actor is inferred from the aggressor side.

## Claim fields

| Field | Meaning |
|---|---|
| `claim_id` | Stable unique ID for this claim |
| `execution_id` | Exactly one individual TradeExecution |
| `actor_id` | Actor Registry reference, or null when identity is unknown/disputed |
| `candidate_actor_ids` | Candidate actors only for DISPUTED claims; never a selected winner |
| `participant_role` | The actor's role in this specific execution |
| `participant_side` | BUY, SELL, NOT_APPLICABLE or UNKNOWN; distinct from aggressor side |
| `epistemic_status` | DIRECT, INFERRED, UNKNOWN or DISPUTED |
| `attribution_method` | Evidence method; NONE for UNKNOWN and CONFLICT_REVIEW for DISPUTED |
| `known_at_utc` / `recorded_at_utc` | Bitemporal knowledge and recording timestamps |
| `valid_from_utc` / `valid_to_utc` | Real-world validity interval; must cover event time for DIRECT/INFERRED |
| `source_observation_ids` | Unique canonical source observation references |
| `supporting_evidence` / `counter_evidence` | Separate evidence and counterevidence references |

All timestamps are strict UTC strings with a trailing `Z`. Amounts are not duplicated in participant claims; quantities and prices remain on TradeExecution.

## Role and side semantics

- BUYER requires participant_side=BUY.
- SELLER requires participant_side=SELL.
- BROKER, EXECUTING_VENUE, CUSTODIAN, CLEARING_PARTICIPANT, FUND, ASSET_MANAGER, BENEFICIAL_OWNER and OTHER require NOT_APPLICABLE or UNKNOWN.
- UNKNOWN is a role placeholder only when the role itself is unknown.
- A participant identity may remain UNKNOWN even when the trade is confirmed.
- A public aggressor side alone creates no participant role claim.

## Evidence and attribution rules

DIRECT requires participant-specific evidence such as an official named execution disclosure, venue participant disclosure or authorized account link. A provider label, wallet movement, custody relationship, exchange deposit, or aggregate flow cannot alone support DIRECT attribution.

INFERRED remains explicitly inferred and must retain supporting evidence and its method. It is never promoted to DIRECT by confidence or repetition alone.

UNKNOWN has no selected actor or candidate and uses method NONE. DISPUTED has at least two known candidate Actor IDs, no selected actor, and counterevidence. Conflicts are resolved per trade and role; different roles do not conflict merely because they name different actors.

BENEFICIAL_OWNER requires explicit evidence of economic ownership. It is not inferred from CUSTODIAN, BROKER, ASSET_MANAGER, FUND, venue, exchange or wallet relationships.

## Point-in-time resolution

A claim is eligible only when:
1. its `known_at_utc` is not later than the requested as-of cutoff; and
2. its validity interval covers the trade's `event_time_utc`.

The resolver groups eligible claims by participant role. Multiple compatible roles coexist. Different actors or sides for the same role resolve to DISPUTED; input order never chooses a winner. Malformed relevant claims cause INVALID_INPUT and abstention rather than silent omission.

## Integration boundary

This v1.1 contract is separate from:
- Source Observation (#6), which provides provenance;
- generic Address/Entity Attribution Claims (#8), which do not prove participation in a trade;
- Actor Registry (#41), which supplies Actor IDs;
- TradeExecution (#43/#51), which proves an individual execution occurred;
- Movement Ledger (#10), which records transfers, not trades.

Fixtures are synthetic BTC/ETH examples only. No provider, credentials, capture, polling, backfill, production persistence or paid service is enabled.
