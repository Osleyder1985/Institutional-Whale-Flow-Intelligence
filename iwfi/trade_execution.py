"""Integrity checks for individual, evidence-backed trade executions."""
from datetime import datetime
import re
from decimal import Decimal, InvalidOperation

_UTC = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z$")
_DECIMAL = re.compile(r"^(0|[1-9][0-9]*)(\.[0-9]+)?$")
_ALLOWED_EVIDENCE = {"VENUE_EXECUTION_RECORD", "OFFICIAL_EXECUTION_DISCLOSURE"}

def _time(value):
    if not isinstance(value, str) or not _UTC.fullmatch(value):
        return None
    try:
        return datetime.strptime(value, "%Y-%m-%dT%H:%M:%SZ")
    except ValueError:
        return None

def _decimal(value):
    if not isinstance(value, str) or not _DECIMAL.fullmatch(value):
        return None
    try:
        return Decimal(value)
    except InvalidOperation:
        return None

def validate_trade_execution(execution, source_evidence_ids=None, actor_ids=None):
    """Return integrity errors; this function never promotes evidence into a trade."""
    if not isinstance(execution, dict):
        return ["execution must be an object"]
    errors = []
    if execution.get("event_type") != "TRADE_EXECUTION":
        errors.append("event_type must be TRADE_EXECUTION")
    if execution.get("aggregation_level") != "INDIVIDUAL_EXECUTION":
        errors.append("only INDIVIDUAL_EXECUTION is admissible")
    if execution.get("execution_status") not in {"EXECUTED", "PARTIALLY_EXECUTED", "CORRECTED", "CANCELLED", "BUSTED", "UNKNOWN"}:
        errors.append("unknown execution_status")
    refs = execution.get("source_observation_ids")
    if not isinstance(refs, list) or not refs or any(not isinstance(x, str) or not x for x in refs):
        errors.append("source_observation_ids must be a non-empty list of IDs")
        refs = []
    if len(refs) != len(set(refs)):
        errors.append("duplicate source_observation_ids")
    available = set(source_evidence_ids or [])
    for ref in refs:
        if ref not in available:
            errors.append(f"source execution evidence not found: {ref}")
    evidence = execution.get("source_evidence")
    if not isinstance(evidence, list) or not evidence:
        errors.append("source_evidence must be a non-empty list")
        evidence = []
    evidence_ids = set()
    for index, item in enumerate(evidence):
        if not isinstance(item, dict):
            errors.append(f"source_evidence[{index}] must be an object")
            continue
        evidence_id = item.get("evidence_id")
        if evidence_id in evidence_ids:
            errors.append(f"duplicate evidence_id: {evidence_id}")
        evidence_ids.add(evidence_id)
        if item.get("evidence_type") not in _ALLOWED_EVIDENCE:
            errors.append(f"non-execution evidence is inadmissible: {item.get('evidence_type')}")
        if item.get("granularity") != "INDIVIDUAL_EXECUTION":
            errors.append("source evidence must describe an individual execution")
    if set(refs) != evidence_ids:
        errors.append("source_observation_ids must match source_evidence IDs")
    times = [execution.get(name) for name in ("event_time_utc", "published_at_utc", "available_at_utc", "ingested_at_utc", "computed_at_utc")]
    parsed = [_time(value) for value in times]
    names = ("event_time_utc", "published_at_utc", "available_at_utc", "ingested_at_utc", "computed_at_utc")
    for name, value in zip(names, parsed):
        if value is None:
            errors.append(f"invalid {name}")
    if all(parsed) and parsed != sorted(parsed):
        errors.append("execution timestamps are not chronological")
    for field in ("base_quantity", "quote_quantity", "price"):
        value = execution.get(field)
        if value is not None and _decimal(value) is None:
            errors.append(f"invalid canonical decimal: {field}")
    fee = execution.get("fee_amount")
    if fee is not None and _decimal(fee) is None:
        errors.append("invalid canonical decimal: fee_amount")
    status = execution.get("participant_attribution_status")
    if status not in {"DIRECT", "INFERRED", "UNKNOWN", "DISPUTED"}:
        errors.append("invalid participant_attribution_status for an individual execution")
    actor_id = execution.get("participant_actor_id")
    claims = execution.get("attribution_claim_ids", [])
    side = execution.get("participant_side")
    if status == "UNKNOWN":
        if actor_id is not None or side != "UNKNOWN" or claims:
            errors.append("UNKNOWN participant attribution must not name an actor, side or claim")
    elif status == "DIRECT":
        if not isinstance(actor_id, str) or not actor_id:
            errors.append("DIRECT participant attribution requires participant_actor_id")
        if not isinstance(claims, list) or not claims:
            errors.append("DIRECT participant attribution requires attribution_claim_ids")
    elif status == "INFERRED":
        if actor_id is None:
            errors.append("INFERRED participant attribution requires an explicit actor candidate")
    elif status == "DISPUTED" and side != "UNKNOWN":
        errors.append("DISPUTED participant attribution must not choose participant_side")
    if actor_id is not None and actor_ids is not None and actor_id not in set(actor_ids):
        errors.append(f"participant actor not found: {actor_id}")
    if execution.get("aggressor_side") not in {"BUY", "SELL", "UNKNOWN"}:
        errors.append("invalid aggressor_side")
    if side not in {"BUY", "SELL", "UNKNOWN"}:
        errors.append("invalid participant_side")
    return sorted(set(errors))
