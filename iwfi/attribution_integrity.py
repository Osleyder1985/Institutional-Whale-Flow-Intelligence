"""Validation helpers for temporal attribution-claim invariants."""
from datetime import datetime
import re


def _parse_utc_timestamp(value):
    if not isinstance(value, str) or re.fullmatch(r"[0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{2}:[0-9]{2}:[0-9]{2}Z", value) is None:
        return None
    try:
        parsed = datetime.fromisoformat(value[:-1] + "+00:00")
    except ValueError:
        return None
    if parsed.utcoffset() is None:
        return None
    return parsed


def validate_claim_validity_interval(claim):
    """Return errors when validity bounds are malformed or chronologically reversed.

    Null bounds remain unknown; they are not interpreted as infinite timestamps.
    """
    errors = []
    start_value = claim.get("valid_from_utc")
    end_value = claim.get("valid_to_utc")
    start = _parse_utc_timestamp(start_value) if start_value is not None else None
    end = _parse_utc_timestamp(end_value) if end_value is not None else None

    if start_value is not None and start is None:
        errors.append("valid_from_utc must be a valid UTC timestamp ending in Z")
    if end_value is not None and end is None:
        errors.append("valid_to_utc must be a valid UTC timestamp ending in Z")
    if start is not None and end is not None and start > end:
        errors.append("valid_from_utc must not be later than valid_to_utc")
    return errors


def validate_claim_collection(claims, known_claim_ids=()):
    """Validate collection-level identity and supersession integrity.

    Pass a complete claim history to resolve every supersession reference.
    For a partial batch, known_claim_ids may contain IDs resolved in the
    persistent history but not included in this batch. Cycles are checked
    within the supplied batch.
    """
    errors = []
    known_ids = set(known_claim_ids)
    claims_by_id = {}

    for index, claim in enumerate(claims):
        if not isinstance(claim, dict):
            errors.append(f"claims[{index}] must be an object")
            continue
        claim_id = claim.get("claim_id")
        if not isinstance(claim_id, str) or not claim_id:
            continue
        if claim_id in claims_by_id:
            errors.append(f"duplicate claim_id: {claim_id}")
        else:
            claims_by_id[claim_id] = claim

    graph = {}
    for claim_id, claim in claims_by_id.items():
        predecessor_id = claim.get("supersedes_claim_id")
        if predecessor_id is None or not isinstance(predecessor_id, str):
            continue
        if predecessor_id == claim_id:
            errors.append(f"claim {claim_id} cannot supersede itself")
            continue
        if predecessor_id not in claims_by_id and predecessor_id not in known_ids:
            errors.append(
                f"claim {claim_id} references unresolved supersedes_claim_id: {predecessor_id}"
            )
            continue
        if predecessor_id in claims_by_id:
            graph[claim_id] = predecessor_id
            previous = claims_by_id[predecessor_id]
            current_recorded = _parse_utc_timestamp(claim.get("recorded_at_utc"))
            previous_recorded = _parse_utc_timestamp(previous.get("recorded_at_utc"))
            if (
                current_recorded is not None
                and previous_recorded is not None
                and current_recorded < previous_recorded
            ):
                errors.append(
                    f"claim {claim_id} is recorded before superseded claim {predecessor_id}"
                )

    visited = set()
    active = set()

    def visit(claim_id):
        if claim_id in active:
            errors.append(f"supersession cycle detected at claim_id: {claim_id}")
            return
        if claim_id in visited:
            return
        active.add(claim_id)
        predecessor_id = graph.get(claim_id)
        if predecessor_id is not None:
            visit(predecessor_id)
        active.remove(claim_id)
        visited.add(claim_id)

    for claim_id in graph:
        visit(claim_id)

    return errors
