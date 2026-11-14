"""Offline integrity primitives for immutable evidence snapshots (IWFI v1.0).

This module never fetches sources or writes storage. Callers provide exact bytes
read from an authorized local artifact and an explicit retention decision.
"""
from datetime import datetime
import copy
import hashlib
import json
from types import MappingProxyType
import re

_UTC = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z$")
_HASH = re.compile(r"^[a-f0-9]{64}$")
_RETENTION = {"RETAINED", "NOT_RETAINED_POLICY", "NOT_RETAINED_UNAVAILABLE"}
_HASH_STATUS = {"AVAILABLE", "NOT_PERMITTED", "NOT_COMPUTED"}
_HASH_SCOPE = {"RAW_BYTES", "CANONICAL_JSON"}
_RELATIONS = {"SUPERSEDES", "CORRECTS", "CONTRADICTS", "RETRACTS", "REVOKES_ACCESS"}


def _valid_utc(value):
    if not isinstance(value, str) or not _UTC.fullmatch(value):
        return False
    try:
        datetime.strptime(value, "%Y-%m-%dT%H:%M:%SZ")
        return True
    except ValueError:
        return False


def _sha256(payload):
    return hashlib.sha256(payload).hexdigest()


def build_snapshot_descriptor(*, source_id, source_snapshot_id, retrieved_at_utc,
                               media_type, rights_policy_ref, retention_decision,
                               payload=None, hash_permitted=False, published_at_utc=None,
                               source_version=None, etag=None, last_modified=None,
                               hash_scope="RAW_BYTES", canonicalization_version=None,
                               storage_ref=None, recorded_at_utc=None):
    """Build metadata for one retrieval; payload bytes are never persisted here."""
    if not all(isinstance(x, str) and x.strip() for x in
               (source_id, source_snapshot_id, media_type, rights_policy_ref)):
        raise ValueError("required identifiers and policy reference must be non-empty")
    if not _valid_utc(retrieved_at_utc) or (published_at_utc is not None and not _valid_utc(published_at_utc)):
        raise ValueError("invalid UTC timestamp")
    recorded = recorded_at_utc or retrieved_at_utc
    if not _valid_utc(recorded) or recorded < retrieved_at_utc:
        raise ValueError("invalid recorded_at_utc")
    if retention_decision not in _RETENTION:
        raise ValueError("invalid retention decision")
    if hash_scope not in _HASH_SCOPE:
        raise ValueError("invalid hash scope")
    if hash_scope == "CANONICAL_JSON" and not canonicalization_version:
        raise ValueError("canonical JSON hashing requires an explicit canonicalization version")
    if hash_scope == "RAW_BYTES" and canonicalization_version is not None:
        raise ValueError("raw-byte hashing must not claim a canonicalization version")
    if retention_decision == "RETAINED" and (payload is None or not storage_ref):
        raise ValueError("retained payload requires exact bytes and a storage reference")
    if retention_decision != "RETAINED" and storage_ref is not None:
        raise ValueError("non-retained payload must not have a storage reference")
    if payload is not None and not isinstance(payload, bytes):
        raise TypeError("payload must be bytes")
    if payload is None:
        hash_status, payload_hash, payload_size = "NOT_COMPUTED", None, None
    elif hash_permitted:
        hash_status, payload_hash, payload_size = "AVAILABLE", _sha256(payload), len(payload)
    else:
        hash_status, payload_hash, payload_size = "NOT_PERMITTED", None, None
    if retention_decision == "RETAINED" and hash_status != "AVAILABLE":
        raise ValueError("retained payload requires an authorized integrity hash")
    return {
        "contract_version": "1.0.0", "source_id": source_id,
        "source_snapshot_id": source_snapshot_id, "retrieved_at_utc": retrieved_at_utc,
        "published_at_utc": published_at_utc, "source_version": source_version,
        "etag": etag, "last_modified": last_modified, "media_type": media_type,
        "payload_retention": retention_decision, "hash_status": hash_status,
        "hash_scope": hash_scope, "payload_hash": payload_hash,
        "hash_algorithm": "SHA-256", "payload_size_bytes": payload_size,
        "canonicalization_version": canonicalization_version, "storage_ref": storage_ref,
        "rights_policy_ref": rights_policy_ref, "recorded_at_utc": recorded,
    }


def verify_snapshot_payload(snapshot, payload):
    """Verify exact bytes against a descriptor; never fetches or canonicalizes."""
    if not isinstance(snapshot, dict) or not isinstance(payload, bytes):
        return {"status": "INVALID_INPUT"}
    if snapshot.get("hash_status") != "AVAILABLE" or snapshot.get("hash_algorithm") != "SHA-256":
        return {"status": "HASH_UNAVAILABLE"}
    expected = snapshot.get("payload_hash")
    if not isinstance(expected, str) or not _HASH.fullmatch(expected):
        return {"status": "INVALID_EXPECTED_HASH"}
    actual = _sha256(payload)
    if snapshot.get("payload_size_bytes") != len(payload):
        return {"status": "SIZE_MISMATCH", "expected_hash": expected, "actual_hash": actual}
    if actual != expected:
        return {"status": "HASH_MISMATCH", "expected_hash": expected, "actual_hash": actual}
    return {"status": "HASH_VERIFIED", "payload_hash": actual, "payload_size_bytes": len(payload)}


def build_snapshot_relation(*, relation_id, from_snapshot_id, to_snapshot_id,
                            relation_type, recorded_at_utc, rights_policy_ref):
    if not all(isinstance(x, str) and x.strip() for x in
               (relation_id, from_snapshot_id, to_snapshot_id, rights_policy_ref)):
        raise ValueError("relation identifiers and policy reference are required")
    if from_snapshot_id == to_snapshot_id or relation_type not in _RELATIONS:
        raise ValueError("invalid snapshot relation")
    if not _valid_utc(recorded_at_utc):
        raise ValueError("invalid recorded_at_utc")
    return {"relation_id": relation_id, "from_snapshot_id": from_snapshot_id,
            "to_snapshot_id": to_snapshot_id, "relation_type": relation_type,
            "recorded_at_utc": recorded_at_utc, "rights_policy_ref": rights_policy_ref}


def build_reconstruction_manifest(*, claim_id, snapshot_descriptors,
                                   contract_versions, algorithm_id, algorithm_version,
                                   parameters, knowledge_cutoff_utc, valid_time_utc):
    if not claim_id or not algorithm_id or not algorithm_version:
        raise ValueError("claim and algorithm identifiers are required")
    if not _valid_utc(knowledge_cutoff_utc) or not _valid_utc(valid_time_utc):
        raise ValueError("invalid manifest timestamps")
    dependencies, seen = [], set()
    for item in snapshot_descriptors:
        if not isinstance(item, dict):
            raise ValueError("invalid snapshot descriptor")
        sid = item.get("source_snapshot_id")
        if not sid or sid in seen:
            raise ValueError("missing or duplicate snapshot dependency")
        seen.add(sid)
        dependencies.append({"source_id": item.get("source_id"), "source_snapshot_id": sid,
                             "payload_hash": item.get("payload_hash"),
                             "hash_algorithm": item.get("hash_algorithm"),
                             "hash_scope": item.get("hash_scope"),
                             "canonicalization_version": item.get("canonicalization_version")})
    dependencies.sort(key=lambda x: (x["source_id"] or "", x["source_snapshot_id"]))
    manifest = {"manifest_version": "1.0.0", "claim_id": claim_id,
                "contract_versions": dict(sorted(contract_versions.items())),
                "algorithm_id": algorithm_id, "algorithm_version": algorithm_version,
                "parameters": parameters, "knowledge_cutoff_utc": knowledge_cutoff_utc,
                "valid_time_utc": valid_time_utc, "dependencies": dependencies}
    encoded = json.dumps(manifest, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
    manifest["manifest_hash"] = _sha256(encoded)
    return manifest


def verify_manifest_dependencies(manifest, snapshots_by_id, payloads_by_id):
    """Offline-only dependency check. Missing artifacts never imply non-existence."""
    if not isinstance(manifest, dict) or not isinstance(snapshots_by_id, dict) or not isinstance(payloads_by_id, dict):
        return {"status": "INVALID_INPUT", "dependencies": []}
    dependencies = manifest.get("dependencies")
    if not isinstance(dependencies, list):
        return {"status": "INVALID_INPUT", "dependencies": []}
    unsigned = {key: value for key, value in manifest.items() if key != "manifest_hash"}
    encoded = json.dumps(unsigned, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
    expected_manifest_hash = manifest.get("manifest_hash")
    if not isinstance(expected_manifest_hash, str) or _sha256(encoded) != expected_manifest_hash:
        return {"status": "INTEGRITY_FAILED", "dependencies": [],
                "manifest_status": "MANIFEST_HASH_MISMATCH"}
    results = []
    for dependency in dependencies:
        if not isinstance(dependency, dict):
            results.append({"source_snapshot_id": None, "status": "INVALID_DEPENDENCY"})
            continue
        sid = dependency.get("source_snapshot_id")
        snapshot, payload = snapshots_by_id.get(sid), payloads_by_id.get(sid)
        if snapshot is None:
            status = "SNAPSHOT_MISSING"
        elif payload is None:
            status = "PAYLOAD_UNAVAILABLE"
        elif any(snapshot.get(field) != dependency.get(field) for field in
                 ("source_id", "source_snapshot_id", "payload_hash", "hash_algorithm",
                  "hash_scope", "canonicalization_version")):
            status = "SNAPSHOT_REFERENCE_MISMATCH"
        else:
            status = verify_snapshot_payload(snapshot, payload)["status"]
        results.append({"source_snapshot_id": sid, "status": status})
    failed = any(item["status"] != "HASH_VERIFIED" for item in results)
    return {"status": "INTEGRITY_FAILED" if failed else "RECONSTRUCTION_INPUTS_VERIFIED",
            "manifest_status": "HASH_VERIFIED", "dependencies": results}


class AppendOnlySnapshotLedger:
    """Small in-memory reference model: append is allowed; replacement/deletion is not."""

    def __init__(self, snapshots=()):
        records = []
        seen = set()
        for snapshot in snapshots:
            self._validate_snapshot(snapshot)
            sid = snapshot["source_snapshot_id"]
            if sid in seen:
                raise ValueError("duplicate source_snapshot_id")
            seen.add(sid)
            records.append(MappingProxyType(copy.deepcopy(snapshot)))
        self._records = tuple(records)

    @staticmethod
    def _validate_snapshot(snapshot):
        if not isinstance(snapshot, dict):
            raise ValueError("snapshot must be an object")
        required = ("source_id", "source_snapshot_id", "retrieved_at_utc",
                    "payload_retention", "hash_status", "rights_policy_ref")
        if any(not snapshot.get(field) for field in required):
            raise ValueError("snapshot descriptor is incomplete")

    @property
    def snapshots(self):
        return self._records

    def append(self, snapshot):
        self._validate_snapshot(snapshot)
        sid = snapshot["source_snapshot_id"]
        if any(item["source_snapshot_id"] == sid for item in self._records):
            raise ValueError("snapshot identifiers are immutable and cannot be reused")
        self._records = self._records + (MappingProxyType(copy.deepcopy(snapshot)),)
        return self

    def get(self, source_snapshot_id):
        for snapshot in self._records:
            if snapshot["source_snapshot_id"] == source_snapshot_id:
                return snapshot
        return None
