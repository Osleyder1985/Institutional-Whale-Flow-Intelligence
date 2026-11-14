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
