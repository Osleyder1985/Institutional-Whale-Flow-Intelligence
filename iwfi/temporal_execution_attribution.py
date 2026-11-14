"""Strict bitemporal Actor Registry integration for execution participant resolution."""
from copy import deepcopy
from datetime import datetime
import re

from iwfi.execution_participant_roles import (
    resolve_execution_participants,
    validate_execution_participant_role_links,
    validate_execution_participant_roles,
)

_UTC = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z$")
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
        if not isinstance(rid, str) or not rid.strip():
            errors.append(f"{label}: invalid relationship_id")
        elif rid in relationship_ids:
            errors.append(f"{label}: duplicate relationship_id")
        else:
            relationship_ids.add(rid)
        subject, target = item.get("subject_actor_id"), item.get("object_actor_id")
        if not isinstance(subject, str) or subject not in ids or not isinstance(target, str) or target not in ids:
            errors.append(f"{label}: relationship actor reference not found")
        if item.get("status") not in {"VERIFIED", "PROVIDER_LABELLED", "INFERRED", "UNKNOWN", "DISPUTED"}:
            errors.append(f"{label}: invalid relationship status")
        if not isinstance(item.get("relationship_type"), str) or not item.get("relationship_type").strip():
            errors.append(f"{label}: invalid relationship_type")
        for evidence_field in ("evidence_refs", "counter_evidence_refs"):
            refs = item.get(evidence_field)
            if not isinstance(refs, list) or any(not isinstance(ref, str) or not ref.strip() for ref in refs):
                errors.append(f"{label}: invalid {evidence_field}")
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
    if status == "UNKNOWN":
        return {"status": "UNKNOWN", "actor": None}
    if status == "DISPUTED" or actor.get("counter_evidence_refs"):
        return {"status": "DISPUTED", "actor": None}
    return {"status": "ELIGIBLE", "actor": actor}


def resolve_actor_alias_as_of(registry, alias_value, knowledge_cutoff_utc, valid_time_utc,
                             alias_type=None, scope=None):
    """Resolve aliases using separate knowledge-cutoff and real-world-validity instants."""
    cutoff, valid_time = _time(knowledge_cutoff_utc), _time(valid_time_utc)
    if cutoff is None or valid_time is None or not isinstance(alias_value, str) or not alias_value.strip():
        return {"status": "INVALID_INPUT", "actor_ids": []}
    errors = validate_actor_registry_v11(registry)
    if errors:
        return {"status": "INVALID_REGISTRY", "actor_ids": [], "errors": errors}
    matches = set()
    for actor in registry["actors"]:
        identity = resolve_actor_identity_as_of(registry, actor["actor_id"], knowledge_cutoff_utc, valid_time_utc)
        if identity["status"] != "ELIGIBLE":
            continue
        for alias in actor.get("aliases", []):
            if alias.get("value", "").casefold() != alias_value.casefold():
                continue
            if alias_type is not None and alias.get("alias_type") != alias_type:
                continue
            if scope is not None and alias.get("scope") != scope:
                continue
            known, recorded = _time(alias.get("known_at_utc")), _time(alias.get("recorded_at_utc"))
            if known is None or recorded is None or known > cutoff or recorded > cutoff:
                continue
            if _valid_at(alias, valid_time):
                matches.add(actor["actor_id"])
    ordered = sorted(matches)
    if not ordered:
        return {"status": "UNKNOWN", "actor_ids": []}
    if len(ordered) > 1:
        return {"status": "AMBIGUOUS", "actor_ids": ordered}
    return {"status": "UNIQUE", "actor_ids": ordered}


def resolve_relationship_as_of(registry, subject_actor_id, object_actor_id, relationship_type,
                               knowledge_cutoff_utc, valid_time_utc):
    """Resolve only direct relationship claims known by cutoff and valid at the event time."""
    cutoff, valid_time = _time(knowledge_cutoff_utc), _time(valid_time_utc)
    if cutoff is None or valid_time is None:
        return {"status": "INVALID_INPUT", "evidence_refs": []}
    errors = validate_actor_registry_v11(registry)
    if errors:
        return {"status": "INVALID_REGISTRY", "evidence_refs": [], "errors": errors}
    subject_identity = resolve_actor_identity_as_of(
        registry, subject_actor_id, knowledge_cutoff_utc, valid_time_utc
    )
    object_identity = resolve_actor_identity_as_of(
        registry, object_actor_id, knowledge_cutoff_utc, valid_time_utc
    )
    if subject_identity["status"] == "DISPUTED" or object_identity["status"] == "DISPUTED":
        return {"status": "DISPUTED", "evidence_refs": []}
    if subject_identity["status"] != "ELIGIBLE" or object_identity["status"] != "ELIGIBLE":
        return {"status": "UNKNOWN", "evidence_refs": []}
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
    elif len(statuses) > 1 or "DISPUTED" in statuses or any(item.get("counter_evidence_refs") for item in matches):
        status = "DISPUTED"
    else:
        status = next(iter(statuses))
    return {"status": status, "evidence_refs": sorted({
        ref for item in matches for ref in item.get("evidence_refs", [])
    })}


def resolve_relationship_id_as_of(registry, relationship_id, knowledge_cutoff_utc, valid_time_utc):
    """Resolve one explicitly referenced direct relationship claim by ID and both temporal axes."""
    cutoff, valid_time = _time(knowledge_cutoff_utc), _time(valid_time_utc)
    if cutoff is None or valid_time is None or not isinstance(relationship_id, str) or not relationship_id.strip():
        return {"status": "INVALID_INPUT", "relationship": None}
    errors = validate_actor_registry_v11(registry)
    if errors:
        return {"status": "INVALID_REGISTRY", "relationship": None, "errors": errors}
    matches = [item for item in registry["relationships"] if item["relationship_id"] == relationship_id]
    if len(matches) != 1:
        return {"status": "UNKNOWN", "relationship": None}
    relation = matches[0]
    subject = resolve_actor_identity_as_of(
        registry, relation["subject_actor_id"], knowledge_cutoff_utc, valid_time_utc
    )
    target = resolve_actor_identity_as_of(
        registry, relation["object_actor_id"], knowledge_cutoff_utc, valid_time_utc
    )
    if subject["status"] == "DISPUTED" or target["status"] == "DISPUTED":
        return {"status": "DISPUTED", "relationship": None}
    if subject["status"] != "ELIGIBLE" or target["status"] != "ELIGIBLE":
        return {"status": "UNKNOWN", "relationship": None}
    if _time(relation["known_at_utc"]) > cutoff or _time(relation["recorded_at_utc"]) > cutoff:
        return {"status": "UNKNOWN", "relationship": None}
    if not _valid_at(relation, valid_time):
        return {"status": "UNKNOWN", "relationship": None}
    if relation.get("counter_evidence_refs") or relation.get("status") == "DISPUTED":
        return {"status": "DISPUTED", "relationship": None}
    return {"status": relation["status"], "relationship": relation}


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
            candidates = claim.get("candidate_actor_ids")
            if isinstance(candidates, list):
                candidate_ids.update(x for x in candidates if isinstance(x, str))
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
        if claim.get("epistemic_status") in {"DIRECT", "INFERRED"}:
            dependencies = claim.get("required_relationship_ids", [])
            if not isinstance(dependencies, list) or any(
                not isinstance(value, str) or not value.strip() for value in dependencies
            ) or len(dependencies) != len(set(dependencies)):
                return {"status": "INVALID_INPUT", "participants": [], "errors": [
                    f"claim {claim.get('claim_id')}: invalid required_relationship_ids"
                ]}
            relationship_inferred = False
            relationship_blocked = False
            for relationship_id in dependencies:
                relation_result = resolve_relationship_id_as_of(
                    actor_registry, relationship_id, knowledge_cutoff_utc, trade["event_time_utc"]
                )
                relation = relation_result.get("relationship")
                if relation_result["status"] in {"UNKNOWN", "DISPUTED", "INVALID_INPUT", "INVALID_REGISTRY"}:
                    relationship_blocked = True
                    break
                if relation is None or claim.get("actor_id") not in {
                    relation.get("subject_actor_id"), relation.get("object_actor_id")
                }:
                    return {"status": "INVALID_INPUT", "participants": [], "errors": [
                        f"claim {claim.get('claim_id')}: required relationship does not include attributed actor"
                    ]}
                if relation_result["status"] != "VERIFIED":
                    relationship_inferred = True
            if relationship_blocked:
                claim["actor_id"] = None
                claim["candidate_actor_ids"] = []
                claim["epistemic_status"] = "UNKNOWN"
                claim["attribution_method"] = "NONE"
                claim["source_observation_ids"] = []
                claim["supporting_evidence"] = []
                claim["counter_evidence"] = []
            elif relationship_inferred and claim["epistemic_status"] == "DIRECT":
                claim["epistemic_status"] = "INFERRED"
                claim["attribution_method"] = "OTHER"
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
