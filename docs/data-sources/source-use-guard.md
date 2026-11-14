# Source use guard

Status: fail-closed implementation for Issue #68. This contract does not grant data rights or activate a source.

Every restricted source must have a reviewed source-use policy conforming to schemas/source-use-policy.schema.json. The policy records exact terms, rights evidence, purpose, storage scope, retention approval, and inherited restrictions for derived artifacts.

## Allowed under the current Binance Vision scope

- DOWNLOAD, STORE_LOCAL, LOCAL_RESEARCH, and DERIVE_LOCAL, only when the policy is complete and explicitly approves a retention policy.
- Destination must be LOCAL_ONLY.

## Always blocked by the current policy

- EXPORT, SYNC, DISTRIBUTE, COMMERCIAL_USE, LIVE_TRADING, and PUBLIC_SERVICE.
- Any unknown operation, destination, missing rights evidence, unreviewed terms, or unapproved retention policy.

## Important limitations

The guard validates supplied policy metadata; it cannot independently establish that terms were interpreted correctly, that a legal entitlement exists, or that a retention policy is substantively compliant. A human must maintain truthful, current evidence. No policy fixture in tests is an approval to download Binance Vision data.

Source restrictions must propagate to normalized observations, derived features, model artifacts, reports, exports, caches, and backups. A transformed dataset is not presumed unrestricted.

The guard must run before any source access or destination write. It performs no network requests and stores no payloads.