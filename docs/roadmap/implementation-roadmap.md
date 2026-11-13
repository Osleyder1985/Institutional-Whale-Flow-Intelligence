# IWFI Implementation Roadmap

Status: prioritized proposal; no production integration or data capture is authorized by this roadmap.

## Product boundary

Initial pilot: native BTC on Bitcoin mainnet and native ETH on Ethereum mainnet. Tokens, other chains, automated trading, autonomous market evaluation, and unapproved provider polling remain out of scope.

Execution is dependency-driven, not calendar-driven. No dates, durations, budgets, or performance targets are invented before access, workload, and evidence are measured.

## Phase 0 — Governance and audit baseline (P0)

**Objective:** ensure repository changes are traceable and main cannot be changed outside the agreed review process.

- [x] Record the initial repository baseline and its limitations — Issue #1 / PR #2.
- [x] Activate the protect-main repository ruleset with deletion, non-fast-forward, linear-history and pull-request requirements — Issue #4.
- [ ] Require the stable contract-test status check and require the branch to be up to date (strict=true) — Issue #4.
- [ ] Verify effective classic/inherited protection details and document non-destructive evidence for deletion/force-push restrictions — Issue #4.

**Exit gate:** Issue #4 is accepted only after required CI and strict up-to-date checks are configured and verified. CI passing alone is not a merge requirement until GitHub enforces it.

## Phase 1 — Provider and source due diligence (P0)

**Objective:** know what evidence can legally and technically be obtained before selecting a source.

- [x] Document candidate-provider capabilities, limitations, plans, terms questions and official references — Issue #3 / PR #5.
- [ ] Verify account-specific endpoint entitlements, applicable personal/non-commercial terms, storage/retention rights, quotas and actual cost.
- [ ] Obtain representative BTC and ETH samples from an authorized source and validate timestamp, units, revisions, coverage and attribution semantics.
- [ ] Record an explicit provider decision; no provider is approved by the current documentation review.

**Exit gate:** no API adapter, paid plan, polling, historical backfill or raw-payload retention before the relevant permissions and user authorization are recorded.

## Phase 2 — Canonical evidence contracts (P0)

**Objective:** establish versioned, provider-neutral contracts before ingestion.

- [x] Source-observation contract and automated schema tests — Issue #6 / PR #7.
- [x] Temporal, evidence-backed address/entity claims — Issue #8 / PR #9.
- [x] Movement Ledger for native BTC/ETH transfers with source and attribution integrity — Issue #10 / PR #11.
- [x] Deterministic observation-resolution policy for duplicate records, contradictions, partial evidence and individual transfer identity — Issue #12 / PR #13.
- [ ] Complete review of all open contract PRs and merge only after their dependency chain, CI and semantics are accepted.

**Exit gate:** a source record, a claim, a movement, and a resolution decision remain distinct and traceable. No ambiguous identity is silently merged; missing facts remain missing; contradictions remain visible.

## Phase 3 — Authorized read-only vertical slice (P0)

**Objective:** prove one complete path from a permitted source to a validated, reproducible BTC/ETH observation.

- [ ] Select one source only after Phase 1 approval.
- [ ] Implement one read-only adapter for a narrowly scoped endpoint and documented product tier.
- [ ] Validate pagination, rate limits, retries, partial responses, timestamps, source hashes and schema revisions.
- [ ] Run deterministic tests against authorized samples; do not use synthetic fixtures as evidence of provider accuracy.
- [ ] Record coverage gaps and provider/source limitations.

**Exit gate:** reproducible sample validation for both supported assets, explicit permission/retention records, and no unexplained data loss or silent coercion.

## Phase 4 — Persistence and historical integrity (P1)

**Objective:** persist evidence only after source rights and identity rules are accepted.

- [ ] Choose storage technology based on retention, query, integrity, cost and operational requirements.
- [ ] Preserve immutable source observations and append-only resolution decisions.
- [ ] Enforce uniqueness, idempotency, supersession and provenance at the persistence boundary.
- [ ] Test restart/replay, partial ingestion, corrections, duplicates, contradictions and reprocessing.
- [ ] Keep raw payloads only where the source terms explicitly permit them.

**Exit gate:** replaying the same authorized inputs and policy version reproduces the same decision without overwriting historical evidence.

## Phase 5 — Attribution and flow interpretation (P1)

**Objective:** distinguish observed transfers from ownership, exchange activity, trades and institutional intent.

- [ ] Evaluate provider labels as claims with provenance and validity intervals.
- [ ] Corroborate important entity claims using genuinely independent evidence.
- [ ] Keep exchange-flow metrics, ETF disclosures and on-chain transfers as separate evidence types.
- [ ] Do not infer beneficial ownership, accumulation, distribution, buy/sell activity or causality from a transfer alone.
- [ ] Report unknown, disputed, delayed and partial states explicitly.

**Exit gate:** every interpretation links to supporting and counterevidence, alternatives, coverage and uncertainty.

## Phase 6 — Research analytics and user-facing evaluation (P2)

**Objective:** add analysis only after the evidence pipeline is validated.

- [ ] Define and test metric formulas, units, windows, revisions and minimum coverage.
- [ ] Evaluate historical flow patterns without inventing thresholds or probabilities.
- [ ] Assess hypotheses with counterevidence and non-causal alternatives.
- [ ] Persist reproducible, user-requested research snapshots.
- [ ] Add presentation/export only when it improves traceability.

**Exit gate:** analyses are reproducible, explicitly user-initiated, and do not generate unsupported signals or claims.

## Operating constraints

- Market analysis runs only when explicitly requested by the user.
- No scheduled polling, backfill, alerting or autonomous analysis is enabled by default.
- No provider is considered approved based solely on a public feature page or synthetic test fixture.
- A transfer is not a trade; an exchange inflow is not proof of a sale; an outflow is not proof of a purchase.
- Correlation is not causality. Unknown is not zero. Provider labels are not verified legal identity.
- Contract PRs remain stacked in dependency order: #7 → #9 → #11 → #13. Independent research and baseline PRs #2 and #5 are not prerequisites for code integration unless their Issues require it.

## Current work register

| Work item | Issue | PR | Current evidence/state |
|---|---:|---:|---|
| Initial baseline and requirements | #1 | #2 | Documentation drafted; roadmap added; governance and provider decisions remain open |
| Provider due diligence | #3 | #5 | Official documentation reviewed; no provider approved; account and sample validation pending |
| Main-branch governance | #4 | — | Ruleset active; required status checks and strict up-to-date requirement missing |
| Source-observation contract | #6 | #7 | CI verified; PR open |
| Address/entity claims | #8 | #9 | CI 49 tests passed; PR open |
| Movement Ledger | #10 | #11 | CI 98 tests passed; PR Draft |
| Observation resolution | #12 | #13 | CI 173 tests passed; PR Draft |
