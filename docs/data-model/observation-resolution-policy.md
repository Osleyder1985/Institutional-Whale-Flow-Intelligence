# Observation Resolution Policy v1.1.0

Status: proposed, deterministic policy implemented as a pure in-memory resolver; no persistence or provider integration.

## 1. Separate domain concepts

- **Observation:** immutable record received from one provider. Repeated retrievals remain separate observations.
- **Transaction:** network-scoped transaction identified by `network_id + transaction_id`.
- **Transfer event / Movement:** one transfer inside a transaction, identified by transaction identity plus a protocol-specific event locator.
- **Observation link:** explicit relation between two observations; a link is not itself a movement.
- **Resolution decision:** immutable, versioned output containing the input fingerprint, policy version, links, events, evidence and reasons. A correction creates a new decision and may reference the previous decision through `supersedes_decision_id`.

## 2. Strong identity

A strong transfer-event identity requires all of:

1. Equal network IDs.
2. Equal normalized transaction IDs.
3. Equal valid protocol event locators.

Supported locators in this version:
- Bitcoin: `UTXO_VOUT` (output index).
- Ethereum native ETH: `EVM_TRACE_PATH` (internal call path) or `EVM_TX_VALUE` (the transaction's native-value transfer). `EVM_LOG_INDEX` is excluded because it identifies contract logs, typically token events; token asset identities are outside this contract.

Transaction IDs are normalized case-insensitively because the supported identifiers are hexadecimal. Numeric locator components are canonicalized so `0/05` and `0/5` identify the same trace path, and Bitcoin `UTXO_VOUT` values such as `00` and `0` identify the same output index. Original values remain in field-level evidence.

A transaction hash alone is not a transfer-event identity. If the hash matches but either observation lacks a valid locator, the relationship is only a candidate. Different locators within the same transaction are distinct events.

## 3. Candidate and no-match rules

- Same transaction, missing/invalid locator: `CANDIDATE`; never merged.
- Missing transaction ID: a `CANDIDATE` is emitted only when the network matches and at least three exact, non-null values match among `asset_id`, `amount`, `unit`, `from_address`, `to_address`, and `event_time_utc`. This three-field rule is a deterministic review-candidate blocking rule, not a confidence score or event identity; it never authorizes a merge. With fewer than three shared fields, evidence remains insufficient.
- Different network IDs: `NO_MATCH`.
- Different transaction IDs on the same network: `NO_MATCH`.
- Different event locators in the same transaction: `NO_MATCH`.
- Matching amount, addresses, or timestamps alone never produce a strong match.
- Exchange/ETF aggregate metrics and address-label observations are invalid inputs to transfer resolution.

## 4. Complementary facts and conflicts

Only observations with a strong event identity are grouped. Within such a group:
- Missing values may be complemented by a unique, non-null value from another observation.
- Every value retains its observation ID and provider provenance.
- Decimal amounts are compared exactly using `Decimal`; equivalent decimal formatting is not a conflict.
- Conflicting non-null values remain separately visible by field. No average, preferred-provider rule, or arbitrary winner is applied.
- A contradictory event is ineligible for quantitative analysis.

Original observations are never modified. No missing field is converted to zero.

## 5. Source-record repeats and revisions

A repeat from the same provider, endpoint and record ID with the same payload hash is reported as `EXACT_REPEAT`. The same provider record ID with a different payload hash is reported as `SAME_RECORD_DIFFERENT_PAYLOAD`, not silently deduplicated; it may represent a provider correction or revision. These source-record relations are independent of event identity.

If an exact repeat of the same provider record and payload claims two different strong event identities, both events remain separate and the decision is marked `RESOLVED_WITH_RELATION_CONFLICTS` with reason `SOURCE_RECORD_REPEAT_CONTRADICTS_EVENT_IDENTITY`. This surfaces a source/parser integrity contradiction instead of silently accepting either identity.

## 6. Provider-declared duplicate references

The observation-level `quality.duplicate_of` field is preserved as an explicit provider/ingestion assertion and emitted as a separate observation link when its target is present in the resolution input. It never overrides transaction/event identity.

- If the referenced observation has the same strong event identity, the duplicate assertion is consistent with the on-chain identity.
- If both observations have strong but different event identities, the resolver retains both events and marks the decision `RESOLVED_WITH_RELATION_CONFLICTS`; it does not merge them.
- If the target is not part of the current input, the original observation retains the external reference; no identity is inferred.
- A duplicate observation must reference a non-empty, different observation ID.

This relationship is distinct from provider record ID + payload-hash repeat/revision detection.

## 7. Transfer fragments and economic relationships

Distinct transaction IDs or distinct event locators remain distinct events even when amounts, endpoints or times are similar. Fan-in, fan-out, batches, parent/child transfers and possible common economic operations are not inferred or aggregated by this policy. They require a separate evidence-backed relationship model.

## 8. Source quality, historical evidence and analytical eligibility

Source quality is not a single real-time freshness or trust score. This policy distinguishes:

- `VALID`: source observation passes the provider/ingestion quality checks.
- `PARTIAL`: observation is usable for the fields it actually contains; missing values remain missing.
- `DELAYED`: observation arrived late but may still support historical reconstruction. Its delayed status is preserved in field-level evidence. It does not establish that the event was available to a real-time monitor at event time.
- `DUPLICATE`: observation is retained and linked for audit, but is excluded from event field evidence, resolved values and the event's contributing `observation_ids`. Its ID is exposed separately as `excluded_observation_ids` when it shares a strong event identity with an event supported by other observations. A duplicate alone cannot create an event or make it analytically eligible.
- `INVALID` / `QUARANTINED`: retained as adverse quality evidence and make the event ineligible.

Only `VALID`, `PARTIAL` and `DELAYED` observations may contribute event fields. The Movement Ledger validator accepts the same set as source observations. A delayed observation is admissible for historical integrity validation, not proof of real-time availability. This contract defines no freshness threshold or real-time eligibility state; consumers requiring real-time monitoring must apply a separately specified and tested freshness policy.

## 9. Resolution states and analytical eligibility

Each strong event receives:
- `COMPLETE`: all required analytical fields, including confirmation status, have one unambiguous value.
- `PARTIAL`: one or more required fields remain missing.
- `CONTRADICTORY`: at least one field has conflicting non-null values.
- `INVALID`: at least one source is invalid/quarantined.

Only `COMPLETE` events with `confirmation_status=CONFIRMED` and no material conflicts are `ELIGIBLE`. `DUPLICATE` observations never contribute to that completeness decision; `DELAYED` observations may contribute to historical completeness with their quality status preserved. `PENDING` or `UNKNOWN` confirmation is `INELIGIBLE` with an explicit reason. Other states are also `INELIGIBLE`. A candidate link does not create an event and is not eligible for event-level analytics. Eligibility does not establish institutional attribution, trade direction, or buy/sell intent.

## 10. Determinism and audit

The resolver:
- sorts observations, links, evidence and events deterministically;
- indexes candidate comparisons by event identity, transaction identity, source record and shared partial-field keys instead of generating a global all-pairs matrix;
- materializes strong/candidate links and relevant source-record revisions; NO_MATCH remains available through pair classification rather than an exhaustive quadratic list;
- derives a SHA-256 input fingerprint from canonical observations and a separate decision-context fingerprint from the policy version, input fingerprint and optional superseded decision ID;
- produces the same result for the same inputs regardless of input order;
- performs no I/O, persistence, provider calls, wallet clustering or probabilistic inference;
- accepts an optional previous decision ID for explicit supersession without overwriting prior output;
- rejects unknown source-quality states and invalid asset/network combinations.

Reprocessing identical inputs with the same policy version and supersession context is idempotent. Changing the superseded decision reference changes the decision-context fingerprint and decision ID even when the observation input fingerprint is unchanged. Policy changes require a policy-version change and therefore produce a distinct decision ID.

## 11. Scope and limitations

This implementation is an in-memory policy engine and test suite only. Pairwise work can still grow inside a large same-transaction or same-candidate bucket; production-scale performance has not been benchmarked. It does not persist observations or decisions, assign a canonical event in a database, implement provider adapters, resolve chain reorganizations/finality, infer common control, group transfers economically, or generate whale metrics/signals. Unsupported or absent event locators remain unresolved candidates rather than being guessed.


## 12. Cross-contract normalization

The movement integrity validator compares transaction IDs case-insensitively, normalizes EVM addresses case-insensitively, and canonicalizes numeric protocol locator components. This allows equivalent provider encodings (for example, vout `00` versus `0`) to be validated without weakening network or event identity. Invalid or network-incompatible locators do not compare as equal.
