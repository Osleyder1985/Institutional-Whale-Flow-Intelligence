# ADR-0002: Offline-First Synchronization Protocol

- Status: Proposed
- Date: 2026-11-14
- Related issue: #22
- Depends on: #16, Source Observation, Entity Attribution, Movement Ledger, Observation Resolution, Chain Integrity v2
- Decision owner: IWFI project owner

## 1. Purpose and boundaries

Define a provider-neutral, auditable protocol for desktop, Android and iOS clients to work while disconnected and later synchronize with one central authoritative IWFI dataset.

This is a protocol proposal only. It does not deploy a service, create a database, issue credentials, activate providers, capture data, enable polling/backfills, or run market analysis. The protocol must not weaken provider retention restrictions or the append-only evidence rules in ADR-0001.

## 2. Roles and authority

- **Client installation:** one registered installation on desktop, Android or iOS. It owns a stable device_id, a protected local database, a durable outbox and a server-issued cursor per synchronization stream.
- **Central service:** the sole authority for the shared dataset, accepted operation receipts, global sequence/cursors, canonical uniqueness constraints, device authorization and conflict records.
- **Local replica:** durable working copy of records already synchronized or created locally. It is not a competing global authority.
- **Provider adapter:** a separately authorized, user-invoked capture process. Synchronization itself never calls providers.

The central service decides whether an operation is accepted, rejected, quarantined, or requires semantic conflict resolution. A client cannot mark an operation SYNCED before it has a verifiable server receipt.

## 3. Operation envelope

Every user-created mutation is represented by an immutable operation envelope:

| Field | Requirement | Semantics |
|---|---|---|
| operation_id | Required, globally unique UUID | Stable across retries and restores |
| device_id | Required | Registered installation identity |
| stream_id | Required | Logical cursor stream |
| device_sequence | Required, monotonic per device/stream | Local ordering hint; not a trusted global clock |
| causal_dependencies | Required array, may be empty | Operation IDs that must be accepted first |
| entity_type / entity_id | Required | Domain target |
| operation_kind | Required | Typed create/revise/link/decision/snapshot action |
| schema_version | Required | Envelope and payload contract version |
| policy_versions | Required map, may be empty | Exact domain policy versions used |
| created_at_device_utc | Required UTC timestamp | Diagnostic only; never determines server order |
| payload_hash | Required SHA-256 | Integrity check over canonical payload bytes |
| retention_class / terms_record_id | Required | Determines whether payload content may be persisted; RAW_ALLOWED requires an explicit approved terms record |
| payload | Required object | Only permitted normalized content; raw provider payload remains prohibited unless specifically authorized |

The idempotency key is operation_id. payload_hash is SHA-256 over canonical UTF-8 JSON payload bytes. The server independently stores operation_fingerprint, SHA-256 over the canonical complete envelope (including payload_hash, schema/policy versions, retention metadata and payload). Object keys are sorted and arrays retain their declared order.

- Same operation_id + same operation_fingerprint: return the original receipt; do not apply twice.
- Same operation_id + different operation_fingerprint: reject as IDEMPOTENCY_KEY_REUSE, preserve a security/audit conflict, and do not overwrite the first operation.
- A retry must reuse the exact operation ID and complete operation fingerprint. A changed payload or envelope is a new operation with a new ID and explicit supersession/correction relation.

## 4. Delivery and acknowledgement

Delivery is at least once. Exactly-once network delivery is not assumed. Exactly-once effects are achieved by a unique operation ID and atomic server-side inbox/application transaction.

1. Client commits the domain change and outbox envelope in one local transaction.
2. Client sends a bounded batch with the last server-confirmed cursor and stable operation IDs.
3. Server authenticates and authorizes the device, validates envelope/payload versions and retention eligibility, then checks idempotency. Every receipt echoes operation_id, device_id and stream_id and fingerprints the full immutable envelope; clients validate this binding before accepting its cursor. A receipt from another device or stream cannot advance the local cursor.
4. Server records the inbox receipt and applies or classifies the operation atomically. Acknowledgement is emitted only after durable commit.
5. Client verifies the receipt, marks the operation SYNCED, and advances its local cursor only to the server-issued cursor.
6. If the response is lost after server commit, the client resends the same operation IDs. The server returns the original receipts without duplicate effects.
7. If a batch is interrupted, the client resumes from the last confirmed cursor and resends unacknowledged operation IDs.

No client timestamp is used as a global ordering or conflict-resolution authority.

## 5. Server inbox and cursor model

The server maintains:

- **SyncInbox:** one durable receipt per operation_id, including device, payload hash, validation outcome, apply outcome, server sequence and timestamps.
- **SyncOutbox:** committed server changes available to clients, each with a monotonic server sequence within a named stream.
- **SyncCursor:** server-confirmed high-water mark per device and stream.
- **SyncConflict:** immutable references to competing operations/records and their conflict class.
- **Device:** registration, key reference, status, creation/revocation metadata and supported client versions.

Cursors are opaque, server-issued tokens or monotonic sequence positions. A client must not invent, increment, or derive a cursor from wall-clock time. Cursor advancement is atomic with the corresponding page/batch acknowledgement. A page is complete only when the server returns its explicit continuation/terminal marker. Before accepting a receipt, the client validates the complete outcome tuple: ACCEPTED/DUPLICATE must carry a positive non-boolean server sequence, non-empty cursor and valid commit timestamp; DEPENDENCY_PENDING/REJECTED/QUARANTINED/CONFLICT must carry a stable reason and must not carry a commit timestamp, sequence or cursor. Receipt timestamps are real UTC calendar values, not regex-only strings. A cursor must match the requesting device and stream, carry a real UTC issue timestamp, never move behind the last confirmed server sequence, and preserve the same opaque token when replaying the same sequence. Non-terminal pages require an explicit next token different from the current token (self-referential pagination loops are rejected); terminal pages prohibit one.

Server sequence numbers express commit order in the central authority, not the real-world event time of blockchain or provider observations.

## 6. Operation state machine

Client-visible states:

| State | Meaning | Allowed next states |
|---|---|---|
| LOCAL_PENDING | Durable locally; not yet sent | IN_FLIGHT, LOCAL_REJECTED |
| IN_FLIGHT | Sent; no final server receipt yet | SYNCED, SERVER_REJECTED, QUARANTINED, CONFLICT, LOCAL_PENDING |
| SYNCED | Server receipt verified and cursor advanced | Terminal for this operation |
| SERVER_REJECTED | Server rejected with stable reason; no domain mutation applied | Corrected new operation; original remains terminal |
| QUARANTINED | Preserved but excluded from domain resolution pending review | Explicit release as a new operation or terminal retention outcome |
| CONFLICT | Semantically incompatible with existing accepted facts/decisions | Explicit resolution operation; never silent overwrite |
| LOCAL_REJECTED | Client-side validation failed before send | Corrected new operation; original retained in local audit history |

A timeout or connection loss is not a rejection. The operation returns to LOCAL_PENDING unless a durable receipt proves otherwise.

## 7. Causal dependencies and out-of-order delivery

- Every operation may list zero or more causal_dependencies.
- The server applies an operation only after all dependencies have accepted receipts.
- If a dependency is not yet present, return DEPENDENCY_PENDING; retain the envelope in a retryable state without advancing the relevant applied cursor.
- If a dependency is permanently rejected or references an unknown device/operation outside retention, return a stable conflict/rejection reason for explicit handling.
- Device sequence is diagnostic and detects local gaps; server causal links determine whether an operation can be applied.
- Clock skew changes neither causal order nor cursor position.

## 8. Entity-specific conflict policy

| Entity / operation | Idempotent duplicate | Conflict behavior |
|---|---|---|
| SourceObservation | Same observation ID and identical canonical content: deduplicate by receipt | Same ID with different content: quarantine/conflict; preserve both envelopes without overwriting |
| ChainInclusionObservation | Same observation ID/content: deduplicate | Different block/source/view assertions: preserve separately; never merge source assertions |
| CanonicalityAssessment | Same evidence fingerprint and policy: same assessment content | Different content for same evidence/policy fingerprint: integrity conflict; differing evidence/policy creates a new assessment and optional supersession link |
| AttributionClaim | Exact claim/version: deduplicate | Contradictory overlapping claims: retain both with DISPUTED/conflict; require policy resolution or explicit review |
| Movement | Same strong identity (network + normalized transaction ID + event locator) and compatible facts: link evidence to same movement | Contradictory facts or missing locator: candidate/conflict; never infer a locator or merge by amount/address/time |
| ResolutionDecision | Same policy + exact canonical input fingerprint: deduplicate | Different outputs for same policy/input fingerprint: deterministic-integrity incident; preserve both records and quarantine affected output |
| ResearchSnapshot | Same snapshot ID/content: deduplicate | Same ID with changed content: reject as immutable-record violation; a new user-requested run creates a new snapshot |
| SyncConflict | Same conflict ID: deduplicate | New evidence/resolution appends a new conflict state/event; never erase the original conflict |

No last-write-wins is permitted for evidence, movements, claims, chain assessments, resolution decisions or snapshots.

Independent user annotations may be merged only if their schema defines distinct stable IDs and no shared field is overwritten. No such merge behavior is assumed by this protocol.

## 9. Schema and policy compatibility

- Every client advertises supported envelope/schema versions and policy versions.
- The server publishes its accepted compatibility set and minimum client version.
- A compatible historical payload is stored with its original schema/policy version; it is never silently rewritten to the newest version.
- A domain decision created under an older policy remains an assessment under that policy. Re-evaluation under a newer policy is a new decision linked by supersession.
- Unsupported schema versions are rejected with UNSUPPORTED_SCHEMA_VERSION; unsupported policy-dependent operations are quarantined or rejected according to the entity contract. The server returns the required version and a stable reason.
- Clients may retain pending operations during incompatibility. They must not repeatedly mutate the same operation to make it appear compatible.
- Migration is explicit and creates a new operation with source operation reference, transformation version and preserved original hash.

## 10. Retention and payload admission

Retention is checked before durable inbox or domain persistence.

- No raw provider payload may be stored merely because it is inside a sync envelope.
- retention_class, source/endpoint terms reference and permitted data classification must be validated before the server accepts the payload.
- A payload forbidden by current source terms is rejected or quarantined without persisting the prohibited content; retain only the minimum permitted audit metadata and a non-reversible digest if allowed.
- Offline storage does not extend retention rights. A client must apply the same source-specific expiry/deletion policy to its local replica, outbox, exports and backups.
- Deletion/expiry is a separately audited operation that records scope, reason, policy, affected derivatives and completion status. Logical append-only history does not override mandatory deletion or provider terms.

## 11. Security and device lifecycle

- Use authenticated encrypted transport (TLS) and encrypt local databases and backups at rest.
- Keep device keys in OS-protected key storage; do not embed credentials in source code, logs, fixtures or synced payloads.
- Use short-lived access tokens and least-privilege device-scoped authorization. A device may only submit operations under its own registered identity.
- Device registration creates a server-side record and binds a public-key credential; key rotation is explicit and audited.
- Revocation blocks subsequent server synchronization and provider access. It cannot retroactively erase an offline device; local data/key erasure is best-effort when the device next connects or when OS security controls permit.
- Logout clears access tokens and session material; local data handling follows the explicit user-selected local retention policy. Offline logout cannot be represented as server-confirmed revocation until reconnection.
- A restored local backup must preserve device identity only if its key remains valid; otherwise it must enroll as a new device and retain the old operation IDs for idempotent recovery.

## 12. Required synthetic test scenarios (reference-model tests are contract simulations, not production transport/persistence tests)

1. Same batch delivered repeatedly.
2. Server commits, response is lost, and the client retries the same IDs.
3. Network cut mid-batch and resume from the last confirmed cursor.
4. Two devices create separate observations for the same strong movement identity.
5. Two devices create contradictory attribution claims for the same address/interval.
6. A policy version changes while one device is offline.
7. An outdated client submits an unsupported schema.
8. Operations arrive out of causal order.
9. A local operation is rejected/quarantined without losing its permitted audit envelope.
10. A local ResearchSnapshot predates evidence later synchronized by another device.
11. Device revocation and logout while online/offline.
12. Device clocks disagree or contain invalid timestamps.
13. Local backup restoration resends already acknowledged operations.
14. Same operation ID is reused with a different payload hash.
15. A retention policy forbids the payload in the inbox/outbox.
16. Conflicting chain observations are preserved and do not resolve by provider majority.
17. Two concurrent clients submit the same deterministic resolution decision.
18. Cursor pagination repeats or omits a page under simulated interruption.
19. A dependency is delayed, rejected, or permanently missing.
20. A server restore replays inbox operations without duplicate domain effects.

## 13. Unresolved decisions and evidence gates

This ADR does not invent:
- maximum batch size or payload size;
- retry interval, timeout, backoff or offline duration;
- cursor expiry and history-compaction policy;
- concurrency/throughput/latency/availability targets;
- RPO/RTO or backup cadence;
- deployment region, service operator or budget;
- key-management provider or device recovery UX.

These require workload, security, operational and cost evidence. External operating cost remains constrained by Issue #3/Issue #59; no paid hosting, database, object storage, backup or API dependency is approved here.

## 14. Decision gate

Issue #22 remains open until:
- operation, receipt, cursor and conflict contracts are versioned and validated;
- the state machine and entity-specific conflict rules are testable;
- synthetic tests prove idempotency, lost-response recovery, resumability and multi-device behavior;
- security and retention controls are reviewed against the actual local/client environments;
- unresolved operational parameters are assigned without arbitrary defaults;
- the project owner accepts the protocol.

This proposal does not authorize a production sync service, physical database schema, credentials, provider capture, polling, backfills, automatic analysis, or raw payload retention.
