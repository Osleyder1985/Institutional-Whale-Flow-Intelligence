"""Deterministic, offline reconstruction binding for IWFI attribution claims."""
import hashlib
import json
from datetime import datetime

from iwfi.evidence_snapshot_provenance import verify_snapshot_payload

_CANONICALIZATION = "IWFI-JSON-C14N-1"


def _parse_utc(value):
    if not isinstance(value, str) or len(value) != 20 or not value.endswith("Z"):
        raise ValueError("timestamp must use YYYY-MM-DDTHH:MM:SSZ")
    try:
        return datetime.strptime(value, "%Y-%m-%dT%H:%M:%SZ")
    except ValueError as exc:
        raise ValueError("invalid UTC timestamp") from exc


def _canonical_json_bytes(value):
    """IWFI-JSON-C14N-1: UTF-8, sorted object keys, compact separators, no NaN."""
    return json.dumps(
        value, sort_keys=True, separators=(",", ":"),
        ensure_ascii=False, allow_nan=False,
    ).encode("utf-8")


def _sha256(payload):
    return hashlib.sha256(payload).hexdigest()


def _collect_observation_ids(value):
    found = set()

    def visit(node):
        if isinstance(node, dict):
            for key, child in node.items():
                if key in {"observation_id"} and isinstance(child, str) and child.strip():
                    found.add(child)
                elif key in {"observation_ids", "source_observation_ids"} and isinstance(child, list):
                    found.update(item for item in child if isinstance(item, str) and item.strip())
                visit(child)
        elif isinstance(node, list):
            for child in node:
                visit(child)

    visit(value)
    return found


def build_attribution_reconstruction_manifest(
    *, claim, snapshot_descriptors, observation_snapshot_map,
    knowledge_cutoff_utc, valid_time_utc, algorithm_id,
    algorithm_version, parameters,
):
    """Freeze a claim and every snapshot supporting its referenced observations."""
    if not isinstance(claim, dict):
        raise ValueError("claim must be an object")
    claim_id = claim.get("claim_id")
    claim_version = claim.get("contract_version")
    claim_recorded = claim.get("recorded_at_utc")
    if not isinstance(claim_id, str) or not claim_id.strip():
        raise ValueError("claim_id is required")
    if not isinstance(claim_version, str) or not claim_version.strip():
        raise ValueError("claim contract_version is required")
    claim_time = _parse_utc(claim_recorded)
    cutoff = _parse_utc(knowledge_cutoff_utc)
    valid_time = _parse_utc(valid_time_utc)
    if claim_time > cutoff:
        raise ValueError("claim was recorded after the knowledge cutoff")
    valid_from = claim.get("valid_from_utc")
    valid_to = claim.get("valid_to_utc")
    if valid_from is not None and valid_time < _parse_utc(valid_from):
        raise ValueError("requested valid time precedes the claim validity interval")
    if valid_to is not None and valid_time > _parse_utc(valid_to):
        raise ValueError("requested valid time follows the claim validity interval")
    if not isinstance(algorithm_id, str) or not algorithm_id.strip():
        raise ValueError("algorithm_id is required")
    if not isinstance(algorithm_version, str) or not algorithm_version.strip():
        raise ValueError("algorithm_version is required")
    if not isinstance(parameters, dict):
        raise ValueError("parameters must be an object")
    if not isinstance(observation_snapshot_map, dict):
        raise ValueError("observation_snapshot_map must be an object")

    descriptors = {}
    for descriptor in snapshot_descriptors:
        if not isinstance(descriptor, dict):
            raise ValueError("snapshot descriptor must be an object")
        sid = descriptor.get("source_snapshot_id")
        if not isinstance(sid, str) or not sid.strip() or sid in descriptors:
            raise ValueError("snapshot IDs must be present and unique")
        retrieved = _parse_utc(descriptor.get("retrieved_at_utc"))
        if retrieved > cutoff:
            raise ValueError("snapshot was retrieved after the knowledge cutoff")
        descriptors[sid] = descriptor

    observation_ids = _collect_observation_ids(claim)
    snapshot_observations = {sid: set() for sid in descriptors}
    for observation_id in observation_ids:
        snapshot_ids = observation_snapshot_map.get(observation_id)
        if isinstance(snapshot_ids, str):
            snapshot_ids = [snapshot_ids]
        if not isinstance(snapshot_ids, list) or not snapshot_ids:
            raise ValueError("claim observation has no snapshot mapping: " + observation_id)
        for sid in snapshot_ids:
            if sid not in descriptors:
                raise ValueError("observation maps to an unknown snapshot: " + str(sid))
            snapshot_observations[sid].add(observation_id)

    dependencies = []
    for sid, descriptor in descriptors.items():
        if snapshot_observations[sid]:
            dependencies.append({
                "source_id": descriptor.get("source_id"),
                "source_snapshot_id": sid,
                "retrieved_at_utc": descriptor.get("retrieved_at_utc"),
                "payload_hash": descriptor.get("payload_hash"),
                "hash_algorithm": descriptor.get("hash_algorithm"),
                "hash_scope": descriptor.get("hash_scope"),
                "canonicalization_version": descriptor.get("canonicalization_version"),
                "observation_ids": sorted(snapshot_observations[sid]),
            })
    dependencies.sort(key=lambda item: (item["source_id"] or "", item["source_snapshot_id"]))
    if observation_ids and not dependencies:
        raise ValueError("no evidence snapshot dependencies resolved")

    manifest = {
        "manifest_version": "1.0.0",
        "claim_id": claim_id,
        "claim_contract_version": claim_version,
        "claim_hash": _sha256(_canonical_json_bytes(claim)),
        "claim_hash_algorithm": "SHA-256",
        "claim_canonicalization_version": _CANONICALIZATION,
        "claim_recorded_at_utc": claim_recorded,
        "knowledge_cutoff_utc": knowledge_cutoff_utc,
        "valid_time_utc": valid_time_utc,
        "algorithm_id": algorithm_id,
        "algorithm_version": algorithm_version,
        "parameters": parameters,
        "dependencies": dependencies,
        "manifest_hash_algorithm": "SHA-256",
        "manifest_canonicalization_version": _CANONICALIZATION,
    }
    manifest["manifest_hash"] = _sha256(_canonical_json_bytes(manifest))
    return manifest


def verify_attribution_reconstruction(
    *, manifest, claim, snapshots_by_id, payloads_by_id,
):
    """Verify a frozen claim and all exact dependencies without network access."""
    if not all(isinstance(item, dict) for item in (manifest, claim, snapshots_by_id, payloads_by_id)):
        return {"status": "INVALID_INPUT", "dependencies": []}
    unsigned = {key: value for key, value in manifest.items() if key != "manifest_hash"}
    try:
        expected_manifest_hash = _sha256(_canonical_json_bytes(unsigned))
        actual_claim_hash = _sha256(_canonical_json_bytes(claim))
    except (TypeError, ValueError):
        return {"status": "INTEGRITY_FAILED", "manifest_status": "NON_CANONICAL_INPUT", "dependencies": []}
    if manifest.get("manifest_canonicalization_version") != _CANONICALIZATION:
        return {"status": "INTEGRITY_FAILED", "manifest_status": "UNSUPPORTED_CANONICALIZATION", "dependencies": []}
    if manifest.get("manifest_hash") != expected_manifest_hash:
        return {"status": "INTEGRITY_FAILED", "manifest_status": "MANIFEST_HASH_MISMATCH", "dependencies": []}
    if manifest.get("claim_canonicalization_version") != _CANONICALIZATION:
        return {"status": "INTEGRITY_FAILED", "manifest_status": "UNSUPPORTED_CLAIM_CANONICALIZATION", "dependencies": []}
    if (
        manifest.get("claim_hash") != actual_claim_hash
        or manifest.get("claim_id") != claim.get("claim_id")
        or manifest.get("claim_contract_version") != claim.get("contract_version")
        or manifest.get("claim_recorded_at_utc") != claim.get("recorded_at_utc")
    ):
        return {"status": "INTEGRITY_FAILED", "manifest_status": "CLAIM_HASH_MISMATCH", "dependencies": []}
    try:
        cutoff = _parse_utc(manifest["knowledge_cutoff_utc"])
        claim_time = _parse_utc(claim.get("recorded_at_utc"))
        valid_time = _parse_utc(manifest["valid_time_utc"])
        if claim_time > cutoff:
            raise ValueError("claim after cutoff")
        valid_from = claim.get("valid_from_utc")
        valid_to = claim.get("valid_to_utc")
        if valid_from is not None and valid_time < _parse_utc(valid_from):
            raise ValueError("valid time before claim interval")
        if valid_to is not None and valid_time > _parse_utc(valid_to):
            raise ValueError("valid time after claim interval")
    except (KeyError, ValueError):
        return {"status": "INTEGRITY_FAILED", "manifest_status": "INVALID_TEMPORAL_SCOPE", "dependencies": []}

    results = []
    for dependency in manifest.get("dependencies", []):
        sid = dependency.get("source_snapshot_id") if isinstance(dependency, dict) else None
        snapshot = snapshots_by_id.get(sid)
        payload = payloads_by_id.get(sid)
        if snapshot is None:
            status = "SNAPSHOT_MISSING"
        elif payload is None:
            status = "PAYLOAD_UNAVAILABLE"
        elif any(snapshot.get(field) != dependency.get(field) for field in (
            "source_id", "source_snapshot_id", "retrieved_at_utc", "payload_hash",
            "hash_algorithm", "hash_scope", "canonicalization_version",
        )):
            status = "SNAPSHOT_REFERENCE_MISMATCH"
        else:
            try:
                retrieved = _parse_utc(snapshot.get("retrieved_at_utc"))
                status = "SNAPSHOT_AFTER_CUTOFF" if retrieved > cutoff else verify_snapshot_payload(snapshot, payload)["status"]
            except ValueError:
                status = "INVALID_SNAPSHOT_TIMESTAMP"
        results.append({"source_snapshot_id": sid, "status": status})
    failed = any(item["status"] != "HASH_VERIFIED" for item in results)
    return {
        "status": "INTEGRITY_FAILED" if failed else "RECONSTRUCTION_INPUTS_VERIFIED",
        "manifest_status": "HASH_VERIFIED",
        "claim_status": "HASH_VERIFIED",
        "dependencies": results,
    }
