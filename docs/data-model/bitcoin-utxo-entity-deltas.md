# Bitcoin UTXO entity-delta accounting v1

Status: implementation candidate; synthetic contract tests only. No real mainnet transaction has been ingested or validated by this module.

## Why a separate model is required

A Bitcoin transaction does not define a unique sender for each output. It may consume multiple UTXOs owned by different addresses and create multiple outputs, including change. A generic from-address/to-address transfer record would invent an input-to-output pairing.

The new transaction contract preserves inputs and outputs independently. Each input is identified by vin and its previous outpoint (previous txid + vout); each output is identified by vout. The transaction also carries block height/hash, event time, recording time, canonicality, confirmation status, fee and source-observation references.

## Accounting

For each entity, the observed address-set delta is:

`sum(attributed output amounts) - sum(attributed input amounts)`

The implementation does not pair inputs with outputs, assign change heuristically, or infer common ownership from transaction co-spend. Each input and output is independently resolved against an existing claim.

- Only VERIFIED + REVIEWED CONTROLLED_BY claims with evidence, no counterevidence, both validity bounds and a valid event-time interval are admitted.
- Provider labels, inferred claims, OPERATED_BY, custody, association and unknown claims do not establish economic control.
- Conflicted/disputed addresses remain unattributed.
- Claims or reviews recorded after known_at_utc do not rewrite the earlier knowledge state.
- All values are integer satoshis; no binary floating point is used.
- The transaction is accepted for accounting only if sum(inputs) = sum(outputs) + fee.
- Fees are reported once per transaction and are not allocated to an entity.
- Duplicate transaction IDs and duplicate input/output indices fail closed.
- Non-canonical or unconfirmed transactions are excluded.

## Interpretation and limits

The output is an observed address-set delta for the supplied transactions. It is not a complete entity balance, total exposure, beneficial ownership estimate, trade, purchase/sale, or accumulation/distribution classification. A transaction may have unknown or conflicted endpoints; known endpoint deltas can be emitted as partial observations but must not be represented as full entity-wide coverage.

The current implementation does not infer input/output pairing, wallet clusters, CoinJoin ownership, change outputs, entity completeness, opening balances, reorg history, or fee payer identity. Coinbase transactions are outside this first contract because their input/reward semantics differ from ordinary transactions.

## Real-data acceptance

The schema and tests use synthetic records to verify software rules only. They are not blockchain evidence. Real-data acceptance requires a source whose cost, access terms, usage rights and retention have been approved; a reproducible mainnet sample; block hash/height and canonicality verification; all input previous outpoints and outputs reconciled to the transaction; and evidence-backed claims. No polling, backfill or persistent capture is enabled by this module.

See Issue #109 and source gate Issue #3.
