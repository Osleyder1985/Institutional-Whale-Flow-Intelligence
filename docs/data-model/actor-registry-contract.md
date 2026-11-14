# IWFI Actor Registry Contract v1

Status: proposed contract; synthetic BTC/ETH fixtures only.

## Identity boundary

An Actor is an economic or organizational subject with a stable internal actor_id. It is not an address, wallet, wallet cluster, exchange account, custody account or beneficial owner by implication. A whale cluster is a provisional technical classification and does not assert a legal identity.

Actor type, identity status, relationship status, market relevance and activity evidence remain separate dimensions. A type such as BANK or FUND does not prove holdings, trading activity or capacity to move price.

## Aliases and ambiguity

Aliases are scoped by type and scope; they are not globally unique identifiers. The same ticker, brand or public label can refer to multiple actors. Lookup returns UNIQUE only when exactly one actor is valid and known at the requested as-of instant. Collisions return AMBIGUOUS with all candidates; unknown aliases return UNKNOWN. Input ordering never selects a winner.

## Bitemporal semantics

- valid_from_utc / valid_to_utc: when the assertion applies in the real world.
- known_at_utc: when IWFI could know the assertion.
- recorded_at_utc: when the record was persisted in IWFI.

Historical as-of lookup excludes assertions not yet known at the requested instant and actors outside their validity interval. Null validity bounds are open bounds for the actor's existence; alias claims still require their own evidence and known_at.

## Relationships and contradictions

Relationships are explicit directed edges with evidence and temporal bounds. No transitive closure is performed. Conflicting direct claims remain visible and resolve to DISPUTED; they are never settled by array order. Evidence and counter-evidence are references to existing source observations or attribution claims, not duplicated payloads.

## Coverage

Coverage is recorded per asset, network and activity type. NOT_COVERED and UNKNOWN mean that IWFI has no coverage evidence; they do not mean that the actor had no activity.

## Exclusions

No real identities, wallet clustering, provider integration, legal-identity inference, beneficiary inference, source capture, polling, backfill or price-impact claims are included.
