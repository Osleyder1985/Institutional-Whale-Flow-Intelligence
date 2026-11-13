"""Deterministic, provider-neutral resolution of on-chain observations."""
from collections import defaultdict
from decimal import Decimal, InvalidOperation
import hashlib
import json


POLICY_VERSION = "1.0.0"
TRANSFER_FIELDS = (
    "asset_id",
    "network_id",
    "event_time_utc",
    "amount",
    "unit",
    "from_address",
    "to_address",
    "transaction_id",
    "confirmation_status",
    "event_locator",
)
REQUIRED_ANALYTICAL_FIELDS = (
    "asset_id",
    "network_id",
    "event_time_utc",
    "amount",
    "unit",
    "from_address",
    "to_address",
    "transaction_id",
    "event_locator",
)
LOCATOR_KINDS = {
    "bitcoin-mainnet": {"UTXO_VOUT"},
    "eip155:1": {"EVM_LOG_INDEX", "EVM_TRACE_PATH", "EVM_TX_VALUE"},
}
INVALID_QUALITY = {"INVALID", "QUARANTINED"}


def _canonical_json(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def _decimal_key(value):
    if value is None:
        return None
    try:
        number = Decimal(str(value))
    except (InvalidOperation, TypeError, ValueError):
        return ("INVALID_DECIMAL", str(value))
    if not number.is_finite():
        return ("INVALID_DECIMAL", str(value))
    if number < 0:
        return ("INVALID_DECIMAL", str(value))
    normalized = format(number, "f")
    if "." in normalized:
        normalized = normalized.rstrip("0").rstrip(".")
    return normalized or "0"


def _field_value(observation, field):
    asset = observation.get("asset") or {}
    movement = observation.get("movement") or {}
    if field in {"asset_id", "network_id"}:
        return asset.get(field)
    if field == "event_time_utc":
        return observation.get(field)
    if field == "event_locator":
        return movement.get("event_locator")
    return movement.get(field)


def _normalized_field(field, value, network_id):
    if value is None:
        return None
    if field == "amount":
        return _decimal_key(value)
    if field == "transaction_id":
        return value.casefold() if isinstance(value, str) else value
    if field in {"from_address", "to_address"} and network_id == "eip155:1":
        return value.lower() if isinstance(value, str) else value
    if field == "event_locator":
        if not isinstance(value, dict):
            return ("INVALID_LOCATOR", str(value))
        kind = value.get("kind")
        raw = value.get("value")
        if not isinstance(kind, str) or not isinstance(raw, str) or not raw:
            return ("INVALID_LOCATOR", _canonical_json(value))
        if kind in {"UTXO_VOUT", "EVM_LOG_INDEX"}:
            if not raw.isdigit():
                return ("INVALID_LOCATOR", _canonical_json(value))
            raw = str(int(raw))
        elif kind == "EVM_TRACE_PATH":
            parts = raw.split("/")
            if not parts or any(not part.isdigit() for part in parts):
                return ("INVALID_LOCATOR", _canonical_json(value))
            raw = "/".join(str(int(part)) for part in parts)
        elif kind == "EVM_TX_VALUE":
            if raw != "transaction-value":
                return ("INVALID_LOCATOR", _canonical_json(value))
        else:
            return ("INVALID_LOCATOR", _canonical_json(value))
        return (kind, raw)
    return value


def _transaction_key(observation):
    asset = observation.get("asset") or {}
    movement = observation.get("movement") or {}
    network_id = asset.get("network_id")
    txid = movement.get("transaction_id")
    if not isinstance(network_id, str) or not network_id:
        return None
    if not isinstance(txid, str) or not txid.strip():
        return None
    return (network_id, txid.casefold())


def _event_key(observation):
    asset = observation.get("asset") or {}
    movement = observation.get("movement") or {}
    network_id = asset.get("network_id")
    tx_key = _transaction_key(observation)
    locator = movement.get("event_locator")
    if tx_key is None or not isinstance(locator, dict):
        return None
    kind = locator.get("kind")
    value = locator.get("value")
    if kind not in LOCATOR_KINDS.get(network_id, set()):
        return None
    normalized = _normalized_field("event_locator", locator, network_id)
    if not isinstance(normalized, tuple) or len(normalized) != 2 or normalized[0] == "INVALID_LOCATOR":
        return None
    return (network_id, tx_key[1], normalized[0], normalized[1])


def _source_record_relation(left, right):
    ls = left.get("source") or {}
    rs = right.get("source") or {}
    left_key = (ls.get("provider"), ls.get("endpoint"), ls.get("record_id"))
    right_key = (rs.get("provider"), rs.get("endpoint"), rs.get("record_id"))
    if not all(isinstance(part, str) and part for part in left_key):
        return "NONE"
    if left_key != right_key:
        return "NONE"
    if ls.get("payload_sha256") == rs.get("payload_sha256"):
        return "EXACT_REPEAT"
    return "SAME_RECORD_DIFFERENT_PAYLOAD"


def _candidate_field_matches(left, right):
    network = (left.get("asset") or {}).get("network_id")
    comparable = ("asset_id", "amount", "unit", "from_address", "to_address", "event_time_utc")
    matches = 0
    for field in comparable:
        lv = _field_value(left, field)
        rv = _field_value(right, field)
        if lv is not None and rv is not None:
            if _normalized_field(field, lv, network) == _normalized_field(field, rv, network):
                matches += 1
    return matches


def classify_observation_pair(left, right):
    """Classify a pair without merging or mutating either observation."""
    left_id = left.get("observation_id")
    right_id = right.get("observation_id")
    ids = sorted([str(left_id), str(right_id)])
    left_asset = left.get("asset") or {}
    right_asset = right.get("asset") or {}
    left_network = left_asset.get("network_id")
    right_network = right_asset.get("network_id")
    reasons = []
    conflicts = []

    if left_network and right_network and left_network != right_network:
        match_class = "NO_MATCH"
        reasons.append("DIFFERENT_NETWORK")
    else:
        left_tx = _transaction_key(left)
        right_tx = _transaction_key(right)
        left_event = _event_key(left)
        right_event = _event_key(right)
        if left_tx and right_tx and left_tx != right_tx:
            match_class = "NO_MATCH"
            reasons.append("DIFFERENT_TRANSACTION_IDENTITY")
        elif left_event and right_event:
            if left_event == right_event:
                match_class = "STRONG_MATCH"
                reasons.append("SAME_NETWORK_TRANSACTION_AND_EVENT_LOCATOR")
            else:
                match_class = "NO_MATCH"
                reasons.append("DIFFERENT_EVENT_LOCATOR")
        elif left_tx and right_tx and left_tx == right_tx:
            match_class = "CANDIDATE"
            reasons.append("SAME_TRANSACTION_BUT_EVENT_IDENTITY_UNRESOLVED")
        elif left_network and left_network == right_network:
            if _candidate_field_matches(left, right) >= 3:
                match_class = "CANDIDATE"
                reasons.append("PARTIAL_FIELDS_ARE_COMPATIBLE_BUT_NO_STRONG_IDENTIFIER")
            else:
                match_class = "NO_MATCH"
                reasons.append("INSUFFICIENT_SHARED_EVIDENCE")
        else:
            match_class = "NO_MATCH"
            reasons.append("NETWORK_OR_TRANSACTION_IDENTITY_MISSING")

    if match_class == "STRONG_MATCH":
        network = left_network
        for field in TRANSFER_FIELDS:
            lv = _field_value(left, field)
            rv = _field_value(right, field)
            if lv is None or rv is None:
                continue
            if _normalized_field(field, lv, network) != _normalized_field(field, rv, network):
                conflicts.append(field)
        if conflicts:
            reasons.append("CONTRADICTORY_FIELD_VALUES")

    source_relation = _source_record_relation(left, right)
    if source_relation == "EXACT_REPEAT":
        reasons.append("SAME_PROVIDER_RECORD_AND_PAYLOAD")
    elif source_relation == "SAME_RECORD_DIFFERENT_PAYLOAD":
        reasons.append("SAME_PROVIDER_RECORD_WITH_CHANGED_PAYLOAD")

    return {
        "observation_ids": ids,
        "match_class": match_class,
        "source_record_relation": source_relation,
        "field_conflicts": sorted(conflicts),
        "reasons": sorted(reasons),
    }


def _field_evidence(observations, field):
    network = (observations[0].get("asset") or {}).get("network_id")
    values = {}
    for observation in observations:
        value = _field_value(observation, field)
        if value is None:
            continue
        normalized = _normalized_field(field, value, network)
        key = _canonical_json(normalized)
        values.setdefault(key, {"normalized": normalized, "evidence": []})
        source = observation.get("source") or {}
        values[key]["evidence"].append({
            "observation_id": observation["observation_id"],
            "provider": source.get("provider"),
            "value": value,
        })
    result = []
    for key in sorted(values):
        item = values[key]
        item["evidence"].sort(key=lambda entry: (entry["observation_id"], str(entry["provider"])))
        result.append(item)
    return result


def resolve_observations(observations, supersedes_decision_id=None):
    """Create a deterministic resolution decision from source observations.

    Only an identical network + transaction ID + protocol event locator can
    establish a strong transfer-event identity. Candidate links are never
    merged into an event. The function is pure and performs no persistence.
    """
    items = list(observations)
    errors = []
    ids = []
    for item in items:
        identifier = item.get("observation_id") if isinstance(item, dict) else None
        if not isinstance(identifier, str) or not identifier:
            errors.append("observation_id must be a non-empty string")
        else:
            ids.append(identifier)
        if not isinstance(item, dict) or item.get("observation_type") != "ON_CHAIN_TRANSACTION":
            errors.append(f"observation is not ON_CHAIN_TRANSACTION: {identifier}")
            continue
        asset = item.get("asset") or {}
        movement = item.get("movement") or {}
        network_id = asset.get("network_id")
        if not isinstance(network_id, str) or not network_id:
            errors.append(f"missing network_id: {identifier}")
        if not isinstance(movement, dict) or movement.get("movement_type") != "TRANSFER":
            errors.append(f"observation has no TRANSFER movement: {identifier}")
        locator = movement.get("event_locator") if isinstance(movement, dict) else None
        if locator is not None:
            normalized_locator = _normalized_field("event_locator", locator, network_id)
            if (
                not isinstance(locator, dict)
                or locator.get("kind") not in LOCATOR_KINDS.get(network_id, set())
                or not isinstance(normalized_locator, tuple)
                or normalized_locator[0] == "INVALID_LOCATOR"
            ):
                errors.append(f"invalid event_locator for observation: {identifier}")
    duplicate_ids = sorted(identifier for identifier in set(ids) if ids.count(identifier) > 1)
    errors.extend(f"duplicate observation_id: {identifier}" for identifier in duplicate_ids)

    canonical_items = sorted(
        items,
        key=lambda item: (
            str(item.get("observation_id", "")) if isinstance(item, dict) else "",
            _canonical_json(item),
        ),
    )
    fingerprint = hashlib.sha256(_canonical_json(canonical_items).encode("utf-8")).hexdigest()
    decision_id = "decision-" + hashlib.sha256(
        f"{POLICY_VERSION}:{fingerprint}".encode("utf-8")
    ).hexdigest()[:32]

    if errors:
        return {
            "decision_id": decision_id,
            "policy_version": POLICY_VERSION,
            "input_fingerprint": fingerprint,
            "supersedes_decision_id": supersedes_decision_id,
            "status": "INVALID",
            "errors": sorted(set(errors)),
            "links": [],
            "events": [],
        }

    links = []
    for index, left in enumerate(canonical_items):
        for right in canonical_items[index + 1:]:
            links.append(classify_observation_pair(left, right))
    links.sort(key=lambda link: (link["observation_ids"], link["match_class"]))

    grouped = defaultdict(list)
    for item in canonical_items:
        key = _event_key(item)
        if key is not None:
            grouped[key].append(item)

    events = []
    for key in sorted(grouped):
        group = grouped[key]
        group.sort(key=lambda item: item["observation_id"])
        field_evidence = {field: _field_evidence(group, field) for field in TRANSFER_FIELDS}
        conflicts = sorted(field for field, evidence in field_evidence.items() if len(evidence) > 1)
        invalid_fields = sorted(
            field for field, evidence in field_evidence.items()
            if any(
                isinstance(entry["normalized"], tuple)
                and entry["normalized"]
                and entry["normalized"][0] in {"INVALID_DECIMAL", "INVALID_LOCATOR"}
                for entry in evidence
            )
        )
        resolved_fields = {}
        for field, evidence in field_evidence.items():
            if len(evidence) != 1 or field in invalid_fields:
                resolved_fields[field] = None
                continue
            normalized = evidence[0]["normalized"]
            if field == "event_locator":
                resolved_fields[field] = {"kind": normalized[0], "value": normalized[1]}
            elif field in {"amount", "transaction_id"}:
                resolved_fields[field] = normalized
            elif field in {"from_address", "to_address"} and key[0] == "eip155:1":
                resolved_fields[field] = normalized
            else:
                resolved_fields[field] = evidence[0]["evidence"][0]["value"]
        missing = [
            field for field in REQUIRED_ANALYTICAL_FIELDS
            if resolved_fields.get(field) is None
        ]
        invalid_quality = sorted({
            (item.get("quality") or {}).get("status")
            for item in group
            if (item.get("quality") or {}).get("status") in INVALID_QUALITY
        })
        if invalid_fields or invalid_quality:
            resolution_status = "INVALID"
        elif conflicts:
            resolution_status = "CONTRADICTORY"
        elif missing:
            resolution_status = "PARTIAL"
        else:
            resolution_status = "COMPLETE"
        eligibility_reasons = []
        if conflicts:
            eligibility_reasons.append("MATERIAL_FIELD_CONFLICT")
        eligibility_reasons.extend(f"INVALID_FIELD_VALUE:{field}" for field in invalid_fields)
        if missing:
            eligibility_reasons.extend(f"MISSING_REQUIRED_FIELD:{field}" for field in missing)
        if invalid_quality:
            eligibility_reasons.append("INVALID_OR_QUARANTINED_SOURCE_QUALITY")
        eligible = resolution_status == "COMPLETE"
        event_identity = _canonical_json(key)
        event_id = "event-" + hashlib.sha256(event_identity.encode("utf-8")).hexdigest()[:32]
        events.append({
            "event_id": event_id,
            "identity_status": "RESOLVED",
            "resolution_status": resolution_status,
            "analytical_eligibility": "ELIGIBLE" if eligible else "INELIGIBLE",
            "eligibility_reasons": sorted(eligibility_reasons),
            "transaction_identity": {"network_id": key[0], "transaction_id": key[1]},
            "event_locator": {"kind": key[2], "value": key[3]},
            "observation_ids": [item["observation_id"] for item in group],
            "resolved_fields": resolved_fields,
            "field_evidence": field_evidence,
            "field_conflicts": conflicts,
            "missing_required_fields": sorted(missing),
        })

    events.sort(key=lambda event: event["event_id"])
    return {
        "decision_id": decision_id,
        "policy_version": POLICY_VERSION,
        "input_fingerprint": fingerprint,
        "supersedes_decision_id": supersedes_decision_id,
        "status": (
            "RESOLVED_WITH_CANDIDATES"
            if events and any(link["match_class"] == "CANDIDATE" for link in links)
            else "RESOLVED" if events
            else "CANDIDATES_ONLY" if links
            else "INSUFFICIENT_EVIDENCE"
        ),
        "errors": [],
        "links": links,
        "events": events,
    }
