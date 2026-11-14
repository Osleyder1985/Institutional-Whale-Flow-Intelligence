# Historical controlled-address exposure v1

Status: analytical implementation candidate; synthetic balance snapshots only. No real BTC or ETH balance snapshot has been ingested.

## Inputs

Each snapshot batch contains:
- entity scope and asset/network;
- snapshot time, recording time, block height/hash and canonicality/confirmation;
- one address balance per record, in satoshis (BTC) or wei (ETH);
- a source observation reference for every address balance;
- an inventory-coverage declaration with expected/observed/unresolved address counts, evidence reference and review provenance.

Address claims are resolved at the snapshot time and knowledge cutoff. Only VERIFIED + REVIEWED CONTROLLED_BY claims with supporting evidence, no counterevidence, known validity bounds and both recorded/reviewed timestamps at or before the cutoff are admitted.

## Exposure semantics

Two values are kept distinct:

- `known_address_exposure_atomic`: sum of balances for addresses that are admissibly attributed to the scope entity.
- `total_entity_exposure_atomic`: emitted only when the inventory itself has reviewed evidence of completeness, expected and observed address counts agree, there are zero inventory gaps, and every address in the batch resolves to the same scope entity.

A partial or unresolved inventory never becomes a total entity exposure. A controlled address is not proof of beneficial ownership. Custodial customer funds must not be described as proprietary treasury.

## Historical changes

For adjacent snapshots of the same entity and asset:
- known-address delta is emitted only when the same non-empty attributed address set is present in both snapshots;
- total entity delta and relative change are emitted only when both snapshots have complete coverage;
- candidate direction is a descriptive net balance increase/decrease/flat state, not proof of purchases, sales, intent or market accumulation/distribution;
- every candidate remains `NOT_CALIBRATED`; no thresholds, probabilities or trading signals are invented.

All balances use integer atomic units. Relative change is serialized as an exact reduced rational string (numerator/denominator), avoiding float and rounding. BTC and ETH are never mixed.

## Test boundary

Tests use synthetic balances to verify coverage gates, claim resolution, historical deltas, duplicate handling and units. They are not blockchain samples or market results. Real-data validation requires source approval, a reproducible balance snapshot, verified address inventory, and reconciliation to chain state. No polling or backfill is enabled.

See Issue #111 and source gate Issue #3.
