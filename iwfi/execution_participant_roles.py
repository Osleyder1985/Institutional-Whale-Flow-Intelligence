"""Multi-role, execution-specific participant claims with point-in-time resolution."""
from datetime import datetime
import re

_UTC = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z$")
_ROLES = {
    "BUYER", "SELLER", "BROKER", "EXECUTING_VENUE", "CUSTODIAN",
    "CLEARING_PARTICIPANT", "FUND", "ASSET_MANAGER",
    "BENEFICIAL_OWNER", "OTHER", "UNKNOWN",
}
_SIDES = {"BUY", "SELL", "NOT_APPLICABLE", "UNKNOWN"}
_STATUSES = {"DIRECT", "INFERRED", "UNKNOWN", "DISPUTED"}
_DIRECT_EVIDENCE = {
    "OFFICIAL_NAMED_EXECUTION_DISCLOSURE",
    "VENUE_PARTICIPANT_DISCLOSURE",
    "AUTHORIZED_ACCOUNT_LINK",
}


def _time(value):
    if not isinstance(value, str) or not _UTC.fullmatch(value):
        return None
    try:
        return datetime.strptime(value, "%Y-%m-%dT%H:%M:%SZ")
    except ValueError:
        return None


def _nonempty(value):
    return isinstance(value, str) and bool(value.strip())


def _valid_role_side(role, side):
    if role == "BUYER":
        return side == "BUY"
    if role == "SELLER":
        return side == "SELL"
    if role in _ROLES - {"BUYER", "SELLER", "UNKNOWN"}:
        return side in {"NOT_APPLICABLE", "UNKNOWN"}
    return role == "UNKNOWN" and side == "UNKNOWN"


def validate_execution_participant_roles(registry, trades, actor_ids, observation_ids):
    """Return deterministic errors; compatible claims for different roles may coexist."""
    if not isinstance(registry, dict) or registry.get("contract_version") != "1.1.0":
        return ["unsupported execution participant role registry"]
    claims = registry.get("claims")
    if not isinstance(claims, list):
        return ["claims must be a list"]
    if not isinstance(trades, list):
        return ["trades must be a list"]
    if not isinstance(actor_ids, (list, tuple, set)) or any(not _nonempty(x) for x in actor_ids):
        return ["actor_ids must be a collection of non-empty strings"]
    if not isinstance(observation_ids, (list, tuple, set)) or any(not _nonempty(x) for x in observation_ids):
        return ["observation_ids must be a collection of non-empty strings"]

    actors, observations = set(actor_ids), set(observation_ids)
    trades_by_id, errors = {}, []
    for index, trade in enumerate(trades):
        if not isinstance(trade, dict):
            errors.append(f"trades[{index}] must be an object")
            continue
        trade_id = trade.get("trade_id")
        if not _nonempty(trade_id):
            errors.append(f"trades[{index}] has invalid trade_id")
            continue
        if trade_id in trades_by_id:
            errors.append(f"duplicate trade_id: {trade_id}")
            continue
        trades_by_id[trade_id] = trade
        if _time(trade.get("event_time_utc")) is None:
            errors.append(f"trade {trade_id}: invalid event_time_utc")

    seen_claims = set()
    for index, claim in enumerate(claims):
        if not isinstance(claim, dict):
            errors.append(f"claims[{index}] must be an object")
            continue
        claim_id = claim.get("claim_id")
        if not _nonempty(claim_id):
            errors.append(f"claims[{index}] has invalid claim_id")
        elif claim_id in seen_claims:
            errors.append(f"duplicate claim_id: {claim_id}")
        seen_claims.add(claim_id)

        trade_id = claim.get("trade_id")
        trade = trades_by_id.get(trade_id)
        if trade is None:
            errors.append(f"trade not found: {trade_id}")
            continue

        role, side, status = claim.get("participant_role"), claim.get("participant_side"), claim.get("epistemic_status")
        if role not in _ROLES:
            errors.append(f"claim {claim_id}: invalid participant_role")
        if side not in _SIDES:
            errors.append(f"claim {claim_id}: invalid participant_side")
        if role in _ROLES and side in _SIDES and not _valid_role_side(role, side):
            errors.append(f"claim {claim_id}: participant_side is incompatible with participant_role")
        if status not in _STATUSES:
            errors.append(f"claim {claim_id}: invalid epistemic_status")

        actor_id = claim.get("actor_id")
        candidates = claim.get("candidate_actor_ids")
        if not isinstance(candidates, list) or any(not _nonempty(x) for x in candidates) or len(candidates) != len(set(candidates)):
            errors.append(f"claim {claim_id}: invalid candidate_actor_ids")
            candidates = []
        if status in {"DIRECT", "INFERRED"}:
            if not _nonempty(actor_id) or actor_id not in actors:
                errors.append(f"claim {claim_id}: participant actor not found")
            if candidates:
                errors.append(f"claim {claim_id}: named attribution cannot contain candidate_actor_ids")
        elif status == "UNKNOWN":
            if actor_id is not None or candidates or claim.get("attribution_method") != "NONE":
                errors.append(f"claim {claim_id}: UNKNOWN must not select an actor or candidates and must use NONE")
        elif status == "DISPUTED":
            if actor_id is not None or len(candidates) < 2 or not set(candidates).issubset(actors):
                errors.append(f"claim {claim_id}: DISPUTED requires at least two known candidates and no selected actor")
            if claim.get("attribution_method") != "CONFLICT_REVIEW":
                errors.append(f"claim {claim_id}: DISPUTED must use CONFLICT_REVIEW")

        known = _time(claim.get("known_at_utc"))
        recorded = _time(claim.get("recorded_at_utc"))
        if known is None:
            errors.append(f"claim {claim_id}: invalid known_at_utc")
        if recorded is None:
            errors.append(f"claim {claim_id}: invalid recorded_at_utc")
        if known and recorded and recorded < known:
            errors.append(f"claim {claim_id}: recorded_at_utc precedes known_at_utc")

        start_value, end_value = claim.get("valid_from_utc"), claim.get("valid_to_utc")
        start = _time(start_value) if start_value is not None else None
        end = _time(end_value) if end_value is not None else None
        if start_value is not None and start is None:
            errors.append(f"claim {claim_id}: invalid valid_from_utc")
        if end_value is not None and end is None:
            errors.append(f"claim {claim_id}: invalid valid_to_utc")
        if start and end and end < start:
            errors.append(f"claim {claim_id}: validity interval ends before it starts")
        if status in {"DIRECT", "INFERRED"}:
            event_time = _time(trade.get("event_time_utc"))
            if start is None or end is None or event_time is None or not (start <= event_time <= end):
                errors.append(f"claim {claim_id}: validity interval does not cover trade event time")

        refs = claim.get("source_observation_ids")
        if not isinstance(refs, list) or any(not _nonempty(x) for x in refs) or len(refs) != len(set(refs)):
            errors.append(f"claim {claim_id}: invalid source_observation_ids")
            refs = []
        for ref in refs:
            if ref not in observations:
                errors.append(f"claim {claim_id}: source observation not found: {ref}")

        for evidence_field in ("supporting_evidence", "counter_evidence"):
            evidence = claim.get(evidence_field)
            if not isinstance(evidence, list):
                errors.append(f"claim {claim_id}: {evidence_field} must be a list")
                continue
            for evidence_index, item in enumerate(evidence):
                if not isinstance(item, dict):
                    errors.append(f"claim {claim_id}: {evidence_field}[{evidence_index}] must be an object")
                    continue
                observation_id = item.get("observation_id")
                if observation_id is not None:
                    if not _nonempty(observation_id) or observation_id not in observations:
                        errors.append(f"claim {claim_id}: evidence observation not found: {observation_id}")
                    elif observation_id not in refs:
                        errors.append(f"claim {claim_id}: evidence observation is absent from source_observation_ids")
        supporting = claim.get("supporting_evidence", [])
        if status in {"DIRECT", "INFERRED"} and (not refs or not supporting):
            errors.append(f"claim {claim_id}: attributed participant requires source observations and supporting evidence")
        if status == "DIRECT" and not any(
            isinstance(item, dict) and item.get("evidence_type") in _DIRECT_EVIDENCE
            for item in supporting
        ):
            errors.append(f"claim {claim_id}: DIRECT lacks participant-specific evidence")
        if status == "DISPUTED" and not claim.get("counter_evidence"):
            errors.append(f"claim {claim_id}: DISPUTED requires counter_evidence")

    return sorted(set(errors))


def resolve_execution_participants(registry, trade, as_of_utc):
    """Resolve each role independently; malformed relevant claims cause explicit abstention."""
    as_of = _time(as_of_utc)
    event_time = _time(trade.get("event_time_utc")) if isinstance(trade, dict) else None
    trade_id = trade.get("trade_id") if isinstance(trade, dict) else None
    if as_of is None or event_time is None or not _nonempty(trade_id):
        return {"status": "INVALID_INPUT", "participants": [], "errors": ["invalid trade or as_of timestamp"]}
    if not isinstance(registry, dict) or not isinstance(registry.get("claims"), list):
        return {"status": "INVALID_INPUT", "participants": [], "errors": ["invalid claim registry"]}

    active = []
    for claim in registry["claims"]:
        if not isinstance(claim, dict):
            return {"status": "INVALID_INPUT", "participants": [], "errors": ["malformed claim object"]}
        if claim.get("trade_id") != trade_id:
            continue
        known = _time(claim.get("known_at_utc"))
        start_value, end_value = claim.get("valid_from_utc"), claim.get("valid_to_utc")
        start = _time(start_value) if start_value is not None else None
        end = _time(end_value) if end_value is not None else None
        if known is None or (start_value is not None and start is None) or (end_value is not None and end is None):
            return {"status": "INVALID_INPUT", "participants": [], "errors": ["malformed temporal claim"]}
        if known > as_of or (start is not None and event_time < start) or (end is not None and event_time > end):
            continue
        role, side, status = claim.get("participant_role"), claim.get("participant_side"), claim.get("epistemic_status")
        if role not in _ROLES or side not in _SIDES or status not in _STATUSES or not _valid_role_side(role, side):
            return {"status": "INVALID_INPUT", "participants": [], "errors": ["malformed role/side/status claim"]}
        active.append(claim)

    by_role = {}
    for claim in active:
        by_role.setdefault(claim["participant_role"], []).append(claim)

    participants = []
    for role in sorted(by_role):
        claims = by_role[role]
        if any(c["epistemic_status"] == "DISPUTED" for c in claims):
            status = "DISPUTED"
        else:
            named = [c for c in claims if c["epistemic_status"] in {"DIRECT", "INFERRED"}]
            actors = {c.get("actor_id") for c in named}
            sides = {c.get("participant_side") for c in claims}
            if len(actors) > 1 or len(sides) > 1:
                status = "DISPUTED"
            elif not named:
                status = "UNKNOWN"
            elif any(c["epistemic_status"] == "DIRECT" for c in named):
                status = "DIRECT"
            else:
                status = "INFERRED"
        if status in {"DISPUTED", "UNKNOWN"}:
            actor_id = None
        else:
            actor_id = next(c.get("actor_id") for c in claims if c["epistemic_status"] in {"DIRECT", "INFERRED"})
        sides = {c.get("participant_side") for c in claims}
        side = next(iter(sides)) if len(sides) == 1 else "UNKNOWN"
        participants.append({
            "participant_role": role,
            "status": status,
            "actor_id": actor_id,
            "participant_side": side,
            "claim_ids": sorted(c["claim_id"] for c in claims if _nonempty(c.get("claim_id"))),
            "candidate_actor_ids": sorted({x for c in claims for x in c.get("candidate_actor_ids", [])}),
        })
    return {"status": "RESOLVED", "participants": participants, "errors": []}
