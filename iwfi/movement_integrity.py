"""Cross-contract integrity checks for normalized on-chain movements."""
from datetime import datetime
from decimal import Decimal, InvalidOperation


TRANSFER_FIELDS = ("amount", "from_address", "to_address", "transaction_id")


def _utc_datetime(value):
    if not isinstance(value, str) or not value.endswith("Z"):
        return None
    try:
        parsed = datetime.fromisoformat(value[:-1] + "+00:00")
    except ValueError:
        return None
    if parsed.utcoffset() is None:
        return None
    return parsed


def resolve_temporal_status(event_time_utc, valid_from_utc, valid_to_utc, claim_found=True):
    """Resolve a claim interval without treating missing bounds as unbounded."""
    if not claim_found:
        return "CLAIM_NOT_FOUND"
    event = _utc_datetime(event_time_utc)
    if event is None:
        return "TIME_UNRESOLVED"
    start = _utc_datetime(valid_from_utc) if valid_from_utc is not None else None
    end = _utc_datetime(valid_to_utc) if valid_to_utc is not None else None
    if valid_from_utc is not None and start is None:
        return "TIME_UNRESOLVED"
    if valid_to_utc is not None and end is None:
        return "TIME_UNRESOLVED"
    if start is not None and end is not None and start > end:
        return "TIME_UNRESOLVED"
    if start is not None and event < start:
        return "NOT_YET_VALID"
    if end is not None and event > end:
        return "EXPIRED_AT_EVENT_TIME"
    if start is None or end is None:
        return "TIME_UNRESOLVED"
    return "VALID_AT_EVENT_TIME"


def _same_amount(left, right):
    if left is None or right is None:
        return left is right
    try:
        return Decimal(left) == Decimal(right)
    except (InvalidOperation, TypeError, ValueError):
        return False


def validate_movement_integrity(movement, observations, claims):
    """Return deterministic integrity errors; never infer missing source facts.

    observations and claims are iterables of canonical source/claim dictionaries.
    This function validates references and consistency only; it does not mutate data.
    """
    errors = []
    observation_index = {item.get("observation_id"): item for item in observations}
    claim_index = {item.get("claim_id"): item for item in claims}
    referenced = movement.get("source_observation_ids", [])
    if not referenced:
        errors.append("source_observation_ids must not be empty")
        return errors

    resolved_observations = []
    for observation_id in referenced:
        observation = observation_index.get(observation_id)
        if observation is None:
            errors.append(f"source observation not found: {observation_id}")
            continue
        if observation.get("observation_type") != "ON_CHAIN_TRANSACTION":
            errors.append(f"source observation is not ON_CHAIN_TRANSACTION: {observation_id}")
            continue
        source_quality = observation.get("quality", {}).get("status")
        if source_quality in {"INVALID", "QUARANTINED", "DUPLICATE"}:
            errors.append(f"source observation quality is not admissible: {observation_id}")
            continue
        source_asset = observation.get("asset", {})
        if source_asset != movement.get("asset", {}):
            errors.append(f"asset/network mismatch for source observation: {observation_id}")
            continue
        source_transfer = observation.get("movement")
        if not isinstance(source_transfer, dict) or source_transfer.get("movement_type") != "TRANSFER":
            errors.append(f"source observation has no transfer movement: {observation_id}")
            continue
        source_time = observation.get("event_time_utc")
        movement_time = movement.get("event_time_utc")
        if source_time is not None and movement_time is not None and source_time != movement_time:
            errors.append(f"event_time mismatch for source observation: {observation_id}")
        for field in TRANSFER_FIELDS:
            source_value = source_transfer.get(field)
            movement_value = movement.get("transfer", {}).get(field)
            if field == "amount":
                equal = _same_amount(source_value, movement_value)
            else:
                equal = source_value == movement_value
            if source_value is not None and movement_value is not None and not equal:
                errors.append(f"{field} mismatch for source observation: {observation_id}")
            elif source_value is not None and movement_value is None:
                errors.append(f"known source {field} omitted from movement: {observation_id}")
        resolved_observations.append(observation)

    # Do not populate a fact that is absent from every referenced source.
    if resolved_observations:
        for field in TRANSFER_FIELDS:
            movement_value = movement.get("transfer", {}).get(field)
            known_values = [item.get("movement", {}).get(field) for item in resolved_observations
                            if item.get("movement", {}).get(field) is not None]
            if not known_values and movement_value is not None:
                errors.append(f"movement {field} has no supporting source value")

    # A movement event time cannot be invented if every referenced observation lacks it.
    if movement.get("event_time_utc") is not None and resolved_observations:
        if all(item.get("event_time_utc") is None for item in resolved_observations):
            errors.append("movement event_time has no supporting source observation")

    endpoints = {movement.get("transfer", {}).get("from_address"), movement.get("transfer", {}).get("to_address")}
    for resolution in movement.get("attribution_resolutions", []):
        claim_id = resolution.get("claim_id")
        claim = claim_index.get(claim_id)
        if claim is None:
            if resolution.get("temporal_status") != "CLAIM_NOT_FOUND":
                errors.append(f"missing claim must use CLAIM_NOT_FOUND: {claim_id}")
            continue
        subject = claim.get("subject", {})
        target = claim.get("object", {})
        if subject.get("subject_type") != "ADDRESS" or subject.get("subject_id") != resolution.get("address"):
            errors.append(f"claim subject/address mismatch: {claim_id}")
        if subject.get("network_id") != movement.get("asset", {}).get("network_id"):
            errors.append(f"claim network mismatch: {claim_id}")
        if resolution.get("address") not in endpoints:
            errors.append(f"attribution address is not a transfer endpoint: {claim_id}")
        expected = {
            "predicate": claim.get("predicate"),
            "object_type": target.get("object_type"),
            "object_id": target.get("object_id"),
            "epistemic_status": claim.get("epistemic_status"),
        }
        for field, value in expected.items():
            if resolution.get(field) != value:
                errors.append(f"{field} mismatch with claim: {claim_id}")
        temporal = resolve_temporal_status(
            movement.get("event_time_utc"), claim.get("valid_from_utc"), claim.get("valid_to_utc")
        )
        if resolution.get("temporal_status") != temporal:
            errors.append(f"temporal_status mismatch with claim interval: {claim_id}")
    return errors
