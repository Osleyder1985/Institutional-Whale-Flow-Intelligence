# Local artifact retention policy

Status: contract and validator implemented; **no retention policy is approved by this document or by test fixtures**.

## Scope

This contract covers the Binance Vision local research artifact lifecycle:

- `SOURCE_ARCHIVE`: downloaded ZIP payload.
- `CHECKSUM`: provider checksum file and locally computed digest metadata.
- `VALIDATION_REPORT`: offline archive-validation output.
- `NORMALIZED_OBSERVATION`: parsed/normalized source records.
- `DERIVED_DATA`: features, aggregates, indicators, and other transformations.
- `SNAPSHOT`: reproducible research snapshots.
- `LOG`: acquisition, validation, access, and deletion logs.
- `BACKUP`: any locally controlled backup copy.

## Approval semantics

A policy remains `NOT_APPROVED` until the data owner has supplied and reviewed an explicit rule for every artifact class. Each rule must state its basis, either a positive fixed duration in seconds or a named end event, a deletion method, and a requirement to retain deletion evidence. No default duration, grace period, capacity, or automatic deletion behavior is defined here.

The example fixture in tests is synthetic and is not an approval or a recommendation of a retention period.

## Storage and cost

- Storage scope is `LOCAL_ONLY`.
- Cloud synchronization is prohibited.
- External cost must be exactly USD 0.
- No cloud storage, paid backup, hosted service, or paid fallback is authorized.
- Disk capacity must be measured in the actual target environment before acquisition planning; this contract imposes no arbitrary capacity limit.

## Versioning and deletion evidence

Every acquired archive revision must be recorded as a distinct artifact version with acquisition UTC timestamp, exact source URL, provider checksum (when supplied), locally computed cryptographic digest, validation report reference, terms-review timestamp, purpose, and applicable policy ID. A changed archive must never silently overwrite an earlier version.

Deletion evidence must identify the artifact/version, scope of dependent derivatives and copies, execution timestamp, method, and verification result. Deletion must account for derivatives and backups under the user's control. Logs must not retain prohibited payload data merely to prove deletion.

## Enforcement

Call `authorize_artifact_write(source_use_policy, retention_policy, artifact_type)` before any local write. It fails closed unless the source-use policy passes, the retention policy ID and source ID match, all eight artifact classes are approved, cloud sync is disabled, external cost is zero, and the requested artifact type is known.

This validator checks supplied metadata; it does not establish legal rights, choose a retention duration, inspect operating-system sync settings, measure disk capacity, or prove secure erasure. No source adapter, download, polling, backfill, or payload persistence is enabled by this change.


## Proposed owner-reviewed retention model — Binance Vision Spot aggTrades (2026-11-14)

**Status: PROPOSAL ONLY — NOT APPROVED.** This section is a concrete event-based proposal to resolve Issue #71. It does not authorize download, storage, adapter activation, polling, backfill, backup creation, or deletion. The runtime guard must continue to block writes until the owner approves the policy and the local environment gates are verified.

### Source-use boundary informing the proposal

The Binance Vision Dataset Terms v1.0 (last updated 2026-08-26) state:
- Clauses 2.1–2.3: historical datasets are published through `data.binance.vision` and access is free of charge, subject to the terms.
- Clause 2.4: use of data derived from, calculated with, or extracted from datasets remains governed by the terms.
- Clauses 3.1–3.4: CC BY-NC-SA 4.0 applies; commercial use is excluded and requires a separate written enterprise licence.
- Clause 4.1: permitted uses include algorithmic historical backtesting for purely personal non-production research.
- Clauses 4.2–4.4: prohibit live proprietary trading execution, compensated signal distribution, hosting/exploitation of data feeds, and integration into commercial financial products.
- Clause 4.5: redistributed derivative works require Binance Vision attribution and the identical CC BY-NC-SA 4.0 licence.
- Clauses 7.1–7.3: rate limits and automated download protocols must be respected; circumvention and continuous queries that impair service are prohibited.
- Clause 9.2: de-anonymization or reverse-engineering to isolate natural persons is prohibited.

The public Binance Public Data Issue #502 contains a contributor response dated 2026-11-05 stating that a purely private individual research use falls within clause 4.1, automated retrieval remains subject to the Vision Dataset Terms and Binance Terms of Use, and `data-api.binance.vision` is not a live endpoint. This is relevant provider-repository evidence, not a legal opinion or a signed legal/support determination. The source route under evaluation is the historical archive at `data.binance.vision` only.

Official references:
- https://github.com/binance/binance-public-data/blob/master/TERMS_AND_CONDITIONS.md
- https://github.com/binance/binance-public-data/issues/502
- https://creativecommons.org/licenses/by-nc-sa/4.0/legalcode

### Proposed event-based rules (no invented fixed durations)

| Artifact class | Proposed retention end event | Required deletion / control |
|---|---|---|
| `SOURCE_ARCHIVE` | Owner ends the research purpose or explicitly requests deletion, after all dependent artefacts are inventoried | Delete only after dependency review; preserve no uncontrolled copies |
| `CHECKSUM` | The corresponding source archive is deleted and the integrity/deletion audit is complete | Keep linked to the archive revision; do not retain payload bytes in the checksum record |
| `VALIDATION_REPORT` | The source archive and every dependent observation/derivative have been deleted or explicitly retained under a separately approved rule | Report contains metadata only; no raw CSV rows |
| `NORMALIZED_OBSERVATION` | All dependent derived data and snapshots are deleted or explicitly retained under a separately approved rule | Inherit source restrictions; no identity inference from anonymous trades |
| `DERIVED_DATA` | Owner ends the research purpose or explicitly requests deletion, subject to the source licence and dependency review | Inherit source restrictions and attribution/licence obligations |
| `SNAPSHOT` | Owner ends the research purpose or explicitly requests deletion, after dependent reports/models are inventoried | Preserve reproducibility only while the underlying permitted evidence remains available |
| `LOG` | The related artefact lifecycle and deletion audit are complete | Metadata-only; exclude raw payloads, credentials, and unnecessary personal data |
| `BACKUP` | The corresponding primary artefact and all dependants are deleted, or owner explicitly requests deletion | No cloud/hosted/paid backup; any local copy must be individually enumerated and its physical location verified before creation |

### Operational safeguards in the proposal

- Retention is event-based, not a fixed number of days. No automatic deletion or silent expiry is proposed.
- A change in terms triggers immediate suspension of new acquisition/use pending review; it does not automatically assert that previously downloaded data has become unusable. Clause 1.4 must be considered for the specific version and acquisition date.
- Every revision remains immutable and separately hashed. Corrections or changed archives create new revisions; they never overwrite earlier records.
- All source-derived observations, features, models, reports, snapshots, and backups inherit source restrictions.
- Storage remains local-only; cloud sync, external distribution, public hosting, commercial use, live trading execution, and paid services remain blocked.
- Deletion uses the explicit audited deletion workflow, requires a dependency/backup inventory, and makes no secure-erasure claim.
- Backup creation remains operationally blocked until its local destination is explicitly enumerated and verified as non-synchronized.

### Approval gate

The proposal remains `NOT_APPROVED` until the data owner explicitly accepts or revises every event rule and the following are evidenced: exact source policy snapshot/hash, applicability review, local storage path, sync-risk review, actual free disk capacity, and a controlled synthetic deletion test. No Binance sample may be downloaded or persisted before those gates pass.

