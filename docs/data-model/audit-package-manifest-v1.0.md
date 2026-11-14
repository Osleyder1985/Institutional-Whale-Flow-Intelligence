# Offline Audit Package Inventory Manifest v1.0

## Purpose

This contract freezes an exact inventory of files intended for an audit/reconstruction package. It binds the inventory to the SHA-256 hash of the v1.2 reconstruction manifest and records each relative path, semantic role, media type, byte length and SHA-256 digest.

This module is an inventory builder/verifier, not a ZIP/TAR writer and not a storage service. The caller supplies exact bytes and controls packaging and transport.

## Safety and portability

Only safe relative POSIX paths are accepted. Absolute paths, traversal segments, backslashes, drive/alternate-stream syntax, control characters, trailing dot/space segments, Windows device names, duplicate paths and case-colliding paths are rejected. The verifier requires exact equality between the inventory and supplied artifact path set: omitted and unlisted files both fail.

## Offline verification

A verifier receives:
- the package inventory manifest;
- the exact path-to-bytes map;
- the independently expected reconstruction manifest hash.

It recomputes the inventory manifest hash, checks the reconstruction binding, exact path set, byte lengths and SHA-256 for every artifact. It does not extract archives, follow symlinks or access the filesystem.

## Rights and limitations

Only include bytes whose retention and redistribution are permitted by their source rights policy. A manifest does not grant rights to store or distribute evidence. If payloads cannot lawfully be included, produce a metadata-only audit package and label it as non-reconstructable; do not claim that missing evidence has been verified.

Hashes prove byte consistency, not provider authorship, factual truth, beneficial ownership, economic intent, or causality. This contract is not a signature, trusted timestamp, WORM store, archive writer or chain of custody by itself.

No network, capture, polling, backfill, credentials, paid services or external-cost dependencies. Synthetic fixtures only; external cost 0 USD.
