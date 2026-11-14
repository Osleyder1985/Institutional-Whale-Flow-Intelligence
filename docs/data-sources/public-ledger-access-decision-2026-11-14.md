# Public Ledger Access Decision — BTC/ETH (2026-11-14)

## Purpose

Record the endpoint-level decision for zero-external-cash public ledger access. This is source diligence only. It does not authorize requests, sample capture, polling, backfill, or payload persistence. Issue #3 and Issue #71 remain the controlling gates.

## Decision summary

| Network | Candidate | What official evidence establishes | What remains unverified | Decision |
|---|---|---|---|---|
| Bitcoin | Blockstream Esplora public REST API | Official API reference documents transaction, status, block, address, UTXO and raw-block endpoints; amounts are satoshis. Blockstream describes public REST access as rate-limited for prototyping/light use and directs high-volume workloads to enterprise plans. | Numeric public quota, applicable hosted-service terms for the public endpoint, permitted retention, request logging, service continuity and a reproducible zero-cost allowance for IWFI. | CONDITIONAL_CANDIDATE; NOT_APPROVED |
| Ethereum | PublicNode public RPC | PublicNode's own terms explicitly allow automated scripts/indexers/agents for development and production without prior authorization; free public endpoint is advertised without API key. | Numeric per-method quotas, exact pricing/zero-charge commitment for the chosen workload, availability guarantee, and historical/archive access (archive requires API key). | CONDITIONALLY_ELIGIBLE_FOR_ONE_OFF_SAMPLE_AFTER_GATES; NOT_YET_APPROVED |
| Ethereum | Self-operated execution + consensus clients | Official Ethereum node guidance documents the two-client architecture and current hardware requirements. | Actual target-machine disk, bandwidth, I/O, sync duration and operating headroom. | TECHNICALLY_DOCUMENTED; LOCAL_FEASIBILITY_NOT_VERIFIED |

## Bitcoin — Blockstream Esplora

Official references:
- API schema: https://github.com/Blockstream/esplora/blob/master/API.md
- Hosted Explorer API product and current credit pricing: https://blockstream.com/blockchain-data-explorer-api
- Help article describing Explorer API account/plan checkout: https://blockstream.zendesk.com/hc/en-us/articles/52384240998169-Create-an-Explorer-API-account
- Official support/ecosystem explanation of Esplora and privacy: https://help.blockstream.com/education/development/how-bitcoin-evolves/bitcoins-open-source-ecosystem
- Blockstream general terms: https://blockstream.com/terms
- Blockstream privacy policy: https://blockstream.com/privacy/

The API reference establishes observable transaction and block fields, address history and UTXO queries. It does not publish a numeric rate limit or endpoint-specific retention/logging policy for the public instance. Blockstream's product page says the public REST endpoint at blockstream.info is rate-limited for prototyping and light use. The same page currently advertises a paid Basic tier of 500,000 API credits for USD 40, and higher tiers; the public REST route must not be confused with a recurring free allowance or the paid API-credit product. Its separate account guide describes subscription billing and recurring monthly charges for selected plans.

Blockstream's support article explains that third-party explorer operators can log queried addresses/transactions, while self-hosting keeps those queries local. This is a concrete privacy consideration for IWFI address intelligence. No public numeric quota, public-endpoint retention period, or public-endpoint SLA was found in the reviewed official materials.

**Operational rule:** do not implement unattended polling, recurring monitoring, bulk address scans, or backfill against the hosted public endpoint. Do not infer unlimited access from the endpoint being publicly reachable. A future one-off request still requires the exact terms and retention gates in Issues #3 and #71 to be closed.

Self-hosting Esplora is an alternative, but it moves the resource burden to the local machine and requires a Bitcoin data/indexing design. It is not assumed to be feasible without measuring disk, bandwidth and sync requirements.

## Ethereum — PublicNode

Official directory references:
- Ethereum developer tools: https://ethereum.org/developers/tools
- Ethereum network infrastructure providers: https://ethereum.org/developers/tools/categories/network-infrastructure/

The current PublicNode terms expressly permit automated access to listed RPC, WebSocket and gRPC endpoints, including scripts, bots, indexers and AI agents, for development and production without prior authorization. They also state that technical Usage Limits apply, may change without notice, and can result in HTTP 429. Higher limits, archive data and Yellowstone gRPC require an API key through Allnodes. The Ethereum endpoint page separately labels archive access as requiring an additional access step; therefore ordinary public RPC access must not be treated as archive access.

The terms permit returned blockchain data to be used in the user's own applications/services, but prohibit reselling endpoint access or the data as a standalone product without written consent. The service is revocable, may be changed/discontinued at discretion, and is supplied as-is without an uptime or accuracy warranty. This is not an SLA-backed production dependency.

The privacy policy states that, when PublicNode is used as an RPC provider, it will not store the user's IP address or data for more than 24 hours and says IP addresses are not linked/correlated to wallet addresses. This is a provider representation, not an independently audited guarantee. It gives IWFI a documented maximum retention statement to preserve with a dated policy snapshot, but it does not remove the need to assess the privacy implications of sending address/transaction queries to a third party.

**Operational rule:** PublicNode is the stronger candidate for a strictly bounded one-off Ethereum sample after Issues #3 and #71 close. Do not use archive methods, assume unlimited quotas, implement polling/backfill, or treat the service as guaranteed. Before any request, preserve dated copies/hashes of the terms and privacy policy, confirm that the exact selected RPC methods are included in the free public endpoint and incur zero external cash cost, and record the 24-hour provider retention statement. The project's own retention obligations remain separate.

## Ethereum — self-operated node feasibility

Official references:
- Node requirements and clients: https://ethereum.org/developers/docs/nodes-and-clients/run-a-node
- Archive node requirements: https://ethereum.org/developers/docs/nodes-and-clients/archive-nodes

The current official node guide lists a minimum of 2+ CPU cores, 16 GB RAM, 4 TB NVMe SSD and 25+ Mbit/s bandwidth for its full-node guidance. Recommended specifications are higher. Archive storage varies substantially by client and can be several terabytes to well above 10 TB.

The workstation's previously reported 16 GB RAM only matches the stated minimum RAM figure. That does not establish feasibility: available free NVMe capacity, disk I/O, bandwidth, sync time and resource headroom have not been measured in the target environment. Do not begin synchronization or install a node based on RAM alone.

## Comparative assessment and next gate

| Criterion | Blockstream Esplora public REST | PublicNode Ethereum public RPC |
|---|---|---|
| Automated access explicitly documented | Public product page describes light/prototype access; no numeric quota | Yes; terms expressly permit scripts/indexers/agents for development and production |
| Public access cost evidence | Public endpoint described as rate-limited; paid product lists 500k credits for USD 40; no public numeric free allowance | Public endpoint advertised as free/no API key; terms do not publish a numeric quota or a guaranteed free-service commitment |
| Usage limits | Rate-limited; numeric ceiling not published | Dynamic limits; HTTP 429 possible; higher limits require API key |
| Archive/history | Esplora API exposes address history pagination; do not infer unlimited scans | Archive data requires API key; no archive assumption for public endpoint |
| Provider retention/privacy | Public help warns third-party explorer operators can log queries; no specific retention period found | Policy states IP and data not stored over 24 hours; IP not linked to wallet addresses |
| Reliability/contract | No public endpoint SLA identified | Terms provide no uptime/accuracy warranty and allow modification/discontinuation |
| Current decision | CONDITIONAL; no batch capture/polling | Better candidate for one-off bounded sample, only after all gates |

**Next technical gate:** request only a small, explicitly bounded set of recent/known Ethereum block and transaction observations through PublicNode's ordinary public RPC, but only after the source-policy snapshot and local storage/retention gates in Issues #3 and #71 are closed. For Bitcoin, continue to treat the public Esplora route as prototype/light-use only; a reproducible zero-cost allowance and endpoint retention terms remain insufficiently documented. Do not use this document as authorization to call either endpoint.

## Ethereum — bounded one-off sample protocol (design only)

Official JSON-RPC method semantics: https://ethereum.org/developers/docs/apis/json-rpc/

After Issues #3 and #71 are closed and the exact free-use scope is confirmed, the first Ethereum sample should use only the ordinary public RPC endpoint `https://ethereum-rpc.publicnode.com` and the following bounded sequence:

1. `eth_chainId` — require `0x1`; otherwise stop with `WRONG_NETWORK`.
2. `eth_getBlockByNumber(["finalized", false])` — request only a finalized block header and transaction hashes, not full transaction objects. If the method/tag is unsupported or the result is null, stop; do not silently fall back to `latest`, scan older blocks, or request archive access.
3. If the returned block contains no transaction hashes, stop with `EMPTY_SAMPLE`; do not advance to another block automatically.
4. Select exactly the first transaction hash in the returned block in the provider's returned order. Call `eth_getTransactionByHash([tx_hash])`.
5. Call `eth_getTransactionReceipt([tx_hash])`.

This is a maximum of four JSON-RPC requests for a non-empty sample (chain ID, finalized block, transaction, receipt); an empty block or failed prerequisite stops earlier. No retries, polling, address-history scans, `eth_getLogs`, trace/debug methods, archive methods, or fallback providers are included.

Validation requirements:
- Every JSON-RPC response must have `jsonrpc="2.0"`, the matching request ID, and exactly one of `result` or `error`; malformed/error responses stop the sample.
- Chain ID must be Ethereum mainnet (`0x1`).
- Block number/hash and transaction list must be present and well-formed.
- Transaction hash, block hash and block number must match the selected block and receipt. A null transaction/receipt or mismatch yields `INCOMPLETE_OR_CONFLICTED`; it is not repaired by searching another block.
- Preserve integer quantities exactly. Convert wei only with exact integer arithmetic; do not use floating point.
- Count a top-level native-value movement only when the receipt reports `status=0x1`, the transaction has a valid non-null `to` address, and `value` is greater than zero. A reverted transaction (`status=0x0`) contributes no successful movement. Contract-creation transactions (`to=null`) remain transaction observations but are not normalized as address-to-address movements in this first sample.
- The sample covers only top-level transaction `value`. It does not observe internal contract-call value transfers, ERC-20 transfers, token balances, or beneficial ownership. Do not infer those from logs or top-level calldata.
- A finalized-tag response is provider-reported execution-layer evidence; it is not an independent consensus proof. Record provider, endpoint, retrieval time, block number/hash, transaction hash, receipt status, and response hashes. If an independent source is unavailable, retain that limitation.
- This sample plan does not authorize storage of raw responses. Retention classification remains subject to Issue #71 and source-specific terms. Do not place payloads in Git or another cloud service as a workaround.

No RPC call has been made under this design. It is a future execution protocol, not capture authorization.

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

PublicNode is now a documented conditional candidate for a bounded one-off Ethereum sample because its terms expressly permit automated reads and its privacy policy states a 24-hour maximum retention period for RPC IP/data. It is not yet APPROVED: dynamic quotas, service continuity, exact free-use scope and archive limitations remain. Blockstream Esplora remains conditional for prototype/light use; its public quota and endpoint retention remain unspecified, while paid API credits are priced separately. No endpoint is authorized by this review. No network request, capture, polling, backfill, or data persistence was performed or authorized by this change.

Related: Issue #3, Issue #45, Issue #71.
