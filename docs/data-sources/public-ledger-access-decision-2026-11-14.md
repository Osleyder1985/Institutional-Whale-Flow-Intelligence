# Public Ledger Access Decision — BTC/ETH (2026-11-14)

## Purpose

Record the endpoint-level decision for zero-external-cash public ledger access. This is source diligence only. It does not authorize requests, sample capture, polling, backfill, or payload persistence. Issue #3 and Issue #71 remain the controlling gates.

## Decision summary

| Network | Candidate | What official evidence establishes | What remains unverified | Decision |
|---|---|---|---|---|
| Bitcoin | Blockstream Esplora public REST API | Official API reference documents transaction, status, block, address, UTXO and raw-block endpoints; amounts are satoshis. Blockstream describes public REST access as rate-limited for prototyping/light use and directs high-volume workloads to enterprise plans. | Numeric public quota, applicable hosted-service terms for the public endpoint, permitted retention, request logging, service continuity and a reproducible zero-cost allowance for IWFI. | CONDITIONAL_CANDIDATE; NOT_APPROVED |
| Ethereum | PublicNode public RPC | ethereum.org lists PublicNode as offering free Ethereum RPC endpoints without an API key. | PublicNode endpoint-specific terms, request limits, supported historical methods, retention/logging, service availability, and whether the endpoint can serve the exact native-ETH/block data required. | CONDITIONAL_CANDIDATE; NOT_APPROVED |
| Ethereum | Self-operated execution + consensus clients | Official Ethereum node guidance documents the two-client architecture and current hardware requirements. | Actual target-machine disk, bandwidth, I/O, sync duration and operating headroom. | TECHNICALLY_DOCUMENTED; LOCAL_FEASIBILITY_NOT_VERIFIED |

## Bitcoin — Blockstream Esplora

Official references:
- API schema: https://github.com/Blockstream/esplora/blob/master/API.md
- Hosted Explorer API product: https://blockstream.com/blockchain-data-explorer-api
- Help article describing Explorer API account/plan checkout: https://blockstream.zendesk.com/hc/en-us/articles/52384240998169-Create-an-Explorer-API-account
- Official support/ecosystem explanation of Esplora and privacy: https://help.blockstream.com/education/development/how-bitcoin-evolves/bitcoins-open-source-ecosystem

The API reference establishes observable transaction and block fields, address history and UTXO queries. It does not publish a numeric rate limit or a complete public-instance retention/acceptable-use policy. Blockstream's product page describes public REST access at blockstream.info as rate-limited for prototyping and light use, with enterprise plans for high-volume applications. The account/plan help article describes paid subscription checkout for the Explorer API product; it must not be conflated with a published free recurring entitlement for arbitrary hosted usage.

An older public GitHub issue documents HTTP 429 reports, but community reports are not a contractual quota and must not be converted into a numeric limit.

**Operational rule:** do not implement unattended polling, recurring monitoring, bulk address scans, or backfill against the hosted public endpoint. Do not infer unlimited access from the endpoint being publicly reachable. A future one-off request still requires the exact terms and retention gates in Issues #3 and #71 to be closed.

Self-hosting Esplora is an alternative, but it moves the resource burden to the local machine and requires a Bitcoin data/indexing design. It is not assumed to be feasible without measuring disk, bandwidth and sync requirements.

## Ethereum — PublicNode

Official directory references:
- Ethereum developer tools: https://ethereum.org/developers/tools
- Ethereum network infrastructure providers: https://ethereum.org/developers/tools/categories/network-infrastructure/

ethereum.org lists PublicNode as providing free Ethereum RPC endpoints without an API key. This is evidence of a publicly advertised free access route, not a complete endpoint contract. The directory does not establish the exact quotas, retention/logging policy, SLA, historical-state availability, or the right to retain returned payloads for this project's lifecycle.

**Operational rule:** PublicNode remains a candidate only. No adapter may assume an unlimited quota, archive access, stable availability, or zero retention by the provider. Before a sample, preserve the provider's current terms/privacy policy and endpoint documentation; verify the exact methods required for native ETH observations and confirm that the recurring use remains zero external cash cost.

## Ethereum — self-operated node feasibility

Official references:
- Node requirements and clients: https://ethereum.org/developers/docs/nodes-and-clients/run-a-node
- Archive node requirements: https://ethereum.org/developers/docs/nodes-and-clients/archive-nodes

The current official node guide lists a minimum of 2+ CPU cores, 16 GB RAM, 4 TB NVMe SSD and 25+ Mbit/s bandwidth for its full-node guidance. Recommended specifications are higher. Archive storage varies substantially by client and can be several terabytes to well above 10 TB.

The workstation's previously reported 16 GB RAM only matches the stated minimum RAM figure. That does not establish feasibility: available free NVMe capacity, disk I/O, bandwidth, sync time and resource headroom have not been measured in the target environment. Do not begin synchronization or install a node based on RAM alone.

## Source selection consequences

1. A free endpoint is not automatically an approved source. Cost, terms, request limits, retention and data semantics are independent gates.
2. Public-chain data proves on-chain facts, not the beneficial owner, institutional status, or economic purpose of an address.
3. A transaction transfer is not an exchange execution or a buy/sell trade.
4. A hosted explorer/RPC response is a third-party observation. Preserve provider identity, endpoint, retrieval time, response hash, block hash/height and validation status if a later authorized sample is taken.
5. Reorg handling must be explicit: a transaction's initial inclusion is not a permanent finality assertion. Preserve block hash and confirmation/finality evidence; do not overwrite an earlier observation silently.
6. BTC UTXO observations and Ethereum account/state observations require separate source adapters and normalization rules. Do not force both networks into a shared raw transaction schema that discards chain-specific semantics.

## Required gates before any real sample

- [ ] Issue #3: endpoint-specific terms and zero-cost access evidence reviewed and preserved.
- [ ] Issue #71: source policy snapshot/hash and applicability review completed.
- [ ] Issue #71: target local path, sync risk and actual capacity verified; no assumed values.
- [ ] Issue #71: dependency/backup scope and controlled deletion evidence completed.
- [ ] Endpoint-specific retention and logging policy reviewed.
- [ ] One small sample per network explicitly scoped; no polling, monitoring or backfill.
- [ ] Sample method independently cross-checked where feasible; all missing or disputed fields remain explicit.

## Current conclusion

No public-ledger endpoint is promoted to APPROVED by this review. Blockstream Esplora and PublicNode are conditional candidates only. The local Ethereum node route remains unverified for the target machine. No network request, capture, polling, backfill, or data persistence was performed or authorized by this change.

Related: Issue #3, Issue #45, Issue #71.
