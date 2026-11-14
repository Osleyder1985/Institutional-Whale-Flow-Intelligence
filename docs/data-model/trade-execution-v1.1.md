# TradeExecution v1.1 — Multi-role participant references

Status: proposed, versioned contract on the Issue #77 / PR #78 branch. The v1.0 schema remains unchanged.

## Why a new TradeExecution version

TradeExecution v1.0 uses a singular participant summary and `attribution_claim_ids`. That shape cannot authoritatively represent multiple independent participant roles in one execution. Adding a new optional field to a closed v1.0 schema would also break strict consumers that reject additional properties.

v1.1 therefore has a separate schema file: `schemas/trade-execution-v1.1.schema.json`.

## v1.1 invariants

- The execution primary key is `execution_id`, consistent with the canonical TradeExecution contract. Role claims reference this exact ID.
- `participant_role_claim_ids` contains zero or more unique references to `ExecutionParticipantRoleClaim` records.
- Every claim for this execution must be referenced by the execution, and every reference must resolve to a claim for this same execution.
- The old singular summary fields remain in the v1.1 record only for structural compatibility and must stay UNKNOWN/null/empty:
  - `participant_attribution_status = UNKNOWN`
  - `participant_actor_id = null`
  - `participant_side = UNKNOWN`
  - `attribution_claim_ids = []`
- Participant role and side are derived from the referenced role claims at query time; the summary fields are not an alternate source of truth.
- An execution with no participant claims is valid. The execution itself may still be confirmed by venue evidence.

## Validation boundary

`validate_execution_participant_role_links` checks:
1. TradeExecution version and non-empty `execution_id`.
2. Unique, non-empty `participant_role_claim_ids`.
3. No legacy singular attribution on v1.1.
4. Exact bidirectional equality between the execution's claim references and claims whose `execution_id` matches.
5. Every referenced claim's actor and source-observation references, role/side semantics, evidence, and timestamps through the v1.1 claim validator.

The point-in-time resolver accepts the canonical TradeExecution object and filters claims by both `known_at_utc` and `recorded_at_utc` relative to the system cutoff, then by validity at `event_time_utc`.

## Compatibility

- TradeExecution v1.0 and its schema/validator are not modified.
- v1.1 consumers must use the v1.1 schema and role-claim validator together.
- No automatic migration of v1.0 records is performed.
- Legacy singular attribution is not copied into multi-role claims without new evidence.

All examples and fixtures are synthetic. No real data capture, providers, polling, backfills, or paid services are enabled.
