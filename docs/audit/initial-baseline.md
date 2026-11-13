# IWFI Initial Repository Audit

## 1. Audit scope

This baseline records the repository state observed during the initial audit for Institutional & Whale Flow Intelligence (IWFI). It is a documentation-only baseline; it does not claim that any data connector, market-analysis function, or production component exists.

Pilot assets: Bitcoin (BTC) and Ethereum (ETH).

## 2. Repository evidence

| Item | Observed result | Evidence |
|---|---|---|
| Repository | Public repository | GitHub repository metadata |
| Default branch | `main` | Repository metadata |
| Root contents | `README.md` only | Default-branch tree |
| README | One heading; no project specification | Retrieved file content |
| Initial commit | `af2254ddbb636b6c60a8b4a4245eeed2fc19786a` | Commit history |
| Open Issues | Issue #1 exists | Repository Issues search |
| Pull Requests | No PRs found | Repository PR search |
| Repository rulesets | Empty list | GitHub rulesets endpoint |
| Branch protection indicator | `main` reports `protected: false` | Branch listing |
| Direct protection details | Not readable by connected integration (HTTP 403) | Branch-protection endpoint |

The empty repository rulesets response and `protected: false` branch metadata are evidence that no effective repository ruleset or classic protection was visible at audit time. Organization-level inherited policy was not independently verified. Do not represent inaccessible settings as confirmed absent.

## 3. Baseline conclusion

The repository is at inception. There is no existing application architecture, executable source code, test suite, CI workflow, dependency manifest, data model, provider integration, security model, or operational documentation to reuse.

This is a statement about the inspected default-branch contents, not a claim that no external settings or unlisted GitHub features exist.

## 4. Product boundary

IWFI is an independent project. Its initial responsibility is evidence-based intelligence about institutional flows and large-holder activity for BTC and ETH. It must distinguish:
- observed facts;
- provider-derived classifications;
- calculated indicators;
- hypotheses;
- conclusions that remain undetermined.

The product is research and decision support, not an autonomous trading system. It must not place orders or make claims of certain future price direction.

## 5. Initial governance constraints

- Market evaluations run only when explicitly requested by the user.
- No scheduled market analysis or provider polling is enabled by this baseline.
- No provider is activated until its access method, terms, license, retention rights, rate limits, and costs have been reviewed.
- No causal attribution from temporal correlation alone.
- No invented wallet identities, institutional ownership, flow values, thresholds, probabilities, or missing observations.
- All event timestamps are stored in UTC with source timestamp and ingestion timestamp kept distinct.
- Raw source observations, normalized observations, derived metrics, and analyst conclusions remain distinguishable and traceable.
- Repository paths and filenames use English; GitHub Issues and PR descriptions use Spanish.
- Changes are proposed on branches and reviewed through pull requests; no direct implementation commits to `main`.

## 6. Unresolved audit items

1. Classic branch-protection configuration could not be read by the connected integration (HTTP 403). Recheck in GitHub settings with an authorized account.
2. Inherited organization policy was not independently verified.
3. No provider contracts, API credentials, subscriptions, or licenses were supplied for review.
4. Runtime, deployment target, user interface, database, and hosting budget have not been selected.
5. Data retention and archival policy require explicit requirements and provider-rights review.

## 7. Audit status

Repository-content baseline: **completed for the default branch**.

Full governance and provider due-diligence audit: **partially complete**, pending the items above.

No production capability is implemented or validated by this document.
