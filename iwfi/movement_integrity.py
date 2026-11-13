"""Cross-contract integrity checks for normalized on-chain movements."""
from datetime import datetime
from decimal import Decimal, InvalidOperation
import re

from iwfi.attribution_integrity import validate_claim_collection


TRANSFER_FIELDS = ("amount", "unit", "from_address", "to_address", "transaction_id", "confirmation_status")
UTC_TIMESTAMP_PATTERN = re.compile(r"[0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{2}:[0-9]{2}:[0-9]{2}Z")
DECIMAL_AMOUNT_PATTERN = re.compile(r"(?:0|[1-9][0-9]*)(?:\.[0-9]+)?")


def _utc_datetime(value):
    if not isinstance(value, str) or UTC_TIMESTAMP_PATTERN.fullmatch(value) is None:
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
    if (
        not isinstance(left, str)
        or not isinstance(right, str)
        or DECIMAL_AMOUNT_PATTERN.fullmatch(left) is None
        or DECIMAL_AMOUNT_PATTERN.fullmatch(right) is None
    ):
        return False
    try:
        return Decimal(left) == Decimal(right)
    except (InvalidOperation, TypeError, ValueError):
        return False


def validate_movement_integrity(movement, observations, claims, known_claim_ids=()):
    """Return deterministic integrity errors; never infer missing source facts.

    VALID and PARTIAL observations are admissible as source evidence. DELAYED is
    also admissible for historical reconstruction; this validator does not assess
    freshness or real-time eligibility. INVALID, QUARANTINED, DUPLICATE and
    unknown quality states are not admissible.

    Claims are collection-validated before they are used. For partial claim batches,
    known_claim_ids identifies superseded claims resolved in persistent history.
    """
    if not isinstance(movement, dict):
        return ["movement must be an object"]
    try:
        observations = list(observations)
    except TypeError:
        return ["observations must be an iterable of objects"]
    try:
        claims = list(claims)
    except TypeError:
        return ["claims must be an iterable of objects"]

    errors = []

    movement_asset = movement.get("asset")
    if not isinstance(movement_asset, dict):
        errors.append("movement asset must be an object")
        movement_asset = {}
    movement_transfer = movement.get("transfer")
    if not isinstance(movement_transfer, dict):
        errors.append("movement transfer must be an object")
        movement_transfer = {}
    referenced = movement.get("source_observation_ids", [])
    if not isinstance(referenced, (list, tuple)) or any(
        not isinstance(identifier, str) or not identifier for identifier in referenced
    ):
        errors.append("source_observation_ids must be a list of non-empty strings")
        return errors
    attribution_resolutions = movement.get("attribution_resolutions", [])
    if not isinstance(attribution_resolutions, list):
        errors.append("attribution_resolutions must be a list")
        attribution_resolutions = []

    def _unique_index(items, id_field, report_duplicates=True):
        counts = {}
        for index, item in enumerate(items):
            if not isinstance(item, dict):
                if id_field == "observation_id":
                    errors.append(f"observations[{index}] must be an object")
                continue
            identifier = item.get(id_field)
            if not isinstance(identifier, str) or not identifier:
                errors.append(f"invalid {id_field} in evidence collection")
                continue
            counts[identifier] = counts.get(identifier, 0) + 1
        duplicates = sorted(identifier for identifier, count in counts.items() if count > 1)
        if report_duplicates:
            for identifier in duplicates:
                errors.append(f"duplicate {id_field}: {identifier}")
        # Duplicate IDs are ambiguous and must never resolve to an arbitrary
        # record, regardless of whether this helper reports the duplicate.
        duplicate_set = set(duplicates)
        return {
            item[id_field]: item
            for item in items
            if isinstance(item, dict)
            and isinstance(item.get(id_field), str)
            and item[id_field]
            and item[id_field] not in duplicate_set
        }

    observation_index = _unique_index(observations, "observation_id")
    errors.extend(validate_claim_collection(claims, known_claim_ids=known_claim_ids))
    claim_index = _unique_index(claims, "claim_id", report_duplicates=False)
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
        source_quality_data = observation.get("quality")
        source_quality = source_quality_data.get("status") if isinstance(source_quality_data, dict) else None
        if source_quality not in {"VALID", "PARTIAL", "DELAYED"}:
            errors.append(f"source observation quality is not admissible: {observation_id}")
            continue
        source_asset = observation.get("asset", {})
        if source_asset != movement_asset:
            errors.append(f"asset/network mismatch for source observation: {observation_id}")
            continue
        source_transfer = observation.get("movement")
        if not isinstance(source_transfer, dict) or source_transfer.get("movement_type") != "TRANSFER":
            errors.append(f"source observation has no transfer movement: {observation_id}")
            continue
        source_time = observation.get("event_time_utc")
        movement_time = movement.get("event_time_utc")
        if source_time is not None and movement_time is None:
            errors.append(f"known source event_time omitted from movement: {observation_id}")
        elif source_time is not None and movement_time is not None and source_time != movement_time:
            errors.append(f"event_time mismatch for source observation: {observation_id}")
        for field in TRANSFER_FIELDS:
            source_value = source_transfer.get(field)
            movement_value = movement_transfer.get(field)
            if field == "amount":
                if source_value is not None and (
                    not isinstance(source_value, str)
                    or DECIMAL_AMOUNT_PATTERN.fullmatch(source_value) is None
                ):
                    errors.append(f"invalid source amount format: {observation_id}")
                if movement_value is not None and (
                    not isinstance(movement_value, str)
                    or DECIMAL_AMOUNT_PATTERN.fullmatch(movement_value) is None
                ):
                    errors.append("invalid movement amount format")
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
            movement_value = movement_transfer.get(field)
            known_values = [
                item.get("movement", {}).get(field)
                for item in resolved_observations
                if item.get("movement", {}).get(field) is not None
            ]
            if not known_values and movement_value is not None:
                errors.append(f"movement {field} has no supporting source value")

    # A movement event time cannot be invented if every referenced observation lacks it.
    if movement.get("event_time_utc") is not None and resolved_observations:
        if all(item.get("event_time_utc") is None for item in resolved_observations):
            errors.append("movement event_time has no supporting source observation")

    endpoints = [
        movement_transfer.get("from_address"),
        movement_transfer.get("to_address"),
    ]
    for resolution in attribution_resolutions:
        if not isinstance(resolution, dict):
            errors.append("attribution resolution must be an object")
            continue
        claim_id = resolution.get("claim_id")
        if not isinstance(claim_id, str) or not claim_id:
            errors.append("attribution resolution has an invalid claim_id")
            continue
        claim = claim_index.get(claim_id)
        if claim is None:
            if resolution.get("temporal_status") != "CLAIM_NOT_FOUND":
                errors.append(f"missing claim must use CLAIM_NOT_FOUND: {claim_id}")
            continue
        subject = claim.get("subject")
        target = claim.get("object")
        if not isinstance(subject, dict) or not isinstance(target, dict):
            errors.append(f"claim subject/object must be objects: {claim_id}")
            continue
        if subject.get("subject_type") != "ADDRESS" or subject.get("subject_id") != resolution.get("address"):
            errors.append(f"claim subject/address mismatch: {claim_id}")
        if subject.get("network_id") != movement_asset.get("network_id"):
            errors.append(f"claim network mismatch: {claim_id}")
        address = resolution.get("address")
        if not isinstance(address, str) or address not in endpoints:
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
