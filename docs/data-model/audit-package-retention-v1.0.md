# Retention-gated local audit packages v1.0

## Mandatory authorization gate

iwfi/audit_package_retention.py is the fail-closed gate used by the ZIP builder and verifier. Every inventoried artifact requires exactly one individual authorization bound to its exact path and SHA-256. The authorization must identify its direct source IDs, action RETAIN_LOCAL, status AUTHORIZED, and a strict UTC validity interval.

For every direct source, the evaluator traverses source_lineage to its full transitive closure. Every source in that closure must have at least one complete, active, in-date policy. All applicable policies must permit RETAIN_LOCAL; any missing, expired, revoked, incomplete, contradictory, or externally permissive policy rejects the package. Cycles and incomplete lineage reject.

## Frozen decision and revalidation

The ZIP contains retention-authorization.json, conforming to schemas/audit-package-retention-decision-v1.0.schema.json. It binds the exact inventory manifest hash; each artifact path and SHA-256; each individual authorization ID and canonical SHA-256; direct and transitive source IDs; hashes of all applicable source policies; the UTC evaluation time; and the overall authorization evidence hash.

The ZIP verifier requires the caller to provide the current authorization context and re-evaluates all records at its current evaluated_at_utc. It rejects a changed authorization/policy set and any authorization or policy that has expired or become inactive. A previously generated decision is not a perpetual license.

## Local-only boundary

build_audit_package_zip returns ZIP bytes in memory after the gate succeeds. It does not write to a filesystem, publish, distribute, upload, transmit, or synchronize. There is no remote destination or transport API. package_mode must be LOCAL_ONLY; external distribution/synchronization actions are rejected if declared as allowed by a source policy. A detached signature is an integrity/authenticity primitive and is not a grant of redistribution rights.

## Limits

The evaluator checks supplied policy and authorization records; it does not independently authenticate a provider or legal document. The caller must supply the complete, authoritative current policy set and provenance graph. SHA-256 binds bytes, not legal validity or factual truth. No real source, external service, credential, capture, polling, backfill, paid dependency, or external cost is introduced. Tests use synthetic BTC/ETH-related artifacts only.
