"""Deterministic, provider-neutral resolution of on-chain observations."""
from collections import defaultdict
from decimal import Decimal, InvalidOperation
from itertools import combinations
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
CANDIDATE_FIELDS = ("asset_id", "amount", "unit", "from_address", "to_address", "event_time_utc")
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
    "confirmation_status",
)
LOCATOR_KINDS = {
    "bitcoin-mainnet": {"UTXO_VOUT"},
    "eip155:1": {"EVM_TRACE_PATH", "EVM_TX_VALUE"},
}
INVALID_QUALITY = {"INVALID", "QUARANTINED"}
ALLOWED_QUALITY = {"VALID", "PARTIAL", "DELAYED", "DUPLICATE", "INVALID", "QUARANTINED"}
ASSET_NETWORKS = {"bitcoin:btc": "bitcoin-mainnet", "ethereum:eth": "eip155:1"}


def _canonical_json(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def _decimal_key(value):
    if value is None:
        return None
    if not isinstance(value, str):
        return ("INVALID_DECIMAL", str(value))
    try:
        number = Decimal(value)
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
        if kind == "UTXO_VOUT":
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


def _candidate_signature_keys(observation):
    """Return deterministic three-field blocking keys for partial observations."""
    asset = observation.get("asset") or {}
    network_id = asset.get("network_id")
    if not isinstance(network_id, str) or not network_id:
        return []
    known = []
    for field in CANDIDATE_FIELDS:
        value = _field_value(observation, field)
        if value is not None:
            normalized = _normalized_field(field, value, network_id)
            known.append((field, _canonical_json(normalized)))
    if len(known) < 3:
        return []
    return [
        (network_id, tuple(selection))
        for selection in combinations(known, 3)
    ]


def _source_record_key(observation):
    source = observation.get("source") or {}
    parts = (source.get("provider"), source.get("endpoint"), source.get("record_id"))
    if all(isinstance(part, str) and part for part in parts):
        return parts
    return None


def _provider_duplicate_relation(left, right):
    left_id = left.get("observation_id")
    right_id = right.get("observation_id")
    left_target = (left.get("quality") or {}).get("duplicate_of")
    right_target = (right.get("quality") or {}).get("duplicate_of")
    if left_target == right_id and right_target == left_id:
        return "BIDIRECTIONAL_DECLARATION"
    if left_target == right_id:
        return "LEFT_DECLARED_DUPLICATE_OF_RIGHT"
    if right_target == left_id:
        return "RIGHT_DECLARED_DUPLICATE_OF_LEFT"
    return "NONE"


def _source_record_relation(left, right):
    ls = left.get("source") or {}
    rs = right.get("source") or {}
    left_key = (ls.get("provider"), ls.get("endpoint"), ls.get("record_id"))
    right_key = (rs.get("provider"), rs.get("endpoint"), rs.get("record_id"))
    if not all(isinstance(part, str) and part for part in left_key):
        return "NONE"
    if left_key != right_key:
        return "NONE"
    left_hash = ls.get("payload_sha256")
    right_hash = rs.get("payload_sha256")
    valid_hashes = all(
        isinstance(value, str)
        and len(value) == 64
        and all(character in "0123456789abcdef" for character in value)
        for value in (left_hash, right_hash)
    )
    if not valid_hashes:
        return "SAME_RECORD_HASH_UNAVAILABLE"
    if left_hash == right_hash:
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
    left_event = _event_key(left)
    right_event = _event_key(right)
    reasons = []
    conflicts = []

    if left_network and right_network and left_network != right_network:
        match_class = "NO_MATCH"
        reasons.append("DIFFERENT_NETWORK")
    else:
        left_tx = _transaction_key(left)
        right_tx = _transaction_key(right)
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

    provider_duplicate_relation = _provider_duplicate_relation(left, right)
    if provider_duplicate_relation != "NONE":
        reasons.append("PROVIDER_DECLARED_DUPLICATE_RELATION")
        if left_event is not None and right_event is not None:
            if left_event == right_event:
                reasons.append("PROVIDER_DUPLICATE_CONSISTENT_WITH_EVENT_IDENTITY")
            else:
                reasons.append("PROVIDER_DUPLICATE_CONTRADICTS_EVENT_IDENTITY")
        else:
            reasons.append("PROVIDER_DUPLICATE_IDENTITY_UNRESOLVED")

    source_relation = _source_record_relation(left, right)
    if source_relation == "EXACT_REPEAT":
        reasons.append("SAME_PROVIDER_RECORD_AND_PAYLOAD")
    elif source_relation == "SAME_RECORD_DIFFERENT_PAYLOAD":
        reasons.append("SAME_PROVIDER_RECORD_WITH_CHANGED_PAYLOAD")

    return {
        "observation_ids": ids,
        "match_class": match_class,
        "source_record_relation": source_relation,
        "provider_duplicate_relation": provider_duplicate_relation,
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
        source = item.get("source") or {}
        if not isinstance(source.get("provider"), str) or not source["provider"].strip():
            errors.append(f"invalid source provider: {identifier}")
        if not isinstance(source.get("endpoint"), str) or not source["endpoint"].strip():
            errors.append(f"invalid source endpoint: {identifier}")
        payload_hash = source.get("payload_sha256")
        if (
            not isinstance(payload_hash, str)
            or len(payload_hash) != 64
            or any(character not in "0123456789abcdef" for character in payload_hash)
        ):
            errors.append(f"invalid source payload_sha256: {identifier}")
        asset = item.get("asset") or {}
        movement = item.get("movement") or {}
        network_id = asset.get("network_id")
        asset_id = asset.get("asset_id")
        if not isinstance(network_id, str) or not network_id:
            errors.append(f"missing network_id: {identifier}")
        if asset_id not in ASSET_NETWORKS or ASSET_NETWORKS.get(asset_id) != network_id:
            errors.append(f"invalid asset/network identity: {identifier}")
        quality = item.get("quality") or {}
        quality_status = quality.get("status")
        if quality_status not in ALLOWED_QUALITY:
            errors.append(f"invalid quality status: {identifier}")
        if quality_status == "DUPLICATE":
            duplicate_of = quality.get("duplicate_of")
            if not isinstance(duplicate_of, str) or not duplicate_of.strip():
                errors.append(f"duplicate observation missing duplicate_of: {identifier}")
            elif duplicate_of == identifier:
                errors.append(f"observation cannot be duplicate of itself: {identifier}")
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
    if supersedes_decision_id is not None and (
        not isinstance(supersedes_decision_id, str) or not supersedes_decision_id.strip()
    ):
        errors.append("supersedes_decision_id must be null or a non-empty string")

    canonical_items = sorted(
        items,
        key=lambda item: (
            str(item.get("observation_id", "")) if isinstance(item, dict) else "",
            _canonical_json(item),
        ),
    )
    fingerprint = hashlib.sha256(_canonical_json(canonical_items).encode("utf-8")).hexdigest()
    decision_context = {
        "policy_version": POLICY_VERSION,
        "input_fingerprint": fingerprint,
        "supersedes_decision_id": supersedes_decision_id,
    }
    decision_context_fingerprint = hashlib.sha256(
        _canonical_json(decision_context).encode("utf-8")
    ).hexdigest()
    decision_id = "decision-" + decision_context_fingerprint[:32]

    if errors:
        return {
            "decision_id": decision_id,
            "policy_version": POLICY_VERSION,
            "input_fingerprint": fingerprint,
            "decision_context_fingerprint": decision_context_fingerprint,
            "supersedes_decision_id": supersedes_decision_id,
            "status": "INVALID",
            "errors": sorted(set(errors)),
            "links": [],
            "events": [],
        }

    # Build only plausible comparison buckets. Do not materialize the global
    # O(n^2) cross-product of unrelated observations.
    event_buckets = defaultdict(list)
    transaction_buckets = defaultdict(list)
    source_buckets = defaultdict(list)
    partial_buckets = defaultdict(list)
    for index, item in enumerate(canonical_items):
        event_key = _event_key(item)
        transaction_key = _transaction_key(item)
        if event_key is not None:
            event_buckets[event_key].append(index)
        if transaction_key is not None:
            transaction_buckets[transaction_key].append((index, event_key is not None))
        source_key = _source_record_key(item)
        if source_key is not None:
            source_buckets[source_key].append(index)
        for signature in _candidate_signature_keys(item):
            partial_buckets[signature].append(index)

    pair_indexes = set()
    observation_indexes = {
        item["observation_id"]: index
        for index, item in enumerate(canonical_items)
    }
    for index, item in enumerate(canonical_items):
        duplicate_of = (item.get("quality") or {}).get("duplicate_of")
        target_index = observation_indexes.get(duplicate_of)
        if target_index is not None and target_index != index:
            pair_indexes.add(tuple(sorted((index, target_index))))

    def add_pairs(indexes):
        for left_index, right_index in combinations(sorted(set(indexes)), 2):
            pair_indexes.add((left_index, right_index))

    for indexes in event_buckets.values():
        add_pairs(indexes)
    for bucket in transaction_buckets.values():
        for (left_index, left_has_event), (right_index, right_has_event) in combinations(bucket, 2):
            if not (left_has_event and right_has_event):
                pair_indexes.add(tuple(sorted((left_index, right_index))))
    for indexes in source_buckets.values():
        add_pairs(indexes)
    for indexes in partial_buckets.values():
        add_pairs(indexes)

    links = []
    for left_index, right_index in sorted(pair_indexes):
        link = classify_observation_pair(canonical_items[left_index], canonical_items[right_index])
        if (
            link["match_class"] != "NO_MATCH"
            or link["source_record_relation"] != "NONE"
            or link["provider_duplicate_relation"] != "NONE"
        ):
            links.append(link)
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
        confirmation_status = resolved_fields.get("confirmation_status")
        if confirmation_status != "CONFIRMED":
            eligibility_reasons.append("CONFIRMATION_NOT_CONFIRMED")
        eligible = resolution_status == "COMPLETE" and confirmation_status == "CONFIRMED"
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
        "decision_context_fingerprint": decision_context_fingerprint,
        "supersedes_decision_id": supersedes_decision_id,
        "status": (
            "RESOLVED_WITH_RELATION_CONFLICTS"
            if any(
                "PROVIDER_DUPLICATE_CONTRADICTS_EVENT_IDENTITY" in link["reasons"]
                for link in links
            )
            else "RESOLVED_WITH_CANDIDATES"
            if events and any(link["match_class"] == "CANDIDATE" for link in links)
            else "RESOLVED" if events
            else "CANDIDATES_ONLY" if any(link["match_class"] == "CANDIDATE" for link in links)
            else "INSUFFICIENT_EVIDENCE"
        ),
        "errors": [],
        "links": links,
        "events": events,
    }
