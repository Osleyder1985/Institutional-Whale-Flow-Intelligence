"""Execution-specific participant attribution with point-in-time resolution."""
from datetime import datetime
import re

_UTC = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z$")
_DIRECT_EVIDENCE = {
    "OFFICIAL_NAMED_EXECUTION_DISCLOSURE",
    "VENUE_PARTICIPANT_DISCLOSURE",
    "AUTHORIZED_ACCOUNT_LINK",
}
_STATUSES = {"DIRECT", "INFERRED", "UNKNOWN", "DISPUTED"}

def _time(value):
    if not isinstance(value, str) or not _UTC.fullmatch(value):
        return None
    try:
        return datetime.strptime(value, "%Y-%m-%dT%H:%M:%SZ")
    except ValueError:
        return None

def _string_set(values):
    if not isinstance(values, (list, tuple, set)):
        return None
    if any(not isinstance(value, str) or not value.strip() for value in values):
        return None
    return set(values)

def validate_execution_attributions(registry, executions, actor_ids, observation_ids):
    """Validate cross-contract references and evidence without selecting a disputed participant."""
    if not isinstance(registry, dict) or registry.get("contract_version") != "1.0.0":
        return ["unsupported execution attribution registry"]
    claims = registry.get("claims")
    if not isinstance(claims, list):
        return ["claims must be a list"]
    if not isinstance(executions, list):
        return ["executions must be a list"]
    actors = _string_set(actor_ids)
    observations = _string_set(observation_ids)
    if actors is None:
        return ["actor_ids must be a collection of non-empty strings"]
    if observations is None:
        return ["observation_ids must be a collection of non-empty strings"]
    executions_by_id = {}
    errors = []
    for index, item in enumerate(executions):
        if not isinstance(item, dict):
            errors.append(f"executions[{index}] must be an object")
            continue
        execution_id = item.get("execution_id")
        if not isinstance(execution_id, str) or not execution_id.strip():
            errors.append(f"executions[{index}] has invalid execution_id")
        elif execution_id in executions_by_id:
            errors.append(f"duplicate execution_id: {execution_id}")
        else:
            executions_by_id[execution_id] = item
    seen = set()
    for index, claim in enumerate(claims):
        if not isinstance(claim, dict):
            errors.append(f"claims[{index}] must be an object")
            continue
        attribution_id = claim.get("attribution_id")
        if not isinstance(attribution_id, str) or not attribution_id.strip():
            errors.append(f"claims[{index}] has invalid attribution_id")
        elif attribution_id in seen:
            errors.append(f"duplicate attribution_id: {attribution_id}")
        seen.add(attribution_id)
        execution_id = claim.get("execution_id")
        execution = executions_by_id.get(execution_id)
        if execution is None:
            errors.append(f"execution not found: {execution_id}")
            continue
        status = claim.get("attribution_status")
        if status not in _STATUSES:
            errors.append(f"invalid attribution_status: {status}")
        actor_id = claim.get("actor_id")
        candidates = claim.get("candidate_actor_ids", [])
        side = claim.get("participant_side")
        if status in {"DIRECT", "INFERRED"}:
            if not isinstance(actor_id, str) or actor_id not in actors:
                errors.append(f"participant actor not found: {actor_id}")
        elif status == "UNKNOWN":
            if actor_id is not None or candidates or side != "UNKNOWN":
                errors.append("UNKNOWN attribution must not name an actor, candidates or participant side")
        elif status == "DISPUTED":
            candidate_set = _string_set(candidates)
            if actor_id is not None or side != "UNKNOWN" or candidate_set is None or len(candidate_set) < 2:
                errors.append("DISPUTED attribution requires at least two candidates and no selected actor or side")
            elif not candidate_set.issubset(actors):
                for candidate in sorted(candidate_set - actors):
                    errors.append(f"disputed candidate actor not found: {candidate}")
        known = _time(claim.get("known_at_utc"))
        recorded = _time(claim.get("recorded_at_utc"))
        if known is None:
            errors.append(f"claim {attribution_id}: invalid known_at_utc")
        if recorded is None:
            errors.append(f"claim {attribution_id}: invalid recorded_at_utc")
        if known and recorded and recorded < known:
            errors.append(f"claim {attribution_id}: recorded_at_utc precedes known_at_utc")
        start = _time(claim.get("valid_from_utc")) if claim.get("valid_from_utc") is not None else None
        end = _time(claim.get("valid_to_utc")) if claim.get("valid_to_utc") is not None else None
        if claim.get("valid_from_utc") is not None and start is None:
            errors.append(f"claim {attribution_id}: invalid valid_from_utc")
        if claim.get("valid_to_utc") is not None and end is None:
            errors.append(f"claim {attribution_id}: invalid valid_to_utc")
        if start and end and end < start:
            errors.append(f"claim {attribution_id}: validity interval ends before it starts")
        event_time = _time(execution.get("event_time_utc"))
        if status in {"DIRECT", "INFERRED"}:
            if start is None or end is None or event_time is None or not (start <= event_time <= end):
                errors.append(f"claim {attribution_id}: validity interval does not cover execution event time")
        refs = claim.get("source_observation_ids", [])
        ref_set = _string_set(refs)
        if ref_set is None:
            errors.append(f"claim {attribution_id}: invalid source_observation_ids")
            ref_set = set()
        evidence = claim.get("supporting_evidence", [])
        if not isinstance(evidence, list):
            errors.append(f"claim {attribution_id}: supporting_evidence must be a list")
            evidence = []
        evidence_observation_ids = set()
        direct_types = set()
        for evidence_index, item in enumerate(evidence):
            if not isinstance(item, dict):
                errors.append(f"claim {attribution_id}: supporting_evidence[{evidence_index}] must be an object")
                continue
            direct_types.add(item.get("evidence_type"))
            observation_id = item.get("observation_id")
            if observation_id is not None:
                if not isinstance(observation_id, str) or not observation_id.strip():
                    errors.append(f"claim {attribution_id}: invalid evidence observation_id")
                else:
                    evidence_observation_ids.add(observation_id)
                    if observation_id not in observations:
                        errors.append(f"claim {attribution_id}: evidence observation not found: {observation_id}")
        if not evidence_observation_ids.issubset(ref_set):
            errors.append(f"claim {attribution_id}: evidence observation IDs must be listed in source_observation_ids")
        if status == "DIRECT" and not (direct_types & _DIRECT_EVIDENCE):
            errors.append(f"claim {attribution_id}: DIRECT attribution lacks participant-specific evidence")
        if status in {"DIRECT", "INFERRED"} and (not ref_set or not evidence):
            errors.append(f"claim {attribution_id}: attributed participant requires source observations and supporting evidence")
        if status in {"DIRECT", "INFERRED"}:
            if attribution_id not in execution.get("attribution_claim_ids", []):
                errors.append(f"execution {execution_id}: attribution claim reference missing: {attribution_id}")
            if execution.get("participant_actor_id") != actor_id:
                errors.append(f"execution {execution_id}: participant actor does not match claim {attribution_id}")
            if execution.get("participant_side") != side:
                errors.append(f"execution {execution_id}: participant side does not match claim {attribution_id}")
            if execution.get("participant_attribution_status") != status:
                errors.append(f"execution {execution_id}: attribution status does not match claim {attribution_id}")
    return sorted(set(errors))

def resolve_execution_participant(registry, execution, as_of_utc):
    """Resolve only claims known by as_of and valid at execution time; conflicts abstain."""
    as_of = _time(as_of_utc)
    event_time = _time(execution.get("event_time_utc")) if isinstance(execution, dict) else None
    if as_of is None or event_time is None or not isinstance(registry, dict) or not isinstance(registry.get("claims"), list):
        return {"status": "UNKNOWN", "actor_id": None, "participant_side": "UNKNOWN", "attribution_ids": []}
    active = []
    for claim in registry["claims"]:
        if not isinstance(claim, dict) or claim.get("execution_id") != execution.get("execution_id"):
            continue
        known = _time(claim.get("known_at_utc"))
        start = _time(claim.get("valid_from_utc")) if claim.get("valid_from_utc") else None
        end = _time(claim.get("valid_to_utc")) if claim.get("valid_to_utc") else None
        if known is None or known > as_of:
            continue
        if start and event_time < start or end and event_time > end:
            continue
        active.append(claim)
    if not active:
        return {"status": "UNKNOWN", "actor_id": None, "participant_side": "UNKNOWN", "attribution_ids": []}
    if any(c.get("attribution_status") == "DISPUTED" for c in active):
        status = "DISPUTED"
    else:
        named = [c for c in active if c.get("attribution_status") in {"DIRECT", "INFERRED"}]
        actors = {c.get("actor_id") for c in named}
        sides = {c.get("participant_side") for c in named}
        if len(actors) > 1 or len(sides) > 1:
            status = "DISPUTED"
        elif not named:
            status = "UNKNOWN"
        elif any(c.get("attribution_status") == "DIRECT" for c in named):
            status = "DIRECT"
        else:
            status = "INFERRED"
    if status in {"UNKNOWN", "DISPUTED"}:
        actor_id, side = None, "UNKNOWN"
    else:
        named = [c for c in active if c.get("attribution_status") in {"DIRECT", "INFERRED"}]
        actor_id, side = named[0].get("actor_id"), named[0].get("participant_side")
    return {
        "status": status,
        "actor_id": actor_id,
        "participant_side": side,
        "attribution_ids": sorted(c.get("attribution_id") for c in active if c.get("attribution_id")),
    }
