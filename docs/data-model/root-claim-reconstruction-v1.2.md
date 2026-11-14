# Root Claim Snapshot Binding — Manifest v1.2

## Scope

v1.2 extends v1.1 without changing the v1.1 schema or verifier. It freezes a SHA-256 digest of the complete root Attribution Claim snapshot descriptor (including rights/retention metadata) and requires the exact UTF-8 JSON payload bytes to be retained and supplied during offline verification. The root snapshot ID must be distinct from registry evidence snapshot IDs.

The root claim is checked at two levels:
1. Snapshot descriptor and raw payload integrity via the snapshot SHA-256 verifier.
2. Semantic object binding via `IWFI-JSON-C14N-1`, SHA-256, claim ID and contract version.

The v1.1 Actor Registry verifier is then run against the same registry and evidence snapshots. The root claim can no longer be represented only by an externally supplied hash when using v1.2.

## Fail-closed behavior

Missing bytes, metadata-only retention, any descriptor-field substitution, payload mutation, claim ID/version mismatch, root claim recorded after the knowledge cutoff, snapshot retrieval after the cutoff, or valid-time outside the root claim interval prevent reconstruction. The root claim snapshot must be `application/json` and have a `RETAINED` payload decision.

## Limits

The snapshot descriptor's source identity and rights policy remain evidence metadata; hashes do not authenticate the provider or prove truth. Retaining bytes is allowed only where rights policy permits. The verifier does not create storage, signatures, trusted timestamps, or WORM guarantees. v1.2 is offline-only and uses synthetic fixtures; no network, live capture, polling, backfill, credentials, paid service or external-cost dependency.
