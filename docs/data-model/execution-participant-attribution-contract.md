# IWFI Execution Participant Attribution Claim v1

Status: proposed execution-specific attribution contract; synthetic fixtures only.

## Purpose

This contract links one already validated individual TradeExecution to a named participant actor only when evidence explicitly supports that relationship. It closes a semantic gap between the TradeExecution field \`attribution_claim_ids\` and the existing address/entity AttributionClaim contract, which does not model a trade execution as a claim subject.

It does not identify beneficial ownership unless a separate explicit evidence model supports that distinct fact.

## Attribution states

- DIRECT: a source explicitly names the participant for this execution, using an official named execution disclosure, venue participant disclosure or authorized account link. The actor ID, participant side, source observation and event-time validity interval are required.
- INFERRED: an explicit, reviewable inference with method, supporting evidence and bounded event-time validity. It is not equivalent to DIRECT.
- UNKNOWN: no supported participant identity. Actor and participant side remain null/UNKNOWN.
- DISPUTED: incompatible participant claims exist. No actor or side is selected; at least two candidate actor IDs and counterevidence remain visible.

A provider address label, exchange deposit, wallet movement, custody relationship, public aggressor side or aggregate flow cannot alone establish DIRECT participant attribution.

## Time

\`valid_from_utc\` / \`valid_to_utc\` describe when the participant assertion applies; the interval must include the execution event time for DIRECT/INFERRED claims. \`known_at_utc\` records when IWFI could know the claim; \`recorded_at_utc\` records when it was persisted and cannot precede known_at. An as-of lookup excludes claims not yet known at the requested time.

## Cross-contract integrity

Before accepting claims, validate:
- execution_id resolves to one TradeExecution;
- actor_id and disputed candidate IDs resolve to Actor Registry records;
- source observation IDs resolve to canonical Source Observations;
- DIRECT evidence is participant-specific, not merely an execution print or provider label;
- event time falls inside the claim validity interval;
- duplicate attribution IDs are rejected.

Multiple active claims that name different actors or sides resolve to DISPUTED. Input order never selects a winner. An execution may remain EXECUTED while participant attribution is UNKNOWN.

## Scope

This contract is provider-neutral. Fixtures are synthetic. It does not enable provider calls, capture, polling, backfill, storage of real payloads, or trade execution.
