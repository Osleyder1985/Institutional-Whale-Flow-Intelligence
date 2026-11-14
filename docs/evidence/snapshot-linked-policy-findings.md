# Snapshot-linked policy findings

## Purpose

A policy conclusion is reproducible only when it points to the exact captured document bytes and a text excerpt that can be located in those bytes after extraction. A mutable URL, a filename, or a section number alone is insufficient.

## Review register

The versioned JSON schema is `data/schemas/policy-review-register-v1.0.schema.json`. Each finding records:

- stable `finding_id` and the proposition being assessed;
- `conclusion_type`: `OBSERVED_TEXT` or `INTERPRETATION`;
- `source.document_id` and exact `source.snapshot_sha256`;
- optional issuer-declared version;
- exact text excerpt and locator kind (`document_text` or `pdf_page`);
- reviewer, UTC review timestamp, review state and applicability state.

For PDFs, the page number is mandatory in practice and the excerpt must occur on that exact page. For text documents, the excerpt must occur in the extracted document text. Excerpts are exact substrings, not paraphrases.

## Validate locally

The full extraction bundle contains source text and must remain private. The review register contains metadata and short evidence excerpts only; inspect it before committing or publishing.

```powershell
python scripts/validate_policy_findings.py `
  --bundle "$HOME\IWFI-private-evidence\policy-documents\policy-document-extraction-bundle-v1.0.json" `
  --review-register "data\policy-reviews\example-review-register.json" `
  --output "$HOME\IWFI-private-evidence\policy-documents\policy-review-validation.json"
```

The validation report is created outside the repository and is never overwritten. Before checking findings, the tool rebuilds the extraction bundle from the original local snapshots and capture manifest, re-verifies each original file SHA-256/byte count, and requires the supplied bundle contents to match that reconstruction exactly. It then verifies each finding hash and exact text locator. The tool does not determine whether an interpretation is legally correct, whether a clause applies to IWFI, or whether redistribution, retention, or source use is authorized.

## Status semantics

- `REFERENCE_VERIFIED`: exact snapshot hash and excerpt locator were found.
- `ALL_REFERENCES_VERIFIED`: all entries passed technical reference checks.
- These statuses do not mean `LEGALLY_APPROVED`, `AUTHORIZED`, or `APPLICABLE`.

The register is metadata-only. Never place the complete extraction bundle or complete source text in this public repository.
