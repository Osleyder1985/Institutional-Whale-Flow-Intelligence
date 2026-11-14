"""Typed, point-in-time evidence resolution for Actor Registry v1.2.

This module resolves references only against caller-supplied, versioned snapshots.
It performs no I/O and never upgrades an upstream epistemic status.
"""
from datetime import datetime
import re

_UTC = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z$")
_ALLOWED_TYPES = {"SOURCE_OBSERVATION", "ATTRIBUTION_CLAIM"}
_ALLOWED_STATUS = {"VERIFIED", "PROVIDER_LABELLED", "INFERRED", "UNKNOWN", "DISPUTED"}


def _parse_time(value):
    if not isinstance(value, str) or not _UTC.fullmatch(value):
        return None
    try:
        return datetime.strptime(value, "%Y-%m-%dT%H:%M:%SZ")
    except ValueError:
        return None


def _index_unique(items, id_field):
    index = {}
    duplicates = set()
    for item in items:
        if not isinstance(item, dict):
            continue
        key = item.get(id_field)
        if isinstance(key, str) and key.strip():
            if key in index:
                duplicates.add(key)
            else:
                index[key] = item
    return index, duplicates


def _snapshot_status(snapshot):
    if not isinstance(snapshot, dict):
        return "NOT_LOADED"
    status = snapshot.get("status")
    if status not in {"COMPLETE", "PARTIAL"}:
        return "NOT_LOADED"
    return status


def _is_visible(record, cutoff, valid_time, require_validity):
    known = _parse_time(record.get("known_at_utc", record.get("retrieved_at_utc")))
    recorded = _parse_time(record.get("recorded_at_utc", record.get("retrieved_at_utc")))
    if known is None or recorded is None or recorded < known:
        return False, "INVALID_TEMPORAL_METADATA"
    if known > cutoff or recorded > cutoff:
        return False, "AFTER_KNOWLEDGE_CUTOFF"
    if require_validity:
        start_value, end_value = record.get("valid_from_utc"), record.get("valid_to_utc")
        start = _parse_time(start_value) if start_value is not None else None
        end = _parse_time(end_value) if end_value is not None else None
        if (start_value is not None and start is None) or (end_value is not None and end is None):
            return False, "INVALID_VALIDITY_INTERVAL"
        if start and end and end < start:
            return False, "INVALID_VALIDITY_INTERVAL"
        if (start and start > valid_time) or (end and end < valid_time):
            return False, "NOT_VALID_AT_EVENT_TIME"
    event_time = record.get("event_time_utc")
    if event_time is not None:
        event = _parse_time(event_time)
        if event is None or event > cutoff:
            return False, "INVALID_OR_FUTURE_EVENT_TIME"
    return True, "ELIGIBLE"


def _resolve(ref, snapshots, cutoff, valid_time, predicate=None):
    ref_type, ref_id = ref.get("ref_type"), ref.get("ref_id")
    if ref_type not in _ALLOWED_TYPES or not isinstance(ref_id, str) or not ref_id.strip():
        return None, "INVALID_REFERENCE"
    snapshot = snapshots.get(ref_type)
    state = _snapshot_status(snapshot)
    if state == "NOT_LOADED":
        return None, "SNAPSHOT_NOT_LOADED"
    records = snapshot.get("records")
    if not isinstance(records, list):
        return None, "INVALID_SNAPSHOT"
    id_field = "observation_id" if ref_type == "SOURCE_OBSERVATION" else "claim_id"
    index, duplicates = _index_unique(records, id_field)
    if ref_id in duplicates:
        return None, "AMBIGUOUS_DUPLICATE_ID"
    record = index.get(ref_id)
    if record is None:
        return None, "MISSING_FROM_COMPLETE_SNAPSHOT" if state == "COMPLETE" else "NOT_FOUND_IN_PARTIAL_SNAPSHOT"
    eligible, reason = _is_visible(record, cutoff, valid_time, ref_type == "ATTRIBUTION_CLAIM")
    if not eligible:
        return None, reason
    if ref_type == "SOURCE_OBSERVATION" and predicate in {"BUYER", "SELLER", "BENEFICIAL_OWNER", "OWNS", "CONTROLS"}:
        observation_type = str(record.get("observation_type", "")).upper()
        if observation_type in {"ON_CHAIN_TRANSACTION", "TOKEN_TRANSFER", "TRANSFER"}:
            return None, "TRANSFER_DOES_NOT_PROVE_OWNERSHIP_OR_EXECUTION_SIDE"
    if ref_type == "ATTRIBUTION_CLAIM":
        status = record.get("epistemic_status", record.get("status"))
        if status not in _ALLOWED_STATUS:
            return None, "INVALID_UPSTREAM_EPISTEMIC_STATUS"
        nested = record.get("evidence_refs", [])
        if not isinstance(nested, list):
            return None, "INVALID_UPSTREAM_EVIDENCE"
        if any(not isinstance(item, dict) or item.get("ref_type") != "SOURCE_OBSERVATION" for item in nested):
            return None, "CIRCULAR_OR_UNSUPPORTED_CLAIM_REFERENCE"
        return {"record": record, "epistemic_status": status}, "ELIGIBLE"
    return {"record": record, "epistemic_status": None}, "ELIGIBLE"


def resolve_typed_evidence_refs(evidence_refs, snapshots, knowledge_cutoff_utc,
                                valid_time_utc, require_all=True, predicate=None):
    """Resolve a single evidence polarity list; return fail-closed deterministic result.

    Snapshot shape: {"status": "COMPLETE"|"PARTIAL", "records": [...]}
    Missing snapshot != missing record. Partial snapshots never prove non-existence.
    """
    cutoff, valid_time = _parse_time(knowledge_cutoff_utc), _parse_time(valid_time_utc)
    if cutoff is None or valid_time is None or not isinstance(evidence_refs, list) or not isinstance(snapshots, dict):
        return {"status": "INVALID_INPUT", "resolved": [], "rejected": ["INVALID_QUERY_TIME_OR_REFS"]}
    resolved, rejected = [], []
    seen = set()
    for ref in evidence_refs:
        if not isinstance(ref, dict):
            rejected.append({"ref": ref, "reason": "INVALID_REFERENCE"})
            continue
        key = (ref.get("ref_type"), ref.get("ref_id"))
        if key in seen:
            rejected.append({"ref": ref, "reason": "DUPLICATE_REFERENCE"})
            continue
        seen.add(key)
        value, reason = _resolve(ref, snapshots, cutoff, valid_time, predicate)
        if value is None:
            rejected.append({"ref": ref, "reason": reason})
        else:
            resolved.append({"ref": ref, **value})
    if rejected and require_all:
        return {"status": "INVALID_INPUT", "resolved": [], "rejected": rejected}
    return {"status": "RESOLVED_WITH_REJECTIONS" if rejected else "RESOLVED",
            "resolved": resolved, "rejected": rejected}


def resolve_actor_evidence_as_of(actor_record, snapshots, knowledge_cutoff_utc,
                                 valid_time_utc):
    """Resolve supporting and counter evidence independently; never net them."""
    if not isinstance(actor_record, dict):
        return {"status": "INVALID_INPUT", "supporting": None, "counter": None}
    supporting = resolve_typed_evidence_refs(
        actor_record.get("evidence_refs"), snapshots, knowledge_cutoff_utc,
        valid_time_utc)
    counter = resolve_typed_evidence_refs(
        actor_record.get("counter_evidence_refs"), snapshots, knowledge_cutoff_utc,
        valid_time_utc)
    if supporting["status"] == "INVALID_INPUT" or counter["status"] == "INVALID_INPUT":
        return {"status": "INVALID_INPUT", "supporting": supporting, "counter": counter}
    return {"status": "RESOLVED", "supporting": supporting, "counter": counter,
            "identity_status": actor_record.get("identity_status")}


def resolve_actor_registry_evidence_as_of(registry, snapshots,
                                          knowledge_cutoff_utc, valid_time_utc):
    """Resolve evidence for actors, aliases, classifications and relationships."""
    if not isinstance(registry, dict) or registry.get("contract_version") != "1.2.0":
        return {"status": "INVALID_INPUT", "records": [],
                "errors": ["unsupported Actor Registry contract version"]}
    cutoff, valid_time = _parse_time(knowledge_cutoff_utc), _parse_time(valid_time_utc)
    if cutoff is None or valid_time is None:
        return {"status": "INVALID_INPUT", "records": [],
                "errors": ["invalid query timestamps"]}
    collections = []
    for index, actor in enumerate(registry.get("actors", [])):
        collections.append((f"actors[{index}]", actor))
        if isinstance(actor, dict):
            for field in ("aliases", "classifications"):
                for subindex, item in enumerate(actor.get(field, [])):
                    collections.append((f"actors[{index}].{field}[{subindex}]", item))
    for index, relationship in enumerate(registry.get("relationships", [])):
        collections.append((f"relationships[{index}]", relationship))
    results, errors = [], []
    for label, item in collections:
        if not isinstance(item, dict):
            errors.append(f"{label}: expected object")
            continue
        known = _parse_time(item.get("known_at_utc"))
        recorded = _parse_time(item.get("recorded_at_utc"))
        if known is None or recorded is None or recorded < known:
            errors.append(f"{label}: invalid bitemporal metadata")
            continue
        if known > cutoff or recorded > cutoff:
            results.append({"record": label, "status": "EXCLUDED_AFTER_CUTOFF"})
            continue
        start_value, end_value = item.get("valid_from_utc"), item.get("valid_to_utc")
        start = _parse_time(start_value) if start_value is not None else None
        end = _parse_time(end_value) if end_value is not None else None
        if ((start_value is not None and start is None) or
                (end_value is not None and end is None) or
                (start is not None and end is not None and end < start)):
            errors.append(f"{label}: invalid validity interval")
            continue
        if (start and start > valid_time) or (end and end < valid_time):
            results.append({"record": label, "status": "EXCLUDED_OUTSIDE_VALIDITY"})
            continue
        for polarity in ("evidence_refs", "counter_evidence_refs"):
            if polarity not in item:
                continue
            resolved = resolve_typed_evidence_refs(
                item[polarity], snapshots, knowledge_cutoff_utc,
                valid_time_utc, require_all=True)
            results.append({"record": label, "polarity": polarity,
                            "resolution": resolved})
            if resolved["status"] == "INVALID_INPUT":
                errors.append(f"{label}.{polarity}: evidence resolution failed")
    return {"status": "INVALID_INPUT" if errors else "RESOLVED",
            "records": results, "errors": errors}
