# Local policy-evidence extraction

This step consumes the private snapshots produced by
\`scripts/acquire_policy_documents.py\`. It verifies each document's SHA-256 and
byte count against the capture manifest before extracting any text.

## One command

\`\`\`powershell
python scripts/extract_policy_evidence.py --evidence-dir "$HOME\IWFI-private-evidence\policy-documents"
\`\`\`

The command creates
\`policy-document-extraction-bundle-v1.0.json\` in the same private folder.
It contains extracted text and therefore **must remain outside the public
repository and cloud-synchronized folders**. Share it with an authorized reviewer
only through a suitable private channel. Do not commit it.

TXT and Markdown are handled with Python's standard library. PDF extraction uses
the optional \`pypdf\` package; if it is absent, the tool fails explicitly without
changing the source snapshots. The package can be installed in the user's local
Python environment; it is not required by the repository's automated test suite.

## Scope and safeguards

- Recomputes SHA-256 and byte count before processing each snapshot.
- Rejects missing files, symlinks, path traversal, malformed manifests, and
  contradictory integrity metadata.
- Emits section-heading and topic locators to make later review reproducible.
- Preserves source identifiers, hashes, retrieval metadata, and authorization
  status in the output.
- Never sends, uploads, syncs, publishes, or overwrites evidence.
- Does not decide legal applicability, retention rights, licensing compliance,
  or source authorization. Those remain separate human/legal review decisions.

The generated bundle contains the full extracted source text. It is private
evidence, not a public audit artifact.
