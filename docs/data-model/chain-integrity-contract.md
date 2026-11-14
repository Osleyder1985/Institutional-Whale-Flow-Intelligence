# Chain Integrity Contract v2 — Bitcoin and Ethereum mainnet

Status: implemented as a pure evaluator with synthetic fixtures; no provider integration or production persistence is authorized. Related: Issues #18 and #19, Issue #16.

## 1. Immutable facts and versioned assessments

A chain observation is an immutable statement made by a named source at an observed UTC time. A canonicality assessment is a derived interpretation over a defined evidence set and policy version. New evidence creates a new assessment; it never edits an earlier observation, assessment, movement, decision, or ResearchSnapshot.

Every observation identifies network, source kind, stable source ID, source view ID, method/client/API version, observation ID and observed time. `source.view_id` identifies the provider/node chain view or session context used to make the assertion. If the source cannot provide a stable view identifier, it must not be fabricated; same-view sequencing/finality conclusions remain unresolved.

Transaction inclusion identity is network + transaction ID + block height/hash + transaction position when available. Transfer identity remains network + normalized transaction ID + protocol event locator. One transaction can contain multiple transfers; `UTXO_VOUT`, `EVM_TRACE_PATH`, `EVM_TX_VALUE` and separately scoped `EVM_LOG_INDEX` are retained independently. Transaction position is never a transfer locator.

## 2. Bitcoin mainnet

- `MEMPOOL_SEEN` is a source-specific mempool observation, not block inclusion.
- `BLOCK_INCLUDED` records a transaction in a particular block (height/hash/transaction index).
- `BLOCK_STATUS` records the source's explicit status for that exact block.
- `ACTIVE` supports `INCLUDED` for that block at the observation time; `NOT_ACTIVE` supports `NOT_CANONICAL` for that block inclusion only.
- A later inclusion in another block is a new inclusion observation. `REOBSERVED` is allowed only when the old `NOT_ACTIVE` and later `ACTIVE` evidence are strictly ordered and come from the same source ID and same non-empty source view ID. Otherwise the result is `CANONICALITY_UNRESOLVED`.
- Bitcoin has no protocol-level `FINALIZED` state in this contract. Confirmation depth is source-reported chain depth; no universal threshold is invented.

## 3. Ethereum mainnet

- Preserve receipt blockHash, blockNumber, transactionIndex, execution status, and transfer event locator independently.
- A receipt/inclusion without positive canonical-membership evidence is `CANONICALITY_UNRESOLVED`, not `INCLUDED`.
- `SAFE` is not treated as `FINALIZED`.
- A `FINALITY_CHECKPOINT` is an independent block observation. It has no transaction ID and no transaction inclusion object; it records a separate `checkpoint` (block height/hash), the explicit `finalized` tag, source ID, source view ID, method and observation time.
- `FINALIZED` requires all of the following: (1) positive `ACTIVE` evidence for the exact transaction inclusion block; (2) a later `finalized` checkpoint; (3) same source ID and same non-empty source view ID for both assertions; and (4) checkpoint height at or above the inclusion height. Height comparison alone is insufficient.
- This remains an assessment of the reporting source's view, not independent cryptographic proof of consensus ancestry or a guarantee against consensus failure. Provider/client capabilities and evidence provenance must be retained.

## 4. Assessment states

| State | Meaning |
|---|---|
| `UNKNOWN` | No admissible evidence |
| `OBSERVED` | Transaction seen (for example, mempool) without block inclusion |
| `CANONICALITY_UNRESOLVED` | Inclusion exists but canonical membership is not positively established, evidence is stale/incomplete, or sources/views conflict |
| `INCLUDED` | Positive canonical-membership evidence exists for the exact block; no Ethereum finality claim |
| `NOT_CANONICAL` | Positive evidence says this specific block inclusion is no longer canonical |
| `REOBSERVED` | A strictly later inclusion is observed after positive non-canonical evidence from the same source view |
| `FINALIZED` | Ethereum-only source-view assessment meeting every checkpoint condition above |

`NOT_CANONICAL` is not an economic/application reversal. `REVERTED` is excluded because it conflates a chain reorganization with failed execution, replacement, refund, or compensating transfer. Absence, timeout, pruning, or missing index entries never prove non-inclusion or reversal.

## 5. Conflict, determinism and history

- Never resolve cross-provider disagreement by majority vote or implicit provider priority.
- Conflicting ACTIVE/NOT_ACTIVE assertions for the same block remain unresolved.
- Multiple block hashes without a same-source, same-view, strictly ordered reorg sequence remain unresolved.
- The evaluator returns sorted evidence IDs, distinct movement event locators, a policy version and a deterministic SHA-256 assessment fingerprint over the canonicalized full evidence records (not only their IDs). Identical evidence under the same policy produces the same fingerprint; changing evidence content changes the fingerprint. UTC chronology is parsed as timestamps, including fractional seconds, rather than compared lexically.
- A ResearchSnapshot must freeze the assessment fingerprint/ID and exact evidence observation IDs it used. Later assessments are appended; historical snapshots are not recalculated. The current evaluator is pure and does not implement persistence or snapshot storage.

## 6. Synthetic test requirements

Fixtures/tests cover mempool-only observations, inclusion without canonicality, positive and negative block status, same-view re-inclusion, cross-view ambiguity, provider conflict, independent Ethereum checkpoints, finality without active inclusion, multiple event locators in one transaction, determinism, idempotency, and preservation of the earlier assessment result after later evidence.

## 7. Non-goals and release gate

No node/provider activation, polling, mempool subscription, RPC credentials, backfill, real ingestion, production persistence, raw-payload retention, economic intent classification, purchase/sale inference, or market-impact claim is authorized. Persistence must separately implement append-only observations/assessments and snapshot references under Issue #16 and provider terms.

## 8. Official protocol references

- Bitcoin Developer Reference — getblock: https://developer.bitcoin.org/reference/rpc/getblock.html
- Bitcoin Developer Reference — getrawtransaction: https://developer.bitcoin.org/reference/rpc/getrawtransaction.html
- Ethereum Execution APIs — JSON-RPC methods and block tags: https://ethereum.github.io/execution-apis/
- ethereum.org — Proof-of-stake finality: https://ethereum.org/developers/docs/consensus-mechanisms/pos/

These sources describe protocol/client interfaces. They do not establish that every third-party provider exposes the same fields or that a provider's response is independent consensus proof.
