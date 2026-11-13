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
- Chain Integrity Contract v1 for Bitcoin/Ethereum inclusion, canonicality, re-inclusion, and Ethereum finality

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
11. **Chain evidence is append-only:** block-inclusion observations and source chain-status assertions are immutable evidence; canonicality assessments are versioned interpretations, never in-place edits to observations.
12. **Network-specific chain semantics:** Bitcoin has no universal protocol FINALIZED threshold in this contract; Ethereum FINALIZED requires a captured finalized checkpoint from the same identified source covering the inclusion height. REVERTED is not used as a synonym for reorg.
13. **Snapshot temporal integrity:** each ResearchSnapshot freezes the exact chain assessment, observation IDs, policy version and software version known at run time. Later evidence requires a new assessment and new user-requested snapshot.

## 2.1 Requirements already fixed by product scope

The following are requirements, not assumptions to be selected by the storage design:

- Desktop, Android and iOS clients must read and write against the same authoritative IWFI dataset through an offline-first model: each client can work against its durable local replica while disconnected and synchronize later with the central authority.
- Initial analytical scope is BTC and ETH.
- Ingestion, resolution and research evaluations are user-initiated. This architecture does not authorize polling, scheduled market analysis or automatic backfills.
- Historical observations, attribution claims and resolution decisions must remain reproducible and traceable across clients.
- Offline operations are durable and queued locally until acknowledged by the central service. Synchronization is resumable and idempotent; duplicate delivery cannot duplicate canonical facts or decisions.
- No last-write-wins policy may overwrite evidence, movements, attribution claims, resolution decisions, chain assessments or ResearchSnapshots. Semantic conflicts remain explicit and auditable.
- A locally created ResearchSnapshot is frozen and marked local/pending until synchronized; synchronization never recalculates or mutates its historical contents.
- Provider capture requires connectivity and explicit user initiation. Offline support does not authorize background polling, automatic backfills or automatic market analysis.
- Provider retention terms constrain what may be stored. Raw payload storage remains disabled unless the exact provider/endpoint terms authorize it.
- Strong movement identity uses network, normalized transaction ID and protocol-specific event locator when all are known. Missing locators remain unresolved; they are not replaced by a synthetic key.

These requirements rule out treating disconnected local databases as the complete system. A local cache or offline queue may still be considered, but its synchronization and conflict semantics must be designed separately.

## 2.2 Requirements not yet measured

No values are invented for the following operational requirements. They must be measured or explicitly set before a production storage decision:

| Requirement | Current status | Evidence needed |
|---|---|---|
| Daily and peak observation volume | Unknown | Representative provider samples and expected ingestion cadence |
| Concurrent writers and readers | Unknown | Desktop/mobile usage scenarios and simultaneous-session tests |
| Query latency targets | Unknown | Prioritized user queries and measurable response-time objectives |
| Availability target | Unknown | Product operating expectations and deployment constraints |
| Offline-first product behavior | Confirmed | User decision recorded in Issue #22; offline work and later sync are required |
| Sync protocol, conflict handling and compatibility | Unknown | Protocol, entity-specific conflict policy, cursor, schema/policy compatibility and recovery tests (Issue #22) |
| Retention duration per provider/endpoint | Unknown | Applicable terms and documented retention review |
| Recovery point/time objectives (RPO/RTO) | Unknown | Acceptable data-loss and restoration windows |
| Deployment region and data residency | Unknown | Operational/legal requirements and cost comparison |
| Operating budget | Unknown | Hosting, backup, network and maintenance estimates |

These are decision inputs. They must not be filled with arbitrary industry defaults.

## 3. Logical persistence model

The following is a logical model, not a committed SQL schema. Physical tables, column types, partitions, and indexes depend on the selected storage engine.

| Logical entity | Purpose | Mutability rule |
|---|---|---|
| Device | Stable client installation identity and revocation/status metadata | Versioned lifecycle; revocation is explicit |
| SyncOperation | Durable operation envelope with globally unique idempotency key, device ID, schema/policy version and causal dependencies | Immutable; retry preserves the same operation ID |
| SyncCursor | Server-confirmed progress for a client/device and stream | Monotonic server-issued cursor; never infer from device clock |
| SyncConflict | Semantic conflict between concurrent or incompatible operations | Append-only; explicit resolution/supersession |
| SourceObservation | Immutable provider observation envelope and permitted normalized facts | Insert new observation/version; do not overwrite |
| ChainInclusionObservation | Immutable BTC/ETH mempool, block inclusion, block-status or finalized-checkpoint evidence with source and observed time | Append-only; each new block inclusion is a new record |
| CanonicalityAssessment | Versioned assessment over a deterministic set of chain observation IDs and policy version | Append-only; supersede by a new assessment, never overwrite |
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
- One transaction may have multiple ChainInclusionObservations across competing blocks or a later re-inclusion. Inclusion identity is distinct from transfer identity; the Movement event locator remains required to distinguish multiple transfers inside one transaction.
- One CanonicalityAssessment references exact chain observation IDs, source set, policy version, assessed time and prior assessment superseded. Conflicting source assertions remain unresolved unless the chain contract provides positive, network-specific evidence.
- One ResearchSnapshot references the exact resolution decisions, canonicality assessments, metric definitions and evidence IDs used. It does not recalculate or overwrite prior snapshots.

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

### 4.3 Chain inclusion observations and canonicality assessments

A block inclusion observation is distinct from a transfer movement. Its identity uses network + transaction ID + block hash + transaction position when available. The same transaction re-included in a different block creates a new inclusion observation; its transfer event locator remains unchanged. Source assertions about active-chain status are stored with source ID and observed time. Missing responses are not negative evidence.

A canonicality assessment identity uses chain-integrity policy version + sorted input observation IDs + normalized source context. The same inputs and policy must produce the same status/reason. New evidence or a policy change creates a new assessment linked by supersession. Multi-source disagreement remains CANONICALITY_UNRESOLVED; Bitcoin is not assigned a protocol FINALIZED status, and Ethereum finality requires same-source finalized checkpoint evidence covering the inclusion height.

### 4.4 Resolution decisions

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
| SQLite | Embedded, low operational cost, portable, transactional, strong fit for durable per-device local work and outbox | Must be paired with a defined synchronization service/protocol; local database alone is not the shared authority | Strong candidate for local client storage; not the central authority by itself |
| Append-only files/object storage | Simple evidence archive, low-cost immutable objects, easy content-addressing | Weak relational constraints, complex joins, idempotency catalog, transactional linking, concurrent updates and query indexing | Useful as a permitted raw/archive layer, not sufficient alone as the canonical ledger |

### 6.1 Comparative fit against known requirements

This is a qualitative constraint check, not a weighted score or a final selection.

| Requirement / constraint | PostgreSQL | SQLite alone | Append-only files/object storage alone |
|---|---|---|---|
| One authoritative dataset shared by desktop, Android and iOS | Fits a central service model | Does not provide shared multi-client authority without a separate sync/service layer | Does not provide safe shared transactional access by itself |
| Referential integrity across observations, movements, claims and decisions | Native relational constraints | Relational constraints available within one database file | Must be implemented in a separate index/catalog |
| Atomic resolution writes and concurrent clients | Strong fit | Concurrency is more constrained and requires deployment-specific design | Multi-object atomicity is not generally available |
| Local/offline operation | Suitable as central authority; clients still need durable local storage | Strong local transactional fit for per-device replica/outbox | Useful for export/archive, not a transactional offline domain store |
| Content-addressed immutable archive | Can store hashes and metadata; large-object archive is separate | Can store hashes and metadata; large-object archive is separate | Strong fit for permitted immutable objects |
| Cross-record temporal queries and traceability | Strong relational fit | Strong for a single local database | Requires a query/index layer |

The comparison indicates PostgreSQL remains the leading *candidate* for the central authoritative relational service, while SQLite is now a strong candidate for durable per-device local storage, offline work and the synchronization outbox. This suggests a central relational service plus local relational replicas, but does not approve either physical implementation or protocol. Object storage remains an optional archive only for content whose retention is explicitly permitted. Volume, latency, availability, deployment, retention, recovery, security and cost requirements still need evidence.

### 6.2 Provisional direction

A central relational service is the leading category for the canonical shared ledger because IWFI requires referential integrity, transactions, temporal claims, deterministic decision records and multi-client synchronization.

The product decision is offline-first. The leading architectural hypothesis is PostgreSQL (or another validated central relational engine) as the server authority plus SQLite (or another validated embedded relational engine) on each client for local reads/writes and a durable outbox. The sync protocol—not direct database-file sharing—reconciles clients. Neither engine is approved by this ADR; protocol and operational requirements must be validated first.

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

## 9. Chain-integrity dependency and remaining unknowns

The chain-integrity contract dependency is now defined and integrated through PR #20 / Issue #19:
- immutable network-specific inclusion observations for BTC and ETH;
- explicit separation of transaction inclusion identity and transfer event identity;
- versioned canonicality assessments and supersession rather than in-place mutation;
- no inference of non-inclusion from absence of data;
- Bitcoin reorg/re-inclusion semantics without an invented universal confirmation/finality threshold;
- Ethereum finalized checkpoint evidence, source identity and inclusion-height coverage;
- multi-source conflicts remain unresolved; historical ResearchSnapshots freeze the evidence/assessment IDs known at run time.

The persistence implementation must honor `docs/data-model/chain-integrity-contract.md`. This resolves the contract-definition dependency; it does not prove durable snapshot immutability until the persistence model and integration tests are implemented.

Other unresolved inputs include expected event volume, retention duration by provider, deployment location, recovery objectives, security/key-management details, synchronization batch sizing, and actual query workloads. Offline-first behavior is a confirmed product requirement; its protocol and conflict policies remain assigned to Issue #22. No numeric operational target is invented here.

## 10. Validation plan before backend implementation

The implementation plan must include synthetic tests for:
- exact retry/idempotent insert of the same observation;
- same provider record with changed payload hash;
- same transaction with two distinct event locators;
- null locator without accidental uniqueness collision;
- two networks with identical transaction-hash text;
- competing inclusion observations and a transaction re-included in a different block;
- same-source positive evidence for a prior block leaving the active chain;
- cross-source canonicality conflicts that remain unresolved;
- Ethereum finalized checkpoint coverage and unsupported finality tags;
- a new chain assessment without mutation of a historical ResearchSnapshot;
- competing resolution runs over the same input set;
- new observations producing a new decision without overwriting old decisions;
- INVALID/QUARANTINED evidence retained but excluded from resolved fields;
- temporal claim correction and supersession;
- interrupted transactions and retry after failure;
- same sync batch submitted repeatedly, including a lost response after server commit;
- disconnect mid-batch and resume from the last server-confirmed cursor;
- concurrent changes from three simulated clients without last-write-wins data loss;
- causal dependencies arriving out of order and device clocks drifting;
- incompatible schema/policy versions, rejected operations and quarantine;
- local ResearchSnapshot remaining immutable after later synchronized evidence;
- device revocation, local logout, encrypted local data and key lifecycle;
- backup restore and migration rollback/recovery rehearsal.

## 11. Decision gate

This ADR does not authorize:
- selecting or purchasing a database service;
- creating a production database or backend;
- provider credentials, API calls, polling, or historical backfills;
- raw payload retention;
- wallet clustering, institutional attribution, whale statistics, or buy/sell analysis.

Issue #16 remains open until requirements are measured, the options are evaluated against those requirements, retention/security/operational questions are assigned, and the project owner accepts the ADR. Issue #22 defines the offline-first synchronization protocol and must be resolved before backend implementation. Only then should separate implementation Issues and PRs be created.
