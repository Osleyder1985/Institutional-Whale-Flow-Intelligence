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
    within the supplied batch. Duplicate claim IDs are treated as ambiguous
    and are not used to resolve supersession edges.
    """
    errors = []

    if isinstance(known_claim_ids, (str, bytes)):
        errors.append("known_claim_ids must be an iterable of non-empty claim IDs")
        known_values = []
    else:
        try:
            known_values = list(known_claim_ids)
        except TypeError:
            errors.append("known_claim_ids must be an iterable of non-empty claim IDs")
            known_values = []
    invalid_known_ids = [
        value for value in known_values
        if not isinstance(value, str) or not value
    ]
    if invalid_known_ids:
        errors.append("known_claim_ids must contain only non-empty strings")
    known_ids = {
        value for value in known_values
        if isinstance(value, str) and value
    }

    if isinstance(claims, (str, bytes)):
        return sorted(set(errors + ["claims must be an iterable of claim objects"]))
    try:
        claim_items = list(claims)
    except TypeError:
        return sorted(set(errors + ["claims must be an iterable of claim objects"]))

    claims_by_id = {}
    id_counts = {}
    for index, claim in enumerate(claim_items):
        if not isinstance(claim, dict):
            errors.append(f"claims[{index}] must be an object")
            continue
        claim_id = claim.get("claim_id")
        if not isinstance(claim_id, str) or not claim_id:
            errors.append(f"claims[{index}] has an invalid claim_id")
            continue
        id_counts[claim_id] = id_counts.get(claim_id, 0) + 1
        if claim_id not in claims_by_id:
            claims_by_id[claim_id] = claim

    duplicate_ids = {
        claim_id for claim_id, count in id_counts.items()
        if count > 1
    }
    for claim_id in sorted(duplicate_ids):
        errors.append(f"duplicate claim_id: {claim_id}")

    # A duplicated ID is ambiguous. Exclude every version of it from the
    # graph so input order cannot select an arbitrary predecessor edge.
    unique_claims = {
        claim_id: claim
        for claim_id, claim in claims_by_id.items()
        if claim_id not in duplicate_ids
    }

    graph = {}
    for claim_id in sorted(unique_claims):
        claim = unique_claims[claim_id]
        predecessor_id = claim.get("supersedes_claim_id")
        if predecessor_id is None:
            continue
        if not isinstance(predecessor_id, str) or not predecessor_id:
            errors.append(f"claim {claim_id} has an invalid supersedes_claim_id")
            continue
        if predecessor_id == claim_id:
            errors.append(f"claim {claim_id} cannot supersede itself")
            continue
        if predecessor_id in duplicate_ids:
            errors.append(
                f"claim {claim_id} references ambiguous supersedes_claim_id: {predecessor_id}"
            )
            continue
        if predecessor_id not in unique_claims and predecessor_id not in known_ids:
            errors.append(
                f"claim {claim_id} references unresolved supersedes_claim_id: {predecessor_id}"
            )
            continue
        if predecessor_id in unique_claims:
            graph[claim_id] = predecessor_id
            previous = unique_claims[predecessor_id]
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

    # Iterative traversal avoids recursion-depth failures on long histories.
    visited = set()
    for start_id in sorted(graph):
        if start_id in visited:
            continue
        path = []
        active_positions = {}
        current_id = start_id
        while current_id in graph and current_id not in visited:
            if current_id in active_positions:
                cycle_start = path[active_positions[current_id]]
                errors.append(f"supersession cycle detected at claim_id: {cycle_start}")
                break
            active_positions[current_id] = len(path)
            path.append(current_id)
            current_id = graph[current_id]
        visited.update(path)

    return sorted(set(errors))
