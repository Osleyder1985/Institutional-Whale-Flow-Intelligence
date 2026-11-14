# Local policy-document evidence capture

This tool captures only the three allowlisted policy documents declared in
\`scripts/acquire_policy_documents.py\`. It is intended to run on the user's own
computer, writing into a private local directory outside the Git repository and
outside cloud-synchronized folders.

## Command

\`\`\`powershell
python scripts/acquire_policy_documents.py --output-dir "$HOME\\IWFI-private-evidence\\policy-documents"
\`\`\`

Select one or more documents with repeated \`--document-id\` arguments. The default
is all three registered documents. The tool uses only HTTPS GET, follows redirects
only when the destination remains HTTPS on an allowlisted host, streams without an
arbitrary size limit, computes SHA-256 over the exact response bytes, and records
HTTP metadata. Existing snapshot files and manifests are never overwritten.

## Documents

- Binance Vision Dataset Terms v1.0 (the source URL points to the mutable GitHub
  \`master\` branch; the manifest marks it mutable and records ETag/Last-Modified).
- CC BY-NC-SA 4.0 official plain-text legal code.
- Binance Terms of Use PDF dated 2026-01-05, identifying ADGM Binance entities.
  Its applicability to the user's actual account, territory, and intended use is
  unresolved and must be reviewed separately.

## Output and controls

The local folder receives the exact downloaded files and
\`policy-document-evidence-manifest-v1.0.json\`. The manifest records SHA-256,
byte count, requested/final URL, status, content type, ETag, Last-Modified,
retrieval time, and explicit flags:

- \`storage_scope = LOCAL_ONLY\`
- \`external_upload_performed = false\`
- \`external_sync_performed = false\`
- \`legal_review_status = NOT_PERFORMED\`
- \`authorization_status = NOT_GRANTED\`

The tool has no upload, publish, sync, distribution, market-data capture, polling,
or backfill function. Do not place the output folder inside the repository or a
cloud-synced folder. Do not commit the downloaded documents or generated local
manifest.

## Important distinction

A matching SHA-256 proves byte integrity relative to the captured file; it does
not prove issuer authenticity, legal applicability, permission to retain market
data, or approval of any source. Mutable source URLs must be re-captured as new
snapshots rather than overwriting earlier files. Human review remains mandatory.
