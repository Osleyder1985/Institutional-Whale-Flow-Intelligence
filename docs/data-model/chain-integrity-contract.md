# Chain Integrity Contract v1 — Bitcoin and Ethereum mainnet

Status: proposed; synthetic fixtures only. Related: Issue #19, Issue #16.
This contract defines evidence and derived assessments. It does not activate nodes/providers, capture data, poll, backfill, or authorize a production backend.

## 1. Core separation

A chain observation is an immutable statement made by a named source at an observed time. A canonicality assessment is a versioned interpretation over a defined set of observations and policy version. Never overwrite an observation to reflect a later chain view.

The same transaction may have multiple inclusion observations. An inclusion is identified by network + transaction ID + block hash + transaction position when available. A transfer within that transaction remains identified by the Movement Ledger key: network + normalized transaction ID + protocol event locator. Block inclusion identity and transfer identity are distinct.

NOT_OBSERVED is not an evidence state. Missing response, timeout, pruned data, unsupported RPC, and absent index entry are not proof of non-inclusion or reversal.

## 2. Immutable evidence envelope

Each record stores a unique observation ID; network identifier; source kind and stable source ID; transaction ID/hash; observation kind and UTC observation time; inclusion facts (height, hash, transaction position) when observed; source-asserted active-chain status only when explicitly provided; nullable protocol event locator; and source/API/client version plus reproducible evidence reference, subject to provider terms. No secrets.

The envelope records what the source said, not what IWFI concludes. Different sources' contradictory records are retained.

## 3. Network-specific evidence semantics

### Bitcoin mainnet

- MEMPOOL_SEEN means a particular source reported the transaction in its mempool at observed_at. It is not block inclusion.
- BLOCK_INCLUDED records inclusion in a specific block identified by height and hash; transaction position is retained when available.
- BLOCK_STATUS records a source's explicit status for a particular block. Bitcoin Core getblock/getblockheader expose confirmations and report -1 for a block not on the main chain. getrawtransaction with an explicit block hash can report in_active_chain. Preserve exact RPC/method, response time and returned values; do not generalize these fields to every provider.
- If an old block is reported outside the active chain, assess that specific inclusion as NOT_CANONICAL only with positive evidence. Do not say the transaction was economically reversed: it may later be re-included.
- A later inclusion of the same txid in a different block is a new inclusion observation linked to the same transaction. Re-evaluate each transfer event separately using its original UTXO_VOUT locator.
- A transaction returning to a mempool is source-specific evidence only. It is not guaranteed: policy, conflicts, eviction, node configuration and observation timing affect mempool visibility.
- Confirmation count is source-reported chain depth, not protocol finality. This contract defines no universal confirmation threshold and no FINALIZED state for Bitcoin.

### Ethereum mainnet

- BLOCK_INCLUDED records transaction receipt or block inclusion, retaining blockHash, blockNumber, transactionIndex, and receipt/log facts when available.
- A receipt is block-specific. Its existence alone is not an enduring canonicality guarantee. Compare its blockHash with the block at the same height from the same source view; preserve both responses and timestamps. Cross-source disagreement remains unresolved.
- Preserve logIndex and trace path as event locators where available. A transaction may contain multiple logs/internal transfers; never collapse them by transaction hash.
- Record latest, safe, and finalized tags only when the RPC endpoint supports them and the exact returned block number/hash is captured. latest may be reorganized; safe is a source's safe-head view; finalized is the execution client's view of the consensus-finalized head. A tag is evidence of that source's view, not universal proof independent of source/client integrity.
- FINALIZED assessment is allowed only when the included block is at or below a captured finalized checkpoint from an identified source, with checkpoint number/hash and observed time preserved. If unsupported, unavailable, inconsistent, or only safe is reported, status is not FINALIZED.
- If a transaction hash is later included in another block after a reorg, create a new inclusion observation. Preserve the previous receipt/inclusion. Do not reuse the old block hash or mutate the prior snapshot.

## 4. Derived assessment vocabulary

These values are assessments, not source observations:
- OBSERVED: transaction seen by a source; no block inclusion established.
- INCLUDED: at least one inclusion is evidenced, but canonicality has not been established by sufficient current evidence.
- CANONICALITY_UNRESOLVED: evidence conflicts, is incomplete, stale, or cannot establish whether the referenced inclusion is canonical.
- NOT_CANONICAL: positive evidence establishes that the referenced prior inclusion block is no longer in the active/canonical chain. This applies to that inclusion, not as a blanket transaction reversal.
- REOBSERVED: a later observation exists after an earlier inclusion was assessed NOT_CANONICAL; specify whether it is mempool-only or a new inclusion.
- FINALIZED: Ethereum-only, supported by captured finalized checkpoint evidence as described above.
- UNKNOWN: no admissible evidence supports a more specific assessment.

REVERTED is deliberately excluded: it ambiguously conflates chain reorganization with application-level reversal, replacement, refund, or compensating transfer. Those are distinct domain events and require separate evidence.

## 5. Transition and supersession rules

- OBSERVED -> INCLUDED: add a new inclusion observation.
- INCLUDED -> CANONICALITY_UNRESOLVED: conflicting or insufficient chain-view evidence appears.
- INCLUDED -> NOT_CANONICAL: positive evidence establishes that the referenced block left the active/canonical chain.
- NOT_CANONICAL -> REOBSERVED: later mempool sighting or inclusion is observed; record observation kind and new block facts, if any.
- Ethereum INCLUDED -> FINALIZED: captured finalized checkpoint evidence covers the inclusion block and is internally consistent.
- FINALIZED is not downgraded by absence or one provider's contradictory response. A genuine consensus-level contradiction is escalated as a critical integrity incident; retain evidence and create a new CANONICALITY_UNRESOLVED assessment pending investigation rather than silently rewriting history.
- No transition deletes observations, movements, decisions, or snapshots. Each assessment records policy version, input observation IDs/fingerprint, source set, assessed time, and supersedes assessment ID (nullable for first assessment).
- A ResearchSnapshot freezes exact assessment and evidence IDs available at creation. Later evidence creates a new assessment and, only on a new user-requested run, a new snapshot.

## 6. Multi-source conflict handling

Do not select a winner by provider count or arbitrary priority. Preserve each source assertion with source identity, client/API version, observed time and raw-field provenance (payload retention remains governed by provider terms). If sources disagree about block hash at a height, active-chain membership, receipt, or finalized head, return CANONICALITY_UNRESOLVED unless a network-specific evidence rule resolves the exact inclusion. A single provider's silence is not contradictory evidence.

## 7. Validation requirements

- Block height, transaction index and output/log indexes are non-negative integers when present.
- Block hash and transaction ID must match network-specific format; schema validates basic shape, while network-specific semantic validation checks canonical normalization.
- Bitcoin transfer event locator remains UTXO_VOUT; Ethereum event locators remain the Movement Ledger's supported EVM_TRACE_PATH / EVM_TX_VALUE or log locator where separately defined. Never substitute transaction position for transfer event identity.
- observed_at is UTC RFC 3339; event/block timestamps are not substitutes for observation time.
- Unknown fields, missing fields, malformed values, and unsupported source semantics remain explicit validation failures or unresolved states, not guessed defaults.

## 8. Non-goals and release gate

No automatic chain watcher, polling, mempool subscription, RPC credentials, provider activation, raw-payload retention, historical backfill, production persistence, economic intent classification, purchase/sale inference, or market-impact claim is authorized. The next implementation step after contract acceptance is a separate, explicitly scoped design for ingestion and persistence that satisfies provider terms and Issue #16.
