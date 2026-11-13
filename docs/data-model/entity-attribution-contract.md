# IWFI Entity Attribution Claim Contract v1

Status: proposed evidence model; not a wallet-resolution engine.

## Purpose

An attribution claim is a sourced, time-scoped assertion about an address or an IWFI entity. It is not a direct declaration of legal identity, beneficial ownership, or control unless the claim's evidence and review policy support that exact predicate.

Claims are append-only. A correction, changed label, or new evidence creates a new claim. The new claim may point to the prior claim through `supersedes_claim_id`; the old record is not rewritten.

## Typed subjects and objects

- `ADDRESS`: a network-qualified address. Address identity is scoped to its network; identical strings on different networks are not interchangeable.
- `ENTITY`: an opaque IWFI entity identifier. It is an internal grouping key, not proof of a legal person or company.
- `CLASSIFICATION`: a category/label such as `exchange`, `custodian`, or `unknown`. It is not an entity identity.

Entity names and labels are descriptive claims, not primary keys. Never merge entities solely because provider labels or display names match.

## Directed predicates

Predicates are directional and must not be reversed or transitively expanded:

- `LABELLED_AS`: subject has a source-supplied or reviewed classification.
- `CONTROLLED_BY`: subject is asserted to be controlled by the target entity.
- `OPERATED_BY`: subject is asserted to be operated by the target entity.
- `ASSOCIATED_WITH`: a relationship is asserted without claiming control or operation.
- `MEMBER_OF`: subject is asserted to belong to an entity/group.
- `CUSTODIED_BY`: subject is asserted to be in the custody of the target entity.

The schema constrains target types for these predicates. A label is not a control relationship. An on-chain transfer does not prove common control, common ownership, or an entity relationship.

## Epistemic status

- `VERIFIED`: reviewed claim supported by explicit evidence for the exact predicate.
- `PROVIDER_LABELLED`: label supplied by a named provider; not independently verified.
- `INFERRED`: an explicit inference with rationale and supporting evidence.
- `UNKNOWN`: available evidence does not support an attribution.
- `DISPUTED`: material counterevidence or incompatible claims exist.

No numeric confidence score is defined. Do not silently promote `PROVIDER_LABELLED`, `INFERRED`, or `UNKNOWN` to `VERIFIED`.

Every claim also records review provenance. `UNREVIEWED` claims must have null reviewer metadata; `REVIEWED` and `DISPUTED` claims require a reviewer identifier and a UTC review timestamp. `recorded_at_utc` is not a substitute for the time at which a review decision was made.

## Evidence and provenance

Each claim records source/provider, endpoint, source record ID, and related canonical observation IDs where available. Supporting evidence and counterevidence are separate arrays. Each evidence reference includes a source, evidence type, reference ID, and optional observation ID.

A transaction observation may support the existence of a transfer. It does not, by itself, support a claim of ownership or control. Evidence must be relevant to the predicate being asserted.

## Time

`recorded_at_utc` is when IWFI recorded the claim. `valid_from_utc` and `valid_to_utc` describe the asserted period, not when IWFI learned it. All timestamps use RFC 3339 UTC ending in `Z`. A current provider label must not be projected backwards without historical evidence.

The JSON Schema checks timestamp format and UTC notation. `iwfi.attribution_integrity.validate_claim_validity_interval` checks that a supplied start does not occur after a supplied end. A null bound remains unknown and is not treated as an infinite timestamp.

## Append-only corrections

A new claim can reference a previous one through `supersedes_claim_id`. This does not delete or rewrite the earlier claim. The claim history must preserve both the old and new assertion and their separate evidence.

## Explicit non-goals

- No wallet clustering or entity merging by label similarity.
- No transitive closure of control, membership, or association edges.
- No legal identity resolution.
- No causal attribution of price movements.
- No buy/sell signals.
- No live provider integration, polling, backfills, or real wallet data.
