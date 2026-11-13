# Chain inclusion, canonicality and reorganization contract

- Contract: IWFI chain inclusion evidence v1.0.0
- Related issue: #19
- Networks: Bitcoin mainnet (bitcoin-mainnet) and Ethereum mainnet (eip155:1)
- Status: Proposed; no node/provider integration is authorized

## 1. Separate facts from assessments

An inclusion observation is immutable evidence that a source reported a transaction in a particular block. A canonicality assessment is a derived, versioned conclusion over a specific set of observations. Never mutate the original inclusion record when the assessment changes.

Each inclusion observation records unique observation_id; network and transaction ID; block height and hash; transaction index when supplied; event locator for the individual movement when known; source/provider/node identity and endpoint/method; observed timestamp (UTC); evidence kind and exact evidence reference; source capability/version where relevant.

Block identity is network_id + block_height + block_hash. Transaction identity remains network_id + normalized_transaction_id. Movement identity continues to require the event locator when known. Re-inclusion of the same transaction in another block creates another inclusion observation, not another transaction identity or overwrite.

## 2. State vocabulary

| State | Meaning |
|---|---|
| OBSERVED | Transaction/movement observation exists, but no block inclusion evidence is present |
| INCLUDED | Inclusion and positive canonical-membership evidence are present; no finality claim |
| CANONICALITY_UNRESOLVED | Inclusion exists but canonicality is not demonstrated, or sources conflict |
| NOT_CANONICAL | Positive evidence says this specific block is not canonical |
| SAFE | Ethereum source explicitly reports the block at/behind the safe tag |
| FINALIZED | Ethereum source explicitly reports the block at/behind the finalized tag |

NOT_CANONICAL describes a block inclusion, not a transaction-level reversal. Do not use REVERTED as a synonym for reorg: Ethereum receipt status 0 describes failed EVM execution, while a reorg removes a block from the canonical chain.

REOBSERVED is an event/relationship in history, not a canonicality state. Record a later inclusion as a new observation and link it to the same transaction. A new assessment can supersede the current assessment while old assessments remain queryable.

## 3. Bitcoin mainnet semantics

Bitcoin Core getblock/getblockheader report confirmations and use -1 when the referenced block is not in the main chain. getrawtransaction with an explicit block hash can report in_active_chain. getchaintips exposes active and non-active branches; listsinceblock can report wallet transactions removed after a fork point, but is wallet-scoped.

- Record block height, block hash, transaction index and output index (UTXO_VOUT) when supplied.
- A positive active-chain membership result supports INCLUDED at that observation time.
- A positive result that the referenced block is not in the active chain supports NOT_CANONICAL for that block inclusion only.
- If a transaction is later observed in another active block, append a new inclusion observation. Preserve the earlier orphaned inclusion.
- Absence from a provider response, mempool, or index is not proof of reversal, invalidity, or permanent disappearance.
- This contract does not define a Bitcoin protocol-level SAFE or FINALIZED state and does not impose a confirmation-depth threshold.

## 4. Ethereum mainnet semantics

Ethereum JSON-RPC transaction receipts contain blockHash, blockNumber, transactionIndex, status, and logs. A receipt is tied to a particular block inclusion. Block queries support latest, safe, and finalized tags where the client implements them.

- Record receipt block hash/number and transaction index; retain log index or trace path as event locator for the individual transfer.
- Verify canonicality against the reporting node's current block at the receipt height/hash (or a block-hash-aware canonicality check where supported); record method, result, source and observation time.
- safe and finalized may be recorded only when the node/provider explicitly supports and returns those tags. Preserve exact tag and source. Unsupported methods, null responses or errors yield unresolved evidence, not an inferred state.
- FINALIZED is evidence-backed Ethereum consensus status, not a claim that reversal is impossible; Ethereum consensus documentation describes the economic/consensus assumptions.
- Receipt status=0 means execution failure; it must not be conflated with block reorganization or transfer reversal.
- If the transaction is re-included in a different block after a reorg, append a new receipt/inclusion observation and retain the old one.

## 5. Conflict and transition policy

- Assessments are scoped to one network + block height + block hash and one immutable input set.
- Positive and negative canonicality claims from sources that disagree produce CANONICALITY_UNRESOLVED; do not silently rank providers or majority-vote without a separately approved policy.
- Inclusion alone yields CANONICALITY_UNRESOLVED, not INCLUDED.
- Missing observations never trigger a transition.
- A transition requires a new evidence set and creates a new assessment ID, input fingerprint, timestamp and supersession link.
- A ResearchSnapshot retains the assessment ID and exact evidence set it used. Later reorg evidence does not rewrite the earlier snapshot.

## 6. Determinism and idempotency

Canonicalize and sort observation IDs before computing an assessment input fingerprint. The same observations and policy version must produce the same assessment. Repeating the same observation ID with different content is a validation error at persistence boundary; it must not overwrite the original.

The reference implementation in iwfi/chain_integrity.py is a pure evaluator only. It does not fetch data, persist records, poll, schedule work, backfill history, or determine whether a provider is trustworthy.

## 7. Official references and limits

- Bitcoin Core getblock: https://developer.bitcoin.org/reference/rpc/getblock.html
- Bitcoin Core getrawtransaction: https://developer.bitcoin.org/reference/rpc/getrawtransaction.html
- Bitcoin Core getchaintips: https://developer.bitcoin.org/reference/rpc/getchaintips.html
- Bitcoin Core listsinceblock: https://developer.bitcoin.org/reference/rpc/listsinceblock.html
- Ethereum JSON-RPC: https://ethereum.org/developers/docs/apis/json-rpc/
- Ethereum Execution API block receipts/tags: https://ethereum.github.io/execution-apis/api/methods/eth_getBlockReceipts/
- Ethereum Proof-of-Stake finality: https://ethereum.org/developers/docs/consensus-mechanisms/pos/

These references describe node/API behavior. They do not establish that every third-party provider exposes the same fields or implements the same RPC capabilities. Source capability and actual response evidence must be recorded. No confirmation threshold, wait duration, reorg probability, or provider preference is defined here.
