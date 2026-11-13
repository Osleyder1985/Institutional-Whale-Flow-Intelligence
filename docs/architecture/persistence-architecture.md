# ADR-0001: Auditable and Versioned Persistence Architecture

- Status: Proposed
- Date: 2026-11-13
- Related issue: #16
- Scope: BTC and ETH source observations, attribution claims, movement events, resolution decisions, and user-requested research snapshots
- Decision owner: IWFI project owner

## 1. Context

The following provider-neutral contracts are integrated:

- Source Observation v1.1.0
- Entity Attribution contract
- Movement Ledger with an explicit, nullable transfer event locator
- Observation Resolution policy 1.3.2

Persistence must preserve the evidence and decisions described by these contracts. A database schema must not redefine event identity, quality semantics, attribution status, or resolution rules.

This ADR is a design proposal. It does not select a production database, create a backend, connect a provider, or authorize ingestion.

## 2. Non-negotiable invariants

1. **Evidence preservation:** each source observation remains independently addressable with provider, endpoint, record reference, payload hash, event time, retrieval time, schema version, quality, and retention classification.
2. **No silent overwrite:** corrections and provider revisions create new records or versions and explicit supersession links. Historical observations and decisions are not updated in place.
3. **Retention-aware immutability:** append-only history is the default logical model, subject to documented legal/provider retention duties. Raw payloads are not stored unless the applicable terms explicitly permit it.
4. **Transfer identity:** a movement is not a transaction. Strong transfer identity uses network + normalized transaction ID + protocol-specific event locator when known.
5. **Unknown identity stays unknown:** a null event locator is not derived from a transaction hash. A record without a strong event key cannot be forced into a unique canonical movement by amount, address, or timestamp similarity.
6. **No evidence laundering:** INVALID and QUARANTINED observations remain auditable but do not contribute to resolved field values. DUPLICATE observations remain linked and traceable without being counted as additional evidence.
7. **Decision reproducibility:** each resolution decision records policy version, exact input set/fingerprint, output, conflicts, and supersession context.
8. **Temporal attribution:** attribution claims and their validity intervals are versioned. A current label is never projected backward without evidence.
9. **Semantic separation:** aggregate exchange/ETF metrics are not stored as individual transfers. Transfers are not trades, purchases, or sales.
10. **Explicit execution:** ingestion, resolution, and research runs are initiated by the user. No polling, background market analysis, or backfill is enabled by this design.

## 3. Logical persistence model

The following is a logical model, not a committed SQL schema. Physical tables, column types, partitions, and indexes depend on the selected storage engine.

| Logical entity | Purpose | Mutability rule |
|---|---|---|
| SourceObservation | Immutable provider observation envelope and permitted normalized facts | Insert new observation/version; do not overwrite |
| ObservationRevisionLink | Links a revised provider record to its predecessor | Append-only |
| AttributionClaim | Address/entity claim, provenance, epistemic status, and validity interval | New claim/version for corrections |
| Movement | Canonical individual transfer with network, transaction ID, nullable event locator, amount, endpoints, and event time | New movement version only when a documented correction is accepted |
| MovementObservationLink | Links observations to a movement as supporting, candidate, duplicate, or conflicting evidence | Append-only; decision-versioned |
| ResolutionDecision | Deterministic result for a defined input set and policy version | Append-only |
| FieldEvidence | Source/value/provenance contributing to each resolved field | Append-only per decision |
| MovementConflict | Material identity or field contradiction and affected records | Append-only |
| ProviderTermsRecord | Provider, endpoint, terms version/date, access, retention and derived-data permissions | Append-only snapshots |
| ResearchSnapshot | User-requested evaluation with exact source/decision/policy/software versions | Immutable result; reruns create new snapshots |

### 3.1 Relationships

- One SourceObservation may be evaluated against multiple candidate movements while identity is unresolved, but may be confirmed as supporting evidence for at most one movement identity. Conflicting identity claims remain explicit conflicts and cannot cause double-counting.
- One Movement may be supported by multiple SourceObservations only after strong event identity has been established.
- One ResolutionDecision consumes a deterministic set of observation IDs and produces versioned links, field evidence, conflicts, and eligibility.
- One AttributionClaim may apply to an address only during its recorded validity interval; the movement event time determines temporal resolution.
- One ResearchSnapshot references the exact decisions and metric definitions used. It does not recalculate or overwrite prior snapshots.

## 4. Idempotency and uniqueness

### 4.1 Source observations

- observation_id is unique within IWFI.
- A provider record identity can use provider + endpoint + provider record ID when the provider supplies a stable record ID.
- A changed payload hash for the same provider record is a revision, not an exact duplicate; preserve both versions and link them.
- When provider record ID is absent, payload hash and source context may support a repeat relation, but must not be promoted to strong transfer identity.

### 4.2 Transfer events

A strong event key is available only when all required components are known:

(network_id, normalized_transaction_id, normalized_event_locator)

Examples:
- Bitcoin native output: UTXO_VOUT
- Ethereum native internal transfer: EVM_TRACE_PATH
- Ethereum transaction-level native value transfer: EVM_TX_VALUE

A null locator means no strong event key. Do not enforce a uniqueness constraint that merges all null-locator rows for the same transaction. Such observations remain candidates or unresolved records according to policy 1.3.2.

The transaction hash alone is never a unique movement key. Distinct outputs/traces inside the same transaction remain separate movements.

### 4.3 Resolution decisions

A decision identity should be derived from:
- policy version;
- canonical, sorted observation identifiers and payload hashes;
- relevant claim/history context;
- normalized resolver configuration.

The same inputs and policy version must return the same decision identity and content. A changed input set or policy version creates a new decision, linked to the prior decision where applicable.

## 5. Transaction boundaries

The design should provide atomicity for these logical operations:

1. **Manual observation intake:** validate the complete batch, then commit observations and provenance together; invalid batches must not leave partially indexed records.
2. **Resolution run:** read a stable input snapshot, execute the pure resolver, and commit the decision, links, field evidence, and conflicts atomically.
3. **Claim correction:** append the new claim/revision and supersession relation together; preserve the prior claim.
4. **Research snapshot:** store the exact input decision IDs, metric definitions, software version, time window, and output as one reproducible unit.

Retries must be idempotent. Concurrent runs over the same inputs must not create semantically different decisions or duplicate movements.

## 6. Storage options

| Option | Strengths | Risks / costs | Fit |
|---|---|---|---|
| PostgreSQL | Relational constraints, transactions, concurrent writers, temporal/query support, JSONB for bounded provider extensions, mature backup and migration tooling | Requires a managed or self-operated service, credentials, network access, backup operations and cost control | Strong candidate if desktop/mobile clients share one authoritative dataset |
| SQLite | Embedded, low operational cost, portable, transactional, good for local-first/offline prototypes | Multi-device synchronization, concurrent remote writers, central access control and conflict resolution become additional system responsibilities | Candidate if local-first/offline operation is a primary requirement |
| Append-only files/object storage | Simple evidence archive, low-cost immutable objects, easy content-addressing | Weak relational constraints, complex joins, idempotency catalog, transactional linking, concurrent updates and query indexing | Useful as a permitted raw/archive layer, not sufficient alone as the canonical ledger |

### 6.1 Provisional direction

A relational database is the leading category for the canonical ledger because the system needs referential integrity, transactions, temporal claims, deterministic decision records, and multi-client access.

PostgreSQL is the leading candidate if IWFI requires one shared authoritative dataset across clients. SQLite remains viable if the product is explicitly local-first and synchronization is separately designed. Neither choice is approved by this ADR.

A hybrid PostgreSQL + object-storage design may be considered only if provider terms permit the exact raw object retention and a separate evidence-retention policy exists. No raw-payload bucket is assumed.

## 7. Query and indexing requirements

The eventual physical design must support:
- observation lookup by observation ID, provider/endpoint/record ID, payload hash, asset/network, and event/retrieval time;
- movement lookup by network + transaction ID + event locator when complete;
- explicit unresolved/candidate lookup for missing locators or insufficient identity;
- bidirectional movement/observation/decision traceability;
- claims by address, network, epistemic status, and validity interval;
- conflicts and analytical eligibility by decision version;
- research snapshots by user, asset, time window, and software/policy version.

Indexes must be justified by query workloads and measured cardinality. Do not add speculative indexes or partitioning before workload evidence exists.

## 8. Retention, security, and operations

- Retention classification is enforced before any raw payload write.
- The default for unapproved provider terms is normalized-only/hash-only as permitted by the contract; no raw payload retention.
- Store credentials outside the database and never in source files, logs, or fixtures.
- Require least-privilege service identities, encrypted transport, encrypted backups, and auditable administrative access.
- Define retention expiry and lawful deletion/cryptographic erasure procedures before production. Logical append-only history does not override provider terms or applicable law.
- Define backup frequency, recovery-point objective, recovery-time objective, and a tested restore procedure.
- Use versioned, reviewed migrations. Test migrations against synthetic fixtures and a restorable copy before production changes.
- Do not store personal identity assumptions about public addresses; provider labels remain claims with provenance.

## 9. Explicitly unresolved dependencies

The current contracts do not define all chain-finality and reorganization behavior. Before production persistence, a separate decision must define:
- block height/hash and observation confirmation context;
- how a reorg changes a previously observed movement;
- whether a movement is marked orphaned/reverted, superseded, or re-observed;
- how resolution decisions and research snapshots preserve pre- and post-reorg history.

No finality depth, confirmation threshold, or reorg duration is invented here.

Other unresolved inputs include expected event volume, retention duration by provider, multi-device/offline requirements, deployment location, recovery objectives, and actual query workloads.

## 10. Validation plan before backend implementation

The implementation plan must include synthetic tests for:
- exact retry/idempotent insert of the same observation;
- same provider record with changed payload hash;
- same transaction with two distinct event locators;
- null locator without accidental uniqueness collision;
- two networks with identical transaction-hash text;
- competing resolution runs over the same input set;
- new observations producing a new decision without overwriting old decisions;
- INVALID/QUARANTINED evidence retained but excluded from resolved fields;
- temporal claim correction and supersession;
- interrupted transactions and retry after failure;
- backup restore and migration rollback/recovery rehearsal.

## 11. Decision gate

This ADR does not authorize:
- selecting or purchasing a database service;
- creating a production database or backend;
- provider credentials, API calls, polling, or historical backfills;
- raw payload retention;
- wallet clustering, institutional attribution, whale statistics, or buy/sell analysis.

Issue #16 remains open until requirements are measured, the options are evaluated against those requirements, unresolved finality/retention questions are assigned, and the project owner accepts the ADR. Only then should a separate implementation Issue and PR be created.
