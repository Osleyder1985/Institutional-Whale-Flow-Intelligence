# Provider source-policy evidence registry v1.0

## Purpose

This registry is the intake boundary for provider-specific retention rights. Empty is intentional: no provider has been approved merely because the software supports a schema.

## Evidence required for every policy

- Stable source and provider identifiers.
- Policy identifier and version, issuing authority, rights reference, active/revoked state, and stable document reference.
- SHA-256 of the exact original policy document snapshot.
- UTC retrieval and review timestamps.
- Explicit VERIFIED review state, reviewer identifier, and reviewed scope.
- Allowed/prohibited actions and strict effective/expiry timestamps.

A policy without the original document snapshot and matching SHA-256 remains UNASSESSED or PENDING_EVIDENCE. A URL, provider name, email response, or manually typed summary alone is not proof that the exact terms were preserved or reviewed.

## Approval rules

APPROVED is a review outcome, not an automatic default, and the schema rejects an APPROVED provider entry with an empty policy list. It may only be assigned after the source's applicable terms have been reviewed for the exact IWFI use: local retention, historical snapshots, derived artifacts, reconstruction, and any limits on duration, volume, attribution, or onward use. Ambiguity, conflicting terms, missing clauses, or an unverified issuer leaves the source unapproved.

No approval is inherited between providers, products, endpoints, data types, or time periods. Any changed document hash, new policy version, revocation, or expiry invalidates the prior approval and requires a new review.

## Fail-closed behavior

The runtime authorization evaluator now requires issuer, document_ref, document_sha256, retrieved_at_utc, reviewed_at_utc, review_status=VERIFIED, reviewer_id, and a non-empty review_scope for every policy used to authorize an artifact. It rejects malformed document hashes, future retrieval/review timestamps, and any review state other than VERIFIED. The registry's empty initial state authorizes no source. Synthetic test fixtures are not provider approvals.

This registry does not itself establish legal validity. Human review must verify the issuing authority and exact document. Do not create a provider record until its primary evidence is available.
