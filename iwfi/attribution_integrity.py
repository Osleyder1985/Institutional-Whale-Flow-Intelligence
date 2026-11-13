"""Validation helpers for temporal attribution-claim invariants."""
from datetime import datetime


def _parse_utc_timestamp(value):
    if not isinstance(value, str) or not value.endswith("Z"):
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
