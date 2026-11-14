"""End-to-end offline reconstruction across snapshots and Actor Registry v1.2.

Snapshot payload format: UTF-8 JSON object with record_type, coverage_status,
and records. Payload bytes are verified before records are exposed to resolvers.
"""
import json
from datetime import datetime

from iwfi.attribution_reconstruction import verify_attribution_reconstruction
from iwfi.evidence_snapshot_provenance import verify_snapshot_payload
from iwfi.typed_evidence_provenance import resolve_actor_registry_evidence_as_of

_ALLOWED_RECORD_TYPES = {"SOURCE_OBSERVATION", "ATTRIBUTION_CLAIM"}
_ALLOWED_COVERAGE = {"COMPLETE", "PARTIAL"}


def _parse_utc(value):
    if not isinstance(value, str) or len(value) != 20 or not value.endswith("Z"):
        return None
    try:
        return datetime.strptime(value, "%Y-%m-%dT%H:%M:%SZ")
    except ValueError:
        return None


def _load_verified_snapshot_records(snapshot, payload):
    integrity = verify_snapshot_payload(snapshot, payload)
    if integrity.get("status") != "HASH_VERIFIED":
        return None, {"status": "INTEGRITY_FAILED", "reason": integrity.get("status")}
    if snapshot.get("media_type") != "application/json":
        return None, {"status": "INVALID_SNAPSHOT_PAYLOAD", "reason": "UNSUPPORTED_MEDIA_TYPE"}
    try:
        document = json.loads(payload.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError):
        return None, {"status": "INVALID_SNAPSHOT_PAYLOAD", "reason": "INVALID_JSON"}
    if not isinstance(document, dict):
        return None, {"status": "INVALID_SNAPSHOT_PAYLOAD", "reason": "EXPECTED_OBJECT"}
    record_type = document.get("record_type")
    coverage = document.get("coverage_status")
    records = document.get("records")
    if record_type not in _ALLOWED_RECORD_TYPES or coverage not in _ALLOWED_COVERAGE:
        return None, {"status": "INVALID_SNAPSHOT_PAYLOAD", "reason": "INVALID_RECORD_TYPE_OR_COVERAGE"}
    if not isinstance(records, list) or any(not isinstance(item, dict) for item in records):
        return None, {"status": "INVALID_SNAPSHOT_PAYLOAD", "reason": "RECORDS_MUST_BE_OBJECT_ARRAY"}
    id_field = "observation_id" if record_type == "SOURCE_OBSERVATION" else "claim_id"
    normalized = []
    for item in records:
        if not isinstance(item.get(id_field), str) or not item[id_field].strip():
            return None, {"status": "INVALID_SNAPSHOT_PAYLOAD", "reason": "RECORD_ID_MISSING"}
        record = dict(item)
        record.setdefault("retrieved_at_utc", snapshot.get("retrieved_at_utc"))
        record.setdefault("recorded_at_utc", record.get("retrieved_at_utc"))
        normalized.append(record)
    return {
        "record_type": record_type,
        "coverage_status": coverage,
        "records": normalized,
    }, {"status": "HASH_VERIFIED", "record_type": record_type,
        "coverage_status": coverage, "record_count": len(normalized)}


def reconstruct_actor_registry_as_of(
    *, manifest, attribution_claim, actor_registry, snapshots_by_id,
    payloads_by_id, knowledge_cutoff_utc, valid_time_utc,
):
    """Verify manifest + exact payloads, then resolve actor refs as-of offline.

    The claim supplied here must be the same claim frozen by the manifest.
    The resolver receives only records decoded from hash-verified snapshot bytes.
    """
    cutoff = _parse_utc(knowledge_cutoff_utc)
    valid_time = _parse_utc(valid_time_utc)
    if cutoff is None or valid_time is None:
        return {"status": "INVALID_INPUT", "reason": "INVALID_QUERY_TIME"}
    if not isinstance(actor_registry, dict) or actor_registry.get("contract_version") != "1.2.0":
        return {"status": "INVALID_INPUT", "reason": "ACTOR_REGISTRY_V1_2_REQUIRED"}
    if not isinstance(snapshots_by_id, dict) or not isinstance(payloads_by_id, dict):
        return {"status": "INVALID_INPUT", "reason": "SNAPSHOT_MAPS_REQUIRED"}

    integrity = verify_attribution_reconstruction(
        manifest=manifest, claim=attribution_claim,
        snapshots_by_id=snapshots_by_id, payloads_by_id=payloads_by_id,
    )
    if integrity.get("status") != "RECONSTRUCTION_INPUTS_VERIFIED":
        return {"status": "INTEGRITY_FAILED", "integrity": integrity}

    if manifest.get("knowledge_cutoff_utc") != knowledge_cutoff_utc:
        return {"status": "INVALID_INPUT", "reason": "KNOWLEDGE_CUTOFF_MISMATCH"}
    if manifest.get("valid_time_utc") != valid_time_utc:
        return {"status": "INVALID_INPUT", "reason": "VALID_TIME_MISMATCH"}

    typed_snapshots = {}
    decoded = []
    for dependency in manifest.get("dependencies", []):
        sid = dependency.get("source_snapshot_id")
        snapshot = snapshots_by_id.get(sid)
        payload = payloads_by_id.get(sid)
        if not isinstance(snapshot, dict) or not isinstance(payload, bytes):
            return {"status": "INTEGRITY_FAILED", "reason": "DEPENDENCY_UNAVAILABLE",
                    "source_snapshot_id": sid}
        retrieved = _parse_utc(snapshot.get("retrieved_at_utc"))
        if retrieved is None or retrieved > cutoff:
            return {"status": "INVALID_INPUT", "reason": "SNAPSHOT_AFTER_KNOWLEDGE_CUTOFF",
                    "source_snapshot_id": sid}
        records_document, result = _load_verified_snapshot_records(snapshot, payload)
        if records_document is None:
            return {"status": "INTEGRITY_FAILED", "source_snapshot_id": sid,
                    "snapshot_result": result}
        record_type = records_document["record_type"]
        current = typed_snapshots.setdefault(record_type, {
            "status": records_document["coverage_status"], "records": [],
        })
        # Multiple snapshots form a complete collection only if every member is complete.
        if records_document["coverage_status"] == "PARTIAL":
            current["status"] = "PARTIAL"
        current["records"].extend(records_document["records"])
        decoded.append({"source_snapshot_id": sid, **result})

    claim_id = attribution_claim.get("claim_id") if isinstance(attribution_claim, dict) else None
    if not isinstance(claim_id, str) or not claim_id.strip():
        return {"status": "INVALID_INPUT", "reason": "CLAIM_ID_REQUIRED"}
    claim_snapshot = typed_snapshots.setdefault("ATTRIBUTION_CLAIM", {
        "status": "COMPLETE", "records": [],
    })
    existing = [item for item in claim_snapshot["records"] if item.get("claim_id") == claim_id]
    if existing and any(item != attribution_claim for item in existing):
        return {"status": "INTEGRITY_FAILED", "reason": "CLAIM_SNAPSHOT_CONFLICT"}
    if not existing:
        claim_snapshot["records"].append(dict(attribution_claim))

    resolution = resolve_actor_registry_evidence_as_of(
        actor_registry, typed_snapshots, knowledge_cutoff_utc, valid_time_utc,
    )
    if resolution.get("status") != "RESOLVED":
        return {"status": "EVIDENCE_RESOLUTION_FAILED", "integrity": integrity,
                "verified_snapshots": decoded, "resolution": resolution}
    return {
        "status": "ACTOR_REGISTRY_RECONSTRUCTED",
        "claim_id": claim_id,
        "claim_epistemic_status": attribution_claim.get("epistemic_status"),
        "knowledge_cutoff_utc": knowledge_cutoff_utc,
        "valid_time_utc": valid_time_utc,
        "verified_snapshots": decoded,
        "snapshot_retention_warnings": [
            item["source_snapshot_id"] for item in decoded
            if snapshots_by_id[item["source_snapshot_id"]].get("payload_retention") != "RETAINED"
        ],
        "integrity": integrity,
        "resolution": resolution,
    }
