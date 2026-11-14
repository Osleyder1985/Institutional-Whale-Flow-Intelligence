# Policy source versioning — design and operational contract

## Immutable evidence model

A policy source is not a single mutable file. IWFI distinguishes:

1. **Source identity** — stable document ID, provider, canonical URL and source type.
2. **Source version** — issuer-declared version/effective date, when available.
3. **Captured snapshot** — exact bytes, SHA-256, byte count and capture timestamp.
4. **Observation** — a dated retrieval result with body hash and HTTP metadata.
5. **Review** — human assessment linking a conclusion to an exact snapshot hash and clause locator.

A new observation must never mutate a prior snapshot or prior review.

## Change classification

- `UNCHANGED`: retrieved bytes match the registered baseline SHA-256.
- `CONTENT_CHANGED`: bytes differ from the baseline.
- `BASELINE_NOT_ESTABLISHED`: no baseline hash is registered.
- `SOURCE_UNAVAILABLE`: retrieval failed; this is not a revocation or deletion conclusion.
- `REVIEW_REQUIRED`: a human must inspect the event before any baseline or applicability decision.

ETag and Last-Modified are supporting metadata only. They can change without the body changing, or remain stable while the body changes.

## Source-specific storage and redistribution

No universal storage ban or universal permission is inferred. The source register records the evidence basis and status separately for each document. An unresolved redistribution status is not converted to permission merely because a URL is public. Equally, it is not used as a blanket reason to prevent storing unrelated documents whose redistribution basis is documented.

## Review linkage

Every substantive policy finding must cite:
- `document_id`;
- exact `snapshot_sha256`;
- section/clause locator;
- source version/effective date, if present;
- review timestamp and reviewer;
- applicability status and unresolved questions.

A finding without a stable snapshot reference is not considered reproducible evidence.

## Operational boundary

The observer is invoked explicitly. There is no schedule, cron, continuous polling, source activation, market-data capture, or automatic authorization. Retrieval and hash verification are technical facts only; legal review, retention permission and operational source approval remain independent decisions.
