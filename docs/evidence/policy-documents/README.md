# Policy document evidence

This directory keeps the source documents used by the IWFI policy and provenance review.

## Source documents

| Document | Repository copy | Official source | Version/date |
|---|---|---|---|
| Binance Vision Dataset Terms | [Original source text](originals/binance_vision_dataset_terms_v1.md) | [Binance public-data repository](https://github.com/binance/binance-public-data/blob/master/TERMS_AND_CONDITIONS.md) | v1.0, updated 2026-08-26 |
| CC BY-NC-SA 4.0 legal code | [Official legal code text](originals/cc_by_nc_sa_4_0_legalcode.txt) | [Creative Commons legal code](https://creativecommons.org/licenses/by-nc-sa/4.0/legalcode.txt) | 4.0 International |
| Binance ADGM Terms of Use | Source reference and SHA-256 in [source register](source-register-v1.0.json) | [Official PDF](https://bin.bnbstatic.com/static/cms/cg08ou2ak0tn7mcplvfg/file/9958035d95bff024a86a662fb4fdba45527d55a936e2cb9ed1d7ddf205ca082d.pdf) | Effective 2026-01-05 |

The first two source texts are stored in this repository. The ADGM Terms PDF is a binary original. Its original 757,137-byte snapshot and SHA-256 were verified locally, but the GitHub text-file operation used for this change cannot transfer binary bytes. We therefore preserve its official URL, original filename, page count, and verified digest instead of creating a fake or incomplete PDF file.

## Evidence rules

- Source text is preserved as received; any IWFI analysis belongs in a separate review artifact.
- Never silently replace a captured version. Add a new versioned snapshot and update the source register.
- Preserve official source URL, observed version/date, retrieval time when available, and SHA-256 of the captured bytes.
- Distinguish the document's public availability from the scope of rights it grants.
- Do not treat Binance Vision dataset terms as proof that other Binance endpoints or third-party data have the same terms.
- No document in this directory grants IWFI a legal authorization by itself. Authorization, legal applicability, retention permission, and source approval remain separately assessed states.
