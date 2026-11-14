# Documentary claim-to-snapshot provenance

## Purpose

A Documentary Attribution Claim records one analytical assertion and its traceable source support. It is deliberately separate from the original document, source observation, market observation, and legal decision.

## Immutable source identity

Each evidence entry binds all of the following to one catalog record:

- `document_id`;
- exact `snapshot_sha256` of the original captured bytes;
- exact source URL;
- UTC retrieval timestamp;
- declared document version;
- a structured locator (clause, section, page, or character range).

The mutable URL is descriptive metadata only. The snapshot hash is the stable identity. The validator accepts no evidence entry unless its document ID and hash resolve to exactly one record in the caller-supplied snapshot catalog and its URL, retrieval time, and version match that record.

The catalog must describe actual captured snapshots, not merely a current URL or a hash observed in an HTTP response. The validator does not fetch, download, or independently recalculate source bytes.

## Expression and epistemic distinctions

| Expression type | Meaning | Required trace |
|---|---|---|
| `VERBATIM` | The claim reproduces literal source wording | Snapshot + locator + SHA-256 of extracted span |
| `PARAPHRASE` | The claim restates source meaning in new wording | Snapshot + locator + SHA-256 of extracted span |
| `INFERENCE` | The claim is an analytical conclusion, not source wording | Snapshot evidence + locator; no literal-span hash |

The source excerpt itself is intentionally not stored in this public contract. This reduces unnecessary redistribution of source text while preserving a digest that a reviewer can recompute from an independently held extraction. A span hash is not proof that the span is legally reusable or that the interpretation is correct.

A claim's `epistemic_status` remains explicit. The validator does not upgrade `INFERRED`, `UNKNOWN`, or `DISPUTED` to `VERIFIED`. A verbatim expression cannot be labelled as an inference.

## Linking claims to IWFI objects

Every claim must target at least one typed IWFI object: analysis, movement episode, hypothesis, attribution claim, actor, or source observation. The relation records whether the claim supports, contradicts, contextualizes, or derives from that object.

A claim is not a causal finding merely because it is linked to a movement episode. Causal attribution remains a separate analytical assessment and must preserve alternatives and counter-evidence.

## Contradictions and versions

Claims from different snapshots are append-only records. Use the same `contradiction_group_id` to preserve competing assertions. The collection validator reports group membership but never picks a winner, collapses versions, or treats a later publication date as proof of applicability to an earlier event.

## Review and legal boundaries

A reviewed claim requires reviewer identity and review timestamp. Review status is not a legal opinion. The contract enforces:

- `authorization_status = NOT_GRANTED`;
- `legal_review_status = NOT_PERFORMED`.

No source is activated and no redistribution, retention, licensing, or legal applicability is approved by this component.

## Validation

Run the focused suite:

```powershell
python -m unittest discover -s tests -p "test_documentary_claim_provenance.py"
```

The validator is standard-library-only and operates exclusively on caller-supplied Python objects. It performs no network, filesystem, database, or provider operations.
