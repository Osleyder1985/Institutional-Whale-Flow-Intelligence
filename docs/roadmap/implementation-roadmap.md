# IWFI Implementation Roadmap

Status: dependency-driven roadmap, updated after merge of PR #52. No production provider integration, capture, polling or backfill is authorized by this document.

## Product boundary

Initial pilot: native BTC on Bitcoin mainnet and native ETH on Ethereum mainnet. Tokens, other chains, automated trading, autonomous market evaluation and unapproved provider polling remain out of scope.

The product's first question is evidence of **who** is acting and **what** they did. The system must not claim to identify an institutional participant when the source exposes only an anonymous exchange execution, an address label, a transfer or an aggregate flow.

## Phase 0 — Governance and audit baseline (P0)

- [x] Initial repository baseline — Issue #1 / PR #2.
- [x] Main ruleset activated — Issue #4.
- [ ] Require the stable contract-test status check and strict up-to-date branch requirement — Issue #4.
- [ ] Verify effective deletion/force-push protections and document evidence — Issue #4.

**Exit gate:** repository enforcement, not merely passing CI, must demonstrate the agreed main-branch protections.

## Phase 1 — Provider and source due diligence (P0)

- [x] Official-documentation comparison for Arkham, CryptoQuant, Glassnode, Nansen, CoinGlass and primary-source categories — Issue #3 / PR #5.
- [ ] Verify account-specific endpoint entitlements, applicable personal/non-commercial terms, storage/retention rights, quotas and actual cost.
- [ ] Obtain authorized representative BTC and ETH samples.
- [ ] Validate timestamps, units, revisions, history, coverage and attribution semantics against those samples.
- [ ] Record an explicit source decision: APPROVED, APPROVED_WITH_RESTRICTIONS or NOT_APPROVED.

**Current decision:** no commercial provider is approved. CryptoQuant is the best-documented on-chain candidate, not an approved source. Arkham remains a candidate for entity/address intelligence; its account access, endpoint coverage, methodology and retention rights are unverified. Public exchange trades can prove venue executions but generally do not reveal the customer or beneficial owner.

**Exit gate:** source-specific permissions and real samples are verified for both assets. No paid plan, API adapter, polling, backfill or raw-payload retention before explicit approval.

## Phase 2 — Canonical evidence contracts (P0)

- [x] Source Observation contract and tests — Issue #6 / PR #7.
- [x] Temporal, evidence-backed Attribution Claims — Issue #8 / PR #9.
- [x] Native BTC/ETH Movement Ledger — Issue #10 / PR #11.
- [x] Deterministic observation resolution — Issue #12 / PR #13.
- [x] Actor Registry and individual Trade Execution contracts — Issue #51 / PR #52.

**Exit gate:** observations, attribution claims, transfers, actor identities and individual trade executions remain distinct, versioned and traceable. Unknown identities remain unknown; contradictions remain visible; transfer and aggregate flow evidence cannot be represented as individual trades.

## Phase 3 — Integrated architecture and authorized read-only vertical slice (P0)

- [ ] Complete the end-to-end integration design and traceability matrix — Issue #50.
- [ ] Complete source/account approval — Issue #3.
- [ ] Select one source only after Phase 1 approval.
- [ ] Implement one narrowly scoped, read-only adapter for that source and product tier.
- [ ] Validate pagination, rate limits, retries, partial responses, timestamps, hashes, schema revisions and data quality.
- [ ] Run deterministic tests against authorized real samples; synthetic fixtures are not evidence of provider accuracy.
- [ ] Demonstrate both BTC and ETH through the same canonical pipeline, with actor attribution explicitly UNKNOWN when the source does not identify a participant.

**Exit gate:** a reproducible end-to-end path from permitted source observation to a typed, quality-checked result for both assets, with no silent data loss/coercion and explicit identity limitations.

## Phase 4 — Persistence and historical integrity (P1)

- [ ] Select storage based on retention, query, integrity, cost and operational requirements.
- [ ] Preserve immutable observations and append-only claims/resolution decisions within source rights.
- [ ] Enforce uniqueness, idempotency, supersession and provenance at persistence boundaries.
- [ ] Test restart/replay, partial ingestion, corrections, duplicates, contradictions and reprocessing.

**Exit gate:** replaying identical authorized inputs and policy versions reproduces the same decisions without overwriting prior knowledge.

## Phase 5 — Attribution and flow interpretation (P1)

- [ ] Evaluate provider labels as claims with provenance and validity intervals.
- [ ] Corroborate material entity claims with genuinely independent evidence.
- [ ] Keep exchange metrics, ETF disclosures, on-chain transfers, holdings and individual executions separate.
- [ ] Never infer beneficial ownership, accumulation, distribution, intent or price causality from a transfer alone.
- [ ] Report unknown, disputed, delayed and partial states explicitly.

**Exit gate:** every interpretation links to supporting evidence, counterevidence, alternatives, coverage and uncertainty.

## Phase 6 — Research analytics and user-facing evaluation (P2)

- [ ] Define and test metric formulas, units, windows, revisions and minimum coverage.
- [ ] Evaluate historical patterns without invented thresholds or probabilities.
- [ ] Assess hypotheses with counterevidence and non-causal alternatives.
- [ ] Persist reproducible, explicitly requested research snapshots.
- [ ] Add presentation/export only where it improves traceability.

**Exit gate:** analyses are reproducible, user-initiated and do not generate unsupported signals or claims.

## Operating constraints

- Market analysis runs only when explicitly requested.
- No scheduled polling, backfill, alerts or autonomous analysis by default.
- No provider is approved solely by a public feature page or synthetic fixture.
- A transfer is not a trade; exchange inflow is not proof of sale; outflow is not proof of purchase.
- Correlation is not causality. Unknown is not zero. Provider labels are not verified legal identity.
- A public exchange execution may be confirmed while its customer and beneficial owner remain unknown.

## Current work register

| Work item | Issue | PR | Current state |
|---|---:|---:|---|
| Initial baseline | #1 | #2 | Merged |
| Provider due diligence | #3 | #5 | Documentation reviewed; account/sample approval pending |
| Main-branch governance | #4 | — | Ruleset active; enforcement verification incomplete |
| Source Observation | #6 | #7 | Merged |
| Attribution Claims | #8 | #9 | Merged |
| Movement Ledger | #10 | #11 | Merged |
| Observation resolution | #12 | #13 | Merged |
| Actor Registry + Trade Execution | #51 | #52 | Merged; CI success on final HEAD |
| End-to-end architecture | #50 | — | Open; next integration-design task |

## Immediate next gate

Complete Issue #3's account-level/source-sample checks before selecting an adapter. In parallel, complete Issue #50's integration architecture using the now-merged contracts. Only then begin the first authorized read-only BTC/ETH vertical slice.
