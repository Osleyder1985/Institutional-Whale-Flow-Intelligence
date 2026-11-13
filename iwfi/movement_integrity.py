"""Cross-contract integrity checks for normalized on-chain movements."""
from datetime import datetime
from decimal import Decimal, InvalidOperation
import re

from iwfi.attribution_integrity import validate_claim_collection


TRANSFER_FIELDS = ("amount", "unit", "from_address", "to_address", "transaction_id", "confirmation_status", "event_locator")
UTC_TIMESTAMP_PATTERN = re.compile(r"[0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{2}:[0-9]{2}:[0-9]{2}Z")


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
    try:
        return Decimal(left) == Decimal(right)
    except (InvalidOperation, TypeError, ValueError):
        return False



def _normalized_transaction_id(network_id, value):
    if not isinstance(value, str):
        return None
    if network_id == "bitcoin-mainnet":
        return value.lower() if re.fullmatch(r"[0-9a-fA-F]{64}", value) else None
    if network_id == "eip155:1":
        raw = value[2:] if value[:2].lower() == "0x" else value
        return raw.lower() if re.fullmatch(r"[0-9a-fA-F]{64}", raw) else None
    return None


def _normalized_event_locator(value, network_id):
    if not isinstance(value, dict):
        return None
    kind = value.get("kind")
    raw = value.get("value")
    allowed = {
        "bitcoin-mainnet": {"UTXO_VOUT"},
        "eip155:1": {"EVM_TRACE_PATH", "EVM_TX_VALUE"},
    }
    if kind not in allowed.get(network_id, set()) or not isinstance(raw, str):
        return None
    if kind == "UTXO_VOUT":
        if re.fullmatch(r"[0-9]+", raw) is None:
            return None
        raw = raw.lstrip("0") or "0"
    elif kind == "EVM_TRACE_PATH":
        parts = raw.split("/")
        if not parts or any(re.fullmatch(r"[0-9]+", part) is None for part in parts):
            return None
        raw = "/".join(part.lstrip("0") or "0" for part in parts)
    elif kind == "EVM_TX_VALUE" and raw != "transaction-value":
        return None
    return kind, raw


def _same_transfer_field(field, left, right, network_id):
    if field == "amount":
        return _same_amount(left, right)
    if field == "transaction_id":
        left_key = _normalized_transaction_id(network_id, left)
        right_key = _normalized_transaction_id(network_id, right)
        return left_key is not None and left_key == right_key
    if field in {"from_address", "to_address"} and network_id == "eip155:1":
        return (
            left.lower() == right.lower()
            if isinstance(left, str) and isinstance(right, str)
            else left == right
        )
    if field == "event_locator":
        left_key = _normalized_event_locator(left, network_id)
        right_key = _normalized_event_locator(right, network_id)
        return left_key is not None and left_key == right_key
    return left == right


def validate_movement_integrity(movement, observations, claims, known_claim_ids=()):
    """Return deterministic integrity errors; never infer missing source facts.

    VALID, PARTIAL and DELAYED observations may support historical integrity.
    DELAYED remains unchanged and does not establish real-time availability.
    Claims are collection-validated before attribution data is used.
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

        quality = observation.get("quality")
        source_quality = quality.get("status") if isinstance(quality, dict) else None
        if source_quality not in {"VALID", "PARTIAL", "DELAYED"}:
            errors.append(f"source observation quality is not admissible: {observation_id}")
            continue

        source_asset = observation.get("asset")
        if not isinstance(source_asset, dict) or source_asset != movement_asset:
            errors.append(f"asset/network mismatch for source observation: {observation_id}")
            continue

        source_transfer = observation.get("movement")
        if not isinstance(source_transfer, dict) or source_transfer.get("movement_type") != "TRANSFER":
            errors.append(f"source observation has no transfer movement: {observation_id}")
            continue

        source_txid = source_transfer.get("transaction_id")
        if source_txid is not None and _normalized_transaction_id(source_asset.get("network_id"), source_txid) is None:
            errors.append(f"invalid source transaction_id for observation: {observation_id}")
        movement_txid = movement_transfer.get("transaction_id")
        network_id = movement_asset.get("network_id")
        if movement_txid is not None and _normalized_transaction_id(network_id, movement_txid) is None:
            errors.append("movement transaction_id has invalid network-specific format")

        source_time = observation.get("event_time_utc")
        movement_time = movement.get("event_time_utc")
        if source_time is not None and _utc_datetime(source_time) is None:
            errors.append(f"invalid source event_time_utc: {observation_id}")
        if movement_time is not None and _utc_datetime(movement_time) is None:
            errors.append("movement event_time_utc is invalid")
        if source_time is not None and movement_time is None:
            errors.append(f"known source event_time omitted from movement: {observation_id}")
        elif source_time is not None and movement_time is not None and source_time != movement_time:
            errors.append(f"event_time mismatch for source observation: {observation_id}")

        for field in TRANSFER_FIELDS:
            source_value = source_transfer.get(field)
            movement_value = movement_transfer.get(field)
            equal = _same_transfer_field(field, source_value, movement_value, network_id)
            if source_value is not None and movement_value is not None and not equal:
                errors.append(f"{field} mismatch for source observation: {observation_id}")
            elif source_value is not None and movement_value is None:
                errors.append(f"known source {field} omitted from movement: {observation_id}")
        resolved_observations.append(observation)

    if resolved_observations:
        for field in TRANSFER_FIELDS:
            movement_value = movement_transfer.get(field)
            known_values = [
                item.get("movement", {}).get(field)
                for item in resolved_observations
                if isinstance(item.get("movement"), dict)
                and item["movement"].get(field) is not None
            ]
            if not known_values and movement_value is not None:
                errors.append(f"movement {field} has no supporting source value")

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
        address = resolution.get("address")
        if subject.get("subject_type") != "ADDRESS" or subject.get("subject_id") != address:
            errors.append(f"claim subject/address mismatch: {claim_id}")
        if subject.get("network_id") != movement_asset.get("network_id"):
            errors.append(f"claim network mismatch: {claim_id}")
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
