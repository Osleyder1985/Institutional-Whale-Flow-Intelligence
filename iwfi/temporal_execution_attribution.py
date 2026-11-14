"""Strict bitemporal Actor Registry integration for execution participant resolution."""
from copy import deepcopy
from datetime import datetime
import re

from iwfi.execution_participant_roles import (
    resolve_execution_participants,
    validate_execution_participant_role_links,
    validate_execution_participant_roles,
)

_UTC = re.compile(r"^\\d{4}-\\d{2}-\\d{2}T\\d{2}:\\d{2}:\\d{2}Z$")
_ALLOWED_IDENTITY = {"VERIFIED", "PROVIDER_LABELLED", "INFERRED", "UNKNOWN", "DISPUTED"}


def _time(value):
    if not isinstance(value, str) or not _UTC.fullmatch(value):
        return None
    try:
        return datetime.strptime(value, "%Y-%m-%dT%H:%M:%SZ")
    except ValueError:
        return None


def _known_and_recorded(item, cutoff, label, errors):
    known = _time(item.get("known_at_utc"))
    recorded = _time(item.get("recorded_at_utc"))
    if known is None:
        errors.append(f"{label}: invalid known_at_utc")
    if recorded is None:
        errors.append(f"{label}: invalid recorded_at_utc")
    if known and recorded and recorded < known:
        errors.append(f"{label}: recorded_at_utc precedes known_at_utc")
    return bool(known and recorded and known <= cutoff and recorded <= cutoff)


def _valid_at(item, valid_time):
    start_value, end_value = item.get("valid_from_utc"), item.get("valid_to_utc")
    start = _time(start_value) if start_value is not None else None
    end = _time(end_value) if end_value is not None else None
    if start_value is not None and start is None or end_value is not None and end is None:
        return False
    if start and end and end < start:
        return False
    return (start is None or start <= valid_time) and (end is None or valid_time <= end)


def validate_actor_registry_v11(registry):
    """Validate the temporal fields and referential integrity required by the v1.1 resolver."""
    if not isinstance(registry, dict) or registry.get("contract_version") != "1.1.0":
        return ["unsupported Actor Registry contract version"]
    actors = registry.get("actors")
    relationships = registry.get("relationships")
    if not isinstance(actors, list) or not isinstance(relationships, list):
        return ["actors and relationships must be lists"]
    errors, ids = [], set()
    for index, actor in enumerate(actors):
        label = f"actors[{index}]"
        if not isinstance(actor, dict):
            errors.append(f"{label} must be an object")
            continue
        actor_id = actor.get("actor_id")
        if not isinstance(actor_id, str) or not actor_id.strip():
            errors.append(f"{label} has invalid actor_id")
        elif actor_id in ids:
            errors.append(f"duplicate actor_id: {actor_id}")
        else:
            ids.add(actor_id)
        if actor.get("identity_status") not in _ALLOWED_IDENTITY:
            errors.append(f"{label}: invalid identity_status")
        _known_and_recorded(actor, datetime.max, label, errors)
        if not _valid_at(actor, datetime.min):
            # Validate interval shape/order without requiring the actor to be currently active.
            start, end = actor.get("valid_from_utc"), actor.get("valid_to_utc")
            if start is not None and _time(start) is None or end is not None and _time(end) is None:
                errors.append(f"{label}: invalid validity interval")
            elif _time(start) and _time(end) and _time(end) < _time(start):
                errors.append(f"{label}: validity interval ends before it starts")
        for field in ("aliases", "classifications"):
            items = actor.get(field, [])
            if not isinstance(items, list):
                errors.append(f"{label}: {field} must be a list")
                continue
            for item_index, item in enumerate(items):
                sublabel = f"{label}.{field}[{item_index}]"
                if not isinstance(item, dict):
                    errors.append(f"{sublabel} must be an object")
                    continue
                _known_and_recorded(item, datetime.max, sublabel, errors)
                start, end = item.get("valid_from_utc"), item.get("valid_to_utc")
                if start is not None and _time(start) is None or end is not None and _time(end) is None:
                    errors.append(f"{sublabel}: invalid validity interval")
                elif _time(start) and _time(end) and _time(end) < _time(start):
                    errors.append(f"{sublabel}: validity interval ends before it starts")
    relationship_ids = set()
    for index, item in enumerate(relationships):
        label = f"relationships[{index}]"
        if not isinstance(item, dict):
            errors.append(f"{label} must be an object")
            continue
        rid = item.get("relationship_id")
        if not isinstance(rid, str) or not rid.strip() or rid in relationship_ids:
            errors.append(f"{label}: invalid or duplicate relationship_id")
        relationship_ids.add(rid)
        if item.get("subject_actor_id") not in ids or item.get("object_actor_id") not in ids:
            errors.append(f"{label}: relationship actor reference not found")
        _known_and_recorded(item, datetime.max, label, errors)
        start, end = item.get("valid_from_utc"), item.get("valid_to_utc")
        if start is not None and _time(start) is None or end is not None and _time(end) is None:
            errors.append(f"{label}: invalid validity interval")
        elif _time(start) and _time(end) and _time(end) < _time(start):
            errors.append(f"{label}: validity interval ends before it starts")
    return sorted(set(errors))


def resolve_actor_identity_as_of(registry, actor_id, knowledge_cutoff_utc, valid_time_utc):
    """Return identity eligibility using separate system-knowledge and real-world-validity clocks."""
    cutoff, valid_time = _time(knowledge_cutoff_utc), _time(valid_time_utc)
    if cutoff is None or valid_time is None:
        return {"status": "INVALID_INPUT", "actor": None}
    errors = validate_actor_registry_v11(registry)
    if errors:
        return {"status": "INVALID_REGISTRY", "actor": None, "errors": errors}
    matches = [item for item in registry["actors"] if item["actor_id"] == actor_id]
    if len(matches) != 1:
        return {"status": "UNKNOWN", "actor": None}
    actor = matches[0]
    known = _time(actor["known_at_utc"])
    recorded = _time(actor["recorded_at_utc"])
    if known > cutoff or recorded > cutoff or not _valid_at(actor, valid_time):
        return {"status": "NOT_ELIGIBLE_AS_OF", "actor": None}
    status = actor["identity_status"]
    if status in {"UNKNOWN", "DISPUTED"}:
        return {"status": status, "actor": None}
    return {"status": "ELIGIBLE", "actor": actor}


def resolve_relationship_as_of(registry, subject_actor_id, object_actor_id, relationship_type,
                               knowledge_cutoff_utc, valid_time_utc):
    """Resolve only direct relationship claims known by cutoff and valid at the event time."""
    cutoff, valid_time = _time(knowledge_cutoff_utc), _time(valid_time_utc)
    if cutoff is None or valid_time is None:
        return {"status": "INVALID_INPUT", "evidence_refs": []}
    errors = validate_actor_registry_v11(registry)
    if errors:
        return {"status": "INVALID_REGISTRY", "evidence_refs": [], "errors": errors}
    matches = []
    for item in registry["relationships"]:
        if (item.get("subject_actor_id"), item.get("object_actor_id"), item.get("relationship_type")) != (
            subject_actor_id, object_actor_id, relationship_type
        ):
            continue
        if _time(item["known_at_utc"]) <= cutoff and _time(item["recorded_at_utc"]) <= cutoff and _valid_at(item, valid_time):
            matches.append(item)
    statuses = {item.get("status") for item in matches}
    if not matches:
        status = "UNKNOWN"
    elif len(statuses) > 1 or "DISPUTED" in statuses:
        status = "DISPUTED"
    else:
        status = next(iter(statuses))
    return {"status": status, "evidence_refs": sorted({
        ref for item in matches for ref in item.get("evidence_refs", [])
    })}


def resolve_execution_participants_as_of(claim_registry, trade, knowledge_cutoff_utc,
                                         actor_registry, observation_ids):
    """Resolve role claims only when actor identity is bitemporally eligible for the execution."""
    cutoff = _time(knowledge_cutoff_utc)
    event_time = _time(trade.get("event_time_utc")) if isinstance(trade, dict) else None
    if cutoff is None or event_time is None:
        return {"status": "INVALID_INPUT", "participants": [], "errors": ["invalid event_time/cutoff"]}
    actor_errors = validate_actor_registry_v11(actor_registry)
    if actor_errors:
        return {"status": "INVALID_INPUT", "participants": [], "errors": actor_errors}
    if not isinstance(claim_registry, dict) or not isinstance(claim_registry.get("claims"), list):
        return {"status": "INVALID_INPUT", "participants": [], "errors": ["invalid claim registry"]}
    claims = claim_registry["claims"]
    # Validate claim structure and execution links independently of the Actor Registry.
    candidate_ids = set()
    for claim in claims:
        if isinstance(claim, dict):
            if isinstance(claim.get("actor_id"), str):
                candidate_ids.add(claim["actor_id"])
            candidate_ids.update(x for x in claim.get("candidate_actor_ids", []) if isinstance(x, str))
    structural_errors = validate_execution_participant_role_links(
        trade, claim_registry, sorted(candidate_ids), observation_ids
    )
    if structural_errors:
        return {"status": "INVALID_INPUT", "participants": [], "errors": structural_errors}

    actor_ids = {item["actor_id"] for item in actor_registry["actors"]}
    visible_claims = []
    for original in claims:
        claim = deepcopy(original)
        known, recorded = _time(claim.get("known_at_utc")), _time(claim.get("recorded_at_utc"))
        if known is None or recorded is None:
            return {"status": "INVALID_INPUT", "participants": [], "errors": ["malformed claim timestamps"]}
        if known > cutoff or recorded > cutoff:
            continue
        actor_id = claim.get("actor_id")
        if claim.get("epistemic_status") in {"DIRECT", "INFERRED"}:
            identity = resolve_actor_identity_as_of(actor_registry, actor_id, knowledge_cutoff_utc,
                                                     trade["event_time_utc"])
            if identity["status"] != "ELIGIBLE":
                # Preserve the role, but do not emit an ineligible named actor.
                claim["actor_id"] = None
                claim["candidate_actor_ids"] = []
                claim["epistemic_status"] = "UNKNOWN"
                claim["attribution_method"] = "NONE"
                claim["source_observation_ids"] = []
                claim["supporting_evidence"] = []
                claim["counter_evidence"] = []
            elif identity["actor"]["identity_status"] != "VERIFIED" and claim["epistemic_status"] == "DIRECT":
                # The execution disclosure may be direct while the actor's identity is only inferred/labelled.
                claim["epistemic_status"] = "INFERRED"
                claim["attribution_method"] = "OTHER"
        elif claim.get("epistemic_status") == "DISPUTED":
            claim["candidate_actor_ids"] = [
                candidate for candidate in claim.get("candidate_actor_ids", [])
                if resolve_actor_identity_as_of(actor_registry, candidate, knowledge_cutoff_utc,
                                                trade["event_time_utc"])["status"] == "ELIGIBLE"
            ]
            if len(claim["candidate_actor_ids"]) < 2:
                claim["candidate_actor_ids"] = []
                claim["epistemic_status"] = "UNKNOWN"
                claim["attribution_method"] = "NONE"
                claim["source_observation_ids"] = []
                claim["counter_evidence"] = []
        visible_claims.append(claim)

    # Claims converted to UNKNOWN must be schema-valid and must not keep unsupported refs.
    filtered_registry = {"contract_version": claim_registry.get("contract_version"), "claims": visible_claims}
    filtered_trade = deepcopy(trade)
    filtered_trade["participant_role_claim_ids"] = [c["claim_id"] for c in visible_claims]
    safe_actor_ids = actor_ids | candidate_ids
    result = resolve_execution_participants(
        filtered_registry, filtered_trade, knowledge_cutoff_utc, sorted(safe_actor_ids), observation_ids
    )
    return result
