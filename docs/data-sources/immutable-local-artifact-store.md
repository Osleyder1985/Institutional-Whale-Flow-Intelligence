# Immutable local artifact store

The local artifact store is a guarded persistence primitive, not a source adapter and not an approval to acquire Binance Vision data.

## Write contract

Call `store_artifact(root, payload, record, source_policy, retention_policy)` only after the owner has configured and approved a real retention policy. The function:

1. Requires a known artifact type and passes source-use plus artifact-specific retention authorization.
2. Checks source ID, retention policy ID, local-only scope, no cloud sync, personal non-production purpose, UTC timestamps, and payload SHA-256.
3. Requires an existing non-symlink directory chosen by the operator.
4. Creates a new artifact directory exclusively; an existing artifact ID is rejected and never overwritten.
5. Writes payload and JSON provenance record using exclusive-create mode and fsync.

The store performs no network access, no automatic directory creation, no cloud synchronization, no deletion, and no backup. It cannot determine whether an arbitrary directory is synchronized by the operating system; the operator must verify that separately. A process or machine failure during a write can leave an incomplete directory, which must be treated as quarantined and must not be overwritten automatically.

## Limits

This utility does not prove secure erasure, inspect the dependency graph for derivatives, measure free disk capacity, or enable any capture workflow. Test policies are synthetic and do not approve real data retention. External cost remains USD 0.
