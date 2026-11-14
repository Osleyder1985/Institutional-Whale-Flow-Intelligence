# Policy document review — 2026-11-14

## Scope

This review covers the source copies and captured snapshot records currently registered under `docs/evidence/policy-documents/`.

It is a technical/documentary analysis, not legal advice, a legal opinion, a retention authorization, or approval to activate any market-data source.

## Evidence inventory

| Evidence ID | Source | Version / date | Evidence available in IWFI |
|---|---|---|---|
| `binance_vision_dataset_terms_v1` | Binance official public-data repository | v1.0; updated 2026-08-26 | Full Markdown source text and captured SHA-256 |
| `cc_by_nc_sa_4_0_legal_code` | Creative Commons official legal code | 4.0 International | Full legal-code text and captured SHA-256 |
| `binance_terms_of_use_adgm_2026_01_05` | Binance official static PDF | Effective 2026-01-05 | Official URL, 73-page count, original 757,137-byte capture and SHA-256 record; PDF bytes remain at official source |

The local capture manifest recorded these SHA-256 values:

- Binance Vision Dataset Terms: `99c4921dbe023cd68c1a447775707d621453cc78aec6ac0bfe2e6c06a5114ee0`
- CC BY-NC-SA 4.0 legal code: `e66c269d4819aaab34b49ef5220c4ddab6756f21bb5180761a4eb8561f2b7bbd`
- Binance ADGM Terms PDF: `9958035d95bff024a86a662fb4fdba45527d55a936e2cb9ed1d7ddf205ca082d`

The local manifest reported all three as `CAPTURED_UNREVIEWED`, with `authorization_status=NOT_GRANTED`, `legal_review_status=NOT_PERFORMED`, `storage_scope=LOCAL_ONLY`, `external_upload_performed=false`, and `external_sync_performed=false`. These status values describe the capture process and are not changed by committing source text to this evidence directory.

## Findings — Binance Vision Dataset Terms

1. **Contractual relationship and hierarchy.** Clauses 1.2–1.5 state that Vision Dataset Terms supplement and form part of Binance Terms of Use; access/use is deemed acceptance; amendments apply prospectively; and Vision Dataset Terms prevail for the contemplated service where inconsistent unless expressly stated otherwise.
2. **Covered material.** Clauses 2.1–2.4 describe historical market data, order-book metrics, trade-flow logs, indicators, machine-readable archives, and analytical time series published through Binance Vision and associated endpoints. Clause 2.4 expressly extends the terms to data derived from, calculated with, or extracted from those datasets, including charts, models, and derivative indicators.
3. **License and use scope.** Clauses 3.1–3.4 refer to CC BY-NC-SA 4.0, bind use including downloading/caching/querying, state a conflict/obligations rule, and exclude commercial licensing absent a separate written enterprise agreement.
4. **Enumerated permitted non-commercial uses.** Clause 4.1 lists academic research, non-monetized open educational projects, algorithmic historical backtesting for purely personal non-production research, and non-commercial open-source data-science evaluations.
5. **Express prohibitions.** Clauses 4.2–4.4 address live proprietary trading execution, automated commercial order generation, compensated signal distribution, exploitation/hosting of data feeds, and integration into commercial financial products, hedge-fund tools, paid newsletters, or commercial trading bots.
6. **Redistributed derivatives.** Clause 4.5 requires attribution to Binance Vision and identical CC BY-NC-SA 4.0 licensing for redistributed derivative work based on the datasets.
7. **Third-party inputs.** Clauses 5.1–5.2 warn that some indicators, chain data, and market metrics may originate from third parties and may have separate rights/restrictions.
8. **Technical access controls.** Clauses 7.1–7.3 require compliance with rate limits and download protocols and prohibit routines designed to circumvent restrictions or impair hosting.

### IWFI implications (not legal conclusions)

- A stated personal/non-commercial project purpose is relevant context for assessing clause 4.1, but it does not by itself establish that every planned IWFI activity fits the enumerated categories.
- A future change in purpose, monetization, distribution, audience, or deployment context requires a new scope assessment before use.
- Binance Vision terms must not be generalized to Binance REST/WebSocket APIs or third-party data without source-specific evidence.
- The repository must preserve attribution and the source version. A source URL alone is insufficient for historical reproducibility where the upstream file can change.
- No causal, trading, or investment conclusion follows from these terms.

## Findings — CC BY-NC-SA 4.0

1. Section 1(k) defines NonCommercial by reference to whether use is primarily intended for or directed toward commercial advantage or monetary compensation.
2. Section 2(a)(1) grants rights to reproduce/share licensed material and produce/share adapted material for NonCommercial purposes, subject to the license conditions.
3. Section 3(a) establishes attribution conditions, including retaining supplied notices and indicating modifications, with the license text or URI.
4. Section 3(b) applies ShareAlike when Adapted Material is shared; it does not automatically place every independent analysis or all IWFI code under CC BY-NC-SA.
5. Section 4 addresses sui generis database rights where they apply; its application depends on the relevant rights and material.
6. Section 6(a) provides automatic termination for non-compliance. Section 6(b) provides automatic reinstatement if the violation is cured within 30 days of discovery, or express reinstatement by the licensor. This cure/reinstatement detail must not be omitted.

### IWFI implications (not legal conclusions)

- The NC element requires a contextual assessment of purpose; it is not accurately reduced to “any future commercial activity is automatically prohibited.”
- ShareAlike attaches to shared Adapted Material under the defined conditions, not indiscriminately to all project components.
- The license grants only rights the licensor has authority to grant; third-party rights may remain.

## Findings — Binance ADGM Terms of Use

The captured 73-page PDF identifies the effective date as 5 January 2026 and names NEST EXCHANGE LIMITED and other ADGM Binance entities. Its opening provisions state that the agreement governs use of a Binance Account and Binance Services made available through the Binance Platform.

Relevant provisions identified in the captured PDF:

- **Clause 29 — Created IP:** contains an assignment/vesting provision for Created IP. The exact defined terms and scope must be read together with clauses 26–30 before applying it to any IWFI work.
- **Clause 36 — Notice of Claim / negotiation:** establishes a notice and negotiation process before arbitration, including the stated 80-day support-resolution period and a 90-day confidential good-faith negotiation period after Notice of Claim.
- **Clause 37 — Agreement to Arbitrate:** provides for individual ICC arbitration, three arbitrators, ADGM seat, English language, and related procedural provisions.
- **Clause 38 — Governing Law:** selects ADGM law for the agreement/claims described there.
- **Clause 39 — Class Action Waiver:** contains a class-action waiver.

### Applicability boundary

This PDF is an account/services agreement, not the standalone Binance Vision dataset license. Vision Dataset Terms refer to Binance Terms of Use and clause 12 points disputes to terms in the Terms of Use, but the exact contracting entity, acceptance, scope, and applicability to a particular public dataset use must be assessed rather than assumed.

## Unresolved questions

1. Does the intended IWFI workflow remain within the specific personal/non-commercial categories in Vision clause 4.1 at each stage (capture, storage, analysis, internal use, publication, and any later distribution)?
2. Which Binance entity and terms version govern each endpoint/source actually used by IWFI?
3. Which indicators or chain metrics contain third-party inputs, and what are those providers' terms?
4. What retention period and snapshot policy are permitted for each source and each document version?
5. What is the precise scope of the Created IP definition and assignment language in ADGM clause 29, and is that agreement applicable to the user's relationship and the relevant service?

## Review status

- Technical source capture and local hash verification: **VERIFIED** for the three local snapshots, based on the user's capture manifest and independent hash checks already recorded in the project work log.
- Repository source text: **PRESENT** for Binance Vision Dataset Terms and CC BY-NC-SA 4.0 legal code.
- ADGM PDF: **OFFICIAL SOURCE LINK + CAPTURE HASH RECORDED**; the binary file itself is not yet stored in this repository.
- Legal applicability: **NOT DETERMINED**.
- Retention authorization: **NOT GRANTED**.
- Source activation approval: **NOT GRANTED**.

This review is a structured issue-spotting aid. It does not resolve the questions above or authorize historical/live data capture.
