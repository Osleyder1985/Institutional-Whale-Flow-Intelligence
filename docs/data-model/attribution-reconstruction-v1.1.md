# Attribution Reconstruction Manifest v1.1

## Purpose

Version 1.1 extends, rather than mutates, v1.0. It freezes the complete Actor Registry v1.2 object and all typed evidence references reachable from:
- each actor's `evidence_refs` and `counter_evidence_refs`;
- each actor alias's `evidence_refs`;
- each actor classification's `evidence_refs`;
- each relationship's supporting and counter evidence.

The canonical registry bytes use `IWFI-JSON-C14N-1` (UTF-8 JSON, sorted object keys, compact separators, ensure_ascii=false, allow_nan=false). This is an IWFI-specific versioned representation, not a claim of RFC 8785/JCS compliance.

## Frozen fields

The manifest binds:
- root claim ID, contract version and supplied SHA-256;
- Actor Registry contract version and full registry SHA-256;
- exact query knowledge cutoff and valid time;
- algorithm ID/version and parameters;
- every typed reference with its structural record path, evidence polarity and exact snapshot IDs;
- every unique snapshot descriptor and payload hash;
- its own SHA-256 manifest hash.

The reference-to-snapshot map must cover exactly all unique typed references. Missing mappings, extra mapping keys, duplicate record references, unknown snapshot IDs, duplicate dependency IDs and duplicate actor/relationship IDs fail during construction.

## Offline verification

The verifier recomputes the full registry hash, re-enumerates references from the registry, compares the complete reference set and snapshot mapping, checks that dependencies match exactly the referenced snapshot IDs, checks descriptor equality and retrieval time against the frozen cutoff, and verifies exact payload bytes using the existing snapshot verifier.

A partial or hash-only snapshot cannot be silently treated as a complete payload: if bytes are unavailable, verification returns PAYLOAD_UNAVAILABLE. The caller must obey retention and rights policy before supplying bytes.

## Limits

The root claim hash is an externally supplied binding; this verifier does not independently validate the root claim payload unless a separate claim verifier is invoked. A valid SHA-256 proves byte consistency against this manifest, not authorship, factual truth, beneficial ownership, economic intent or causality. A signed/independently anchored manifest is a separate future control. No WORM guarantee is claimed.

No network, live capture, polling, backfill, credentials, paid service or external-cost dependency is introduced. Fixtures are synthetic; external cost is 0 USD.
