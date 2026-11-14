# Versioned policy-source observations

IWFI policy sources are observed only when an operator explicitly runs the observer. No scheduled polling, background monitoring, market-data capture, backfill, or authorization workflow is introduced.

## Run

```powershell
python scripts/observe_policy_sources.py --output-dir "$HOME\IWFI-private-evidence\policy-observations"
```

Select individual records with repeated `--source-id` arguments. The tool performs HTTPS GET only for URLs already registered in `data/policy-document-sources-v1.0.json`.

## Interpretation

| Status | Meaning |
|---|---|
| `UNCHANGED` | Retrieved body SHA-256 matches the registered baseline |
| `CONTENT_CHANGED` | Retrieved body SHA-256 differs from the registered baseline |
| `BASELINE_NOT_ESTABLISHED` | No baseline hash exists; no change conclusion is possible |
| `SOURCE_UNAVAILABLE` / `REVIEW_REQUIRED` | Retrieval failed; this does not prove deletion, revocation, or a legal change |

ETag and Last-Modified are recorded as supporting HTTP metadata. They are not treated as content identity: a different ETag with identical bytes remains `UNCHANGED`. Content-Length is checked against the bytes received.

Each observation is a new JSON file named with source ID and UTC observation time. Existing records are never overwritten. A new baseline must be deliberately reviewed and recorded; the observer never updates the registry itself.

## Independent status dimensions

- Technical observation and byte integrity do not establish issuer authenticity or legal effect.
- Public availability does not automatically establish permission to redistribute.
- Redistribution status, retention status, legal review, and source authorization remain distinct fields.
- A changed document is not automatically applicable to IWFI or to a historical download.
- An unavailable URL is not evidence that the document or rights have been revoked.

The source registry therefore records source-specific redistribution and retention states. The former blanket prohibition on repository storage is removed; a document may be copied into the evidence repository only when its source-specific redistribution basis has been assessed and recorded. Where that basis is unresolved, preserve the official reference and captured hash without representing the copy as authorized.

## Security

The observer uses exact registered HTTPS URLs, restricts redirects to the registered source host, rejects credential-bearing URLs, verifies Content-Length when supplied, and stores only observation metadata/hashes (not source bodies). It does not send observations anywhere.
