"""Root-claim snapshot binding for full offline Actor Registry reconstruction v1.2."""
import hashlib
import json
from datetime import datetime

from iwfi.actor_registry_reconstruction_v1_1 import (
    build_actor_registry_reconstruction_manifest_v1_1,
    verify_actor_registry_reconstruction_manifest_v1_1,
)
from iwfi.evidence_snapshot_provenance import verify_snapshot_payload

_CANON = "IWFI-JSON-C14N-1"


def _canonical(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"),
                      ensure_ascii=False, allow_nan=False).encode("utf-8")


def _sha(data):
    return hashlib.sha256(data).hexdigest()


def _time(value):
    if not isinstance(value, str) or len(value) != 20 or not value.endswith("Z"):
        raise ValueError("UTC timestamp must use YYYY-MM-DDTHH:MM:SSZ")
    return datetime.strptime(value, "%Y-%m-%dT%H:%M:%SZ")


def build_actor_registry_reconstruction_manifest_v1_2(
    *, root_claim, root_claim_snapshot_descriptor, root_claim_payload,
    actor_registry, snapshot_descriptors, reference_snapshot_map,
    knowledge_cutoff_utc, valid_time_utc, algorithm_id, algorithm_version,
    parameters,
):
    """Freeze v1.1 registry evidence plus exact bytes and descriptor of root claim."""
    if not isinstance(root_claim, dict) or not isinstance(root_claim_payload, bytes):
        raise ValueError("root claim object and exact snapshot bytes are required")
    if not isinstance(root_claim_snapshot_descriptor, dict):
        raise ValueError("root claim snapshot descriptor is required")
    try:
        decoded = json.loads(root_claim_payload.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ValueError("root claim snapshot must contain UTF-8 JSON") from exc
    if not isinstance(decoded, dict) or decoded != root_claim:
        raise ValueError("root claim payload must decode to the supplied root claim")
    root_id = root_claim.get("claim_id")
    root_version = root_claim.get("contract_version")
    if not isinstance(root_id, str) or not root_id.strip():
        raise ValueError("root claim claim_id is required")
    if not isinstance(root_version, str) or not root_version.strip():
        raise ValueError("root claim contract_version is required")
    descriptor = root_claim_snapshot_descriptor
    if descriptor.get("media_type") != "application/json":
        raise ValueError("root claim snapshot must use application/json")
    if descriptor.get("payload_retention") != "RETAINED":
        raise ValueError("root claim snapshot bytes must be retained for reconstruction")
    if not isinstance(descriptor.get("source_snapshot_id"), str) or not descriptor["source_snapshot_id"].strip():
        raise ValueError("root claim snapshot ID is required")
    if _time(descriptor.get("retrieved_at_utc")) > _time(knowledge_cutoff_utc):
        raise ValueError("root claim snapshot retrieved after knowledge cutoff")
    integrity = verify_snapshot_payload(descriptor, root_claim_payload)
    if integrity.get("status") != "HASH_VERIFIED":
        raise ValueError("root claim snapshot payload hash is not verified")
    root_hash = _sha(_canonical(root_claim))
    base = build_actor_registry_reconstruction_manifest_v1_1(
        actor_registry=actor_registry, snapshot_descriptors=snapshot_descriptors,
        reference_snapshot_map=reference_snapshot_map,
        knowledge_cutoff_utc=knowledge_cutoff_utc, valid_time_utc=valid_time_utc,
        algorithm_id=algorithm_id, algorithm_version=algorithm_version,
        parameters=parameters, root_claim_id=root_id, root_claim_hash=root_hash,
        root_claim_contract_version=root_version,
    )
    base["manifest_version"] = "1.2.0"
    base["root_claim_snapshot"] = {
        "source_id": descriptor.get("source_id"),
        "source_snapshot_id": descriptor.get("source_snapshot_id"),
        "retrieved_at_utc": descriptor.get("retrieved_at_utc"),
        "payload_hash": descriptor.get("payload_hash"),
        "hash_algorithm": descriptor.get("hash_algorithm"),
        "hash_scope": descriptor.get("hash_scope"),
        "canonicalization_version": descriptor.get("canonicalization_version"),
        "media_type": descriptor.get("media_type"),
        "payload_retention": descriptor.get("payload_retention"),
    }
    base["manifest_hash"] = _sha(_canonical({k: v for k, v in base.items() if k != "manifest_hash"}))
    return base


def verify_actor_registry_reconstruction_manifest_v1_2(
    *, manifest, root_claim_snapshot_descriptor, root_claim_payload,
    actor_registry, snapshots_by_id, payloads_by_id,
    knowledge_cutoff_utc, valid_time_utc,
):
    """Verify root claim exact snapshot before delegating to the v1.1 evidence verifier."""
    def fail(reason):
        return {"status": "INTEGRITY_FAILED", "reason": reason}
    if not isinstance(manifest, dict) or manifest.get("manifest_version") != "1.2.0":
        return {"status": "INVALID_INPUT", "reason": "V1_2_MANIFEST_REQUIRED"}
    unsigned = {k: v for k, v in manifest.items() if k != "manifest_hash"}
    try:
        if manifest.get("manifest_canonicalization_version") != _CANON:
            return fail("UNSUPPORTED_CANONICALIZATION")
        if manifest.get("manifest_hash") != _sha(_canonical(unsigned)):
            return fail("MANIFEST_HASH_MISMATCH")
        frozen = manifest.get("root_claim_snapshot")
        if not isinstance(frozen, dict) or not isinstance(root_claim_snapshot_descriptor, dict):
            return fail("ROOT_CLAIM_SNAPSHOT_BINDING_MISSING")
        fields = ("source_id", "source_snapshot_id", "retrieved_at_utc", "payload_hash",
                  "hash_algorithm", "hash_scope", "canonicalization_version",
                  "media_type", "payload_retention")
        if any(frozen.get(field) != root_claim_snapshot_descriptor.get(field) for field in fields):
            return fail("ROOT_CLAIM_SNAPSHOT_DESCRIPTOR_MISMATCH")
        if not isinstance(root_claim_payload, bytes):
            return fail("ROOT_CLAIM_PAYLOAD_UNAVAILABLE")
        if root_claim_snapshot_descriptor.get("media_type") != "application/json":
            return fail("ROOT_CLAIM_MEDIA_TYPE_UNSUPPORTED")
        if root_claim_snapshot_descriptor.get("payload_retention") != "RETAINED":
            return fail("ROOT_CLAIM_PAYLOAD_NOT_RETAINED")
        if _time(root_claim_snapshot_descriptor.get("retrieved_at_utc")) > _time(knowledge_cutoff_utc):
            return fail("ROOT_CLAIM_SNAPSHOT_AFTER_CUTOFF")
        if verify_snapshot_payload(root_claim_snapshot_descriptor, root_claim_payload).get("status") != "HASH_VERIFIED":
            return fail("ROOT_CLAIM_SNAPSHOT_HASH_MISMATCH")
        root_claim = json.loads(root_claim_payload.decode("utf-8"))
        if not isinstance(root_claim, dict):
            return fail("ROOT_CLAIM_DOCUMENT_INVALID")
        if (_sha(_canonical(root_claim)) != manifest.get("root_claim_hash")
                or root_claim.get("claim_id") != manifest.get("root_claim_id")
                or root_claim.get("contract_version") != manifest.get("root_claim_contract_version")):
            return fail("ROOT_CLAIM_BINDING_MISMATCH")
        base = dict(manifest)
        base.pop("root_claim_snapshot", None)
        base["manifest_version"] = "1.1.0"
        base["manifest_hash"] = _sha(_canonical({k: v for k, v in base.items() if k != "manifest_hash"}))
        verified = verify_actor_registry_reconstruction_manifest_v1_1(
            manifest=base, actor_registry=actor_registry,
            snapshots_by_id=snapshots_by_id, payloads_by_id=payloads_by_id,
            knowledge_cutoff_utc=knowledge_cutoff_utc, valid_time_utc=valid_time_utc,
        )
        if verified.get("status") != "ACTOR_REGISTRY_RECONSTRUCTION_VERIFIED":
            return {"status": "INTEGRITY_FAILED", "reason": "REGISTRY_EVIDENCE_VERIFICATION_FAILED",
                    "registry_verification": verified}
        return {"status": "ROOT_CLAIM_AND_ACTOR_REGISTRY_RECONSTRUCTION_VERIFIED",
                "root_claim_id": root_claim["claim_id"],
                "root_claim_snapshot_id": frozen["source_snapshot_id"],
                "root_claim_snapshot_status": "HASH_VERIFIED",
                "registry_verification": verified}
    except (KeyError, TypeError, ValueError, UnicodeDecodeError, json.JSONDecodeError):
        return fail("INVALID_ROOT_CLAIM_OR_SNAPSHOT")
