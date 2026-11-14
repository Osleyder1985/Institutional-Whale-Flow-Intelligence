# Explicit local artifact deletion and audit

`iwfi.local_artifact_deletion.delete_artifacts` performs only an explicitly requested deletion of artifact IDs supplied by the caller.

## Preconditions

- Existing local non-symlink storage root.
- Approved source-use and retention policies.
- Each artifact has a provenance record matching the source and retention policy.
- The deletion method exactly matches the approved method for each artifact class.
- The caller supplies the complete reviewed list of dependent artifacts and backups.
- Every artifact ID is unique and its directory contains no symlinks.

## Behavior

The function validates every target before deleting any of them and writes an exclusive `*.started.json` intent record under `_deletion_audit/` before removal begins. It then deletes only the explicitly enumerated artifact directories, verifies their absence, and writes an exclusive `*.completed.json` result record. A crash during deletion therefore leaves a durable intent record for manual reconciliation. The audit records reviewed dependency and backup IDs and reports VERIFIED, PARTIAL, or NOT_VERIFIED.

This is a manual, explicit operation. It is not a retention scheduler and does not automatically delete expired data. If completion-audit persistence fails after deletion, the started event remains; operators must inspect the storage root and audit directory before retrying. Audit records themselves are LOG artifacts and remain subject to the approved LOG retention rule.

## Limitations

The function cannot discover derivatives or backups outside the supplied inventory/root. It cannot prove secure erasure from SSD remapping, filesystem journals, snapshots, external backups, or other software. VERIFIED means the listed directories are absent from this storage root after deletion; it is not a forensic secure-erasure certificate. No real user data is deleted by tests.
