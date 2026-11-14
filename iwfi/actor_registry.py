"""Deterministic validation and point-in-time lookup for the IWFI Actor Registry."""
from datetime import datetime
import re

_UTC = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z$")

def _time(value):
    if not isinstance(value, str) or not _UTC.fullmatch(value):
        return None
    try:
        return datetime.strptime(value, "%Y-%m-%dT%H:%M:%SZ")
    except ValueError:
        return None

def _interval_errors(item, prefix, errors):
    start = item.get("valid_from_utc")
    end = item.get("valid_to_utc")
    start_dt = _time(start) if start is not None else None
    end_dt = _time(end) if end is not None else None
    if start is not None and start_dt is None:
        errors.append(f"{prefix}: invalid valid_from_utc")
    if end is not None and end_dt is None:
        errors.append(f"{prefix}: invalid valid_to_utc")
    if start_dt and end_dt and end_dt < start_dt:
        errors.append(f"{prefix}: validity interval ends before it starts")

def validate_actor_registry(registry):
    """Return deterministic integrity errors; ambiguous aliases remain queryable, never auto-resolved."""
    if not isinstance(registry, dict):
        return ["registry must be an object"]
    actors = registry.get("actors")
    if not isinstance(actors, list):
        return ["registry.actors must be a list"]
    errors = []
    ids = {}
    for index, actor in enumerate(actors):
        if not isinstance(actor, dict):
            errors.append(f"actors[{index}] must be an object")
            continue
        actor_id = actor.get("actor_id")
        if not isinstance(actor_id, str) or not actor_id.strip():
            errors.append(f"actors[{index}] has invalid actor_id")
            continue
        ids.setdefault(actor_id, []).append(index)
        for field in ("recorded_at_utc", "known_at_utc"):
            if _time(actor.get(field)) is None:
                errors.append(f"actor {actor_id}: invalid {field}")
        _interval_errors(actor, f"actor {actor_id}", errors)
        for alias_index, alias in enumerate(actor.get("aliases", [])):
            if not isinstance(alias, dict):
                errors.append(f"actor {actor_id}: aliases[{alias_index}] must be an object")
                continue
            if _time(alias.get("known_at_utc")) is None:
                errors.append(f"actor {actor_id}: alias {alias_index} has invalid known_at_utc")
            _interval_errors(alias, f"actor {actor_id} alias {alias_index}", errors)
    for actor_id, positions in ids.items():
        if len(positions) > 1:
            errors.append(f"duplicate actor_id: {actor_id}")
    relationships = registry.get("relationships", [])
    if not isinstance(relationships, list):
        errors.append("registry.relationships must be a list")
        relationships = []
    seen_relationships = {}
    for index, relation in enumerate(relationships):
        if not isinstance(relation, dict):
            errors.append(f"relationships[{index}] must be an object")
            continue
        rid = relation.get("relationship_id")
        if not isinstance(rid, str) or not rid.strip():
            errors.append(f"relationships[{index}] has invalid relationship_id")
        subject, target = relation.get("subject_actor_id"), relation.get("object_actor_id")
        if subject not in ids:
            errors.append(f"relationship {rid}: subject actor not found")
        if target not in ids:
            errors.append(f"relationship {rid}: object actor not found")
        if _time(relation.get("known_at_utc")) is None:
            errors.append(f"relationship {rid}: invalid known_at_utc")
        _interval_errors(relation, f"relationship {rid}", errors)
        key = (subject, target, relation.get("relationship_type"))
        seen_relationships.setdefault(key, set()).add(relation.get("status"))
    for key, statuses in seen_relationships.items():
        if len(statuses) > 1:
            errors.append(f"contradictory relationship claims: {key[0]} -> {key[1]} ({key[2]})")
    return sorted(set(errors))

def resolve_actor_alias(registry, alias_value, as_of_utc, alias_type=None, scope=None):
    """Resolve only records known and valid at as_of; return UNKNOWN/UNIQUE/AMBIGUOUS."""
    instant = _time(as_of_utc)
    if instant is None:
        return {"status": "INVALID_AS_OF", "actor_ids": []}
    if not isinstance(registry, dict) or not isinstance(registry.get("actors"), list):
        return {"status": "INVALID_REGISTRY", "actor_ids": []}
    matches = set()
    for actor in registry["actors"]:
        if not isinstance(actor, dict) or _time(actor.get("known_at_utc")) is None:
            continue
        if _time(actor["known_at_utc"]) > instant:
            continue
        actor_start = _time(actor.get("valid_from_utc")) if actor.get("valid_from_utc") else None
        actor_end = _time(actor.get("valid_to_utc")) if actor.get("valid_to_utc") else None
        if actor_start and instant < actor_start or actor_end and instant > actor_end:
            continue
        for item in actor.get("aliases", []):
            if not isinstance(item, dict) or item.get("value", "").casefold() != alias_value.casefold():
                continue
            if alias_type and item.get("alias_type") != alias_type:
                continue
            if scope and item.get("scope") != scope:
                continue
            known = _time(item.get("known_at_utc"))
            start = _time(item.get("valid_from_utc")) if item.get("valid_from_utc") else None
            end = _time(item.get("valid_to_utc")) if item.get("valid_to_utc") else None
            if known is None or known > instant or start and instant < start or end and instant > end:
                continue
            matches.add(actor["actor_id"])
    ordered = sorted(matches)
    if not ordered:
        return {"status": "UNKNOWN", "actor_ids": []}
    if len(ordered) > 1:
        return {"status": "AMBIGUOUS", "actor_ids": ordered}
    return {"status": "UNIQUE", "actor_ids": ordered}

def resolve_relationship(registry, subject_actor_id, object_actor_id, relationship_type, as_of_utc):
    """Do not infer transitive edges; contradictory direct claims resolve as DISPUTED."""
    instant = _time(as_of_utc)
    if instant is None or not isinstance(registry, dict):
        return {"status": "UNKNOWN", "evidence": []}
    found = []
    for item in registry.get("relationships", []):
        if not isinstance(item, dict):
            continue
        if (item.get("subject_actor_id"), item.get("object_actor_id"), item.get("relationship_type")) != (subject_actor_id, object_actor_id, relationship_type):
            continue
        known = _time(item.get("known_at_utc"))
        start = _time(item.get("valid_from_utc")) if item.get("valid_from_utc") else None
        end = _time(item.get("valid_to_utc")) if item.get("valid_to_utc") else None
        if known and known <= instant and (not start or start <= instant) and (not end or instant <= end):
            found.append(item)
    statuses = {item.get("status") for item in found}
    if not found:
        status = "UNKNOWN"
    elif len(statuses) > 1 or "DISPUTED" in statuses:
        status = "DISPUTED"
    else:
        status = next(iter(statuses))
    return {"status": status, "evidence": sorted({ref for item in found for ref in item.get("evidence_refs", [])})}
