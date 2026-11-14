"""Evidence-gated entity flow aggregation for BTC/ETH movement records.

This module resolves address-to-entity relationships from existing attribution
claims. It does not infer wallet clusters, beneficial ownership, trades, balances,
or accumulation/distribution.
"""
from __future__ import annotations

from collections import defaultdict
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
import re

from iwfi.attribution_integrity import validate_claim_collection


UTC_PATTERN = re.compile(r"[0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{2}:[0-9]{2}:[0-9]{2}Z")
AMOUNT_PATTERN = re.compile(r"(?:0|[1-9][0-9]*)(?:\.[0-9]+)?")


def _parse_utc(value):
    if not isinstance(value, str) or UTC_PATTERN.fullmatch(value) is None:
        return None
    try:
        return datetime.fromisoformat(value[:-1] + "+00:00")
    except ValueError:
        return None


def _address_key(address, network_id):
    if not isinstance(address, str) or not address:
        return None
    return address.lower() if network_id == "eip155:1" else address


def _claim_applies(claim, event_time, known_at):
    """Return (eligible, reason); only reviewed VERIFIED control/operator claims count."""
    if claim.get("epistemic_status") == "DISPUTED" or claim.get("review_status") == "DISPUTED":
        return False, "DISPUTED"
    if claim.get("epistemic_status") != "VERIFIED":
        return False, "NOT_VERIFIED"
    if claim.get("review_status") != "REVIEWED":
        return False, "NOT_REVIEWED"
    if claim.get("predicate") not in {"CONTROLLED_BY", "OPERATED_BY"}:
        return False, "NON_ATTRIBUTING_PREDICATE"
    if claim.get("counter_evidence"):
        return False, "COUNTER_EVIDENCE_PRESENT"
    if not claim.get("supporting_evidence"):
        return False, "SUPPORTING_EVIDENCE_MISSING"
    recorded = _parse_utc(claim.get("recorded_at_utc"))
    start = _parse_utc(claim.get("valid_from_utc"))
    end = _parse_utc(claim.get("valid_to_utc"))
    if recorded is None or start is None or end is None:
        return False, "TIME_UNRESOLVED"
    if recorded > known_at:
        return False, "NOT_KNOWN_AT_CUTOFF"
    if start > end:
        return False, "INVALID_INTERVAL"
    if event_time < start or event_time > end:
        return False, "NOT_VALID_AT_EVENT_TIME"
    subject = claim.get("subject")
    target = claim.get("object")
    if not isinstance(subject, dict) or subject.get("subject_type") != "ADDRESS":
        return False, "SUBJECT_NOT_ADDRESS"
    if not isinstance(target, dict) or target.get("object_type") != "ENTITY":
        return False, "TARGET_NOT_ENTITY"
    if not isinstance(target.get("object_id"), str) or not target["object_id"]:
        return False, "ENTITY_ID_MISSING"
    return True, "ELIGIBLE"


def _resolve_address(address, network_id, event_time, known_at, claim_index):
    key = _address_key(address, network_id)
    if key is None:
        return {"status": "UNKNOWN", "entity_id": None, "claim_ids": [], "reason": "ADDRESS_MISSING"}
    eligible = []
    disputed = []
    rejected_reasons = set()
    for claim in claim_index.values():
        subject = claim.get("subject")
        if not isinstance(subject, dict):
            continue
        if subject.get("subject_type") != "ADDRESS":
            continue
        if subject.get("network_id") != network_id:
            continue
        if _address_key(subject.get("subject_id"), network_id) != key:
            continue
        applies, reason = _claim_applies(claim, event_time, known_at)
        if reason == "DISPUTED":
            disputed.append(claim["claim_id"])
        elif applies:
            eligible.append(claim)
        else:
            rejected_reasons.add(reason)
    entity_ids = {claim["object"]["object_id"] for claim in eligible}
    if disputed:
        return {"status": "DISPUTED", "entity_id": None,
                "claim_ids": sorted(set(disputed + [c["claim_id"] for c in eligible])),
                "reason": "DISPUTED_CLAIM_PRESENT"}
    if len(entity_ids) > 1:
        return {"status": "CONFLICT", "entity_id": None,
                "claim_ids": sorted(c["claim_id"] for c in eligible),
                "reason": "MULTIPLE_VERIFIED_ENTITY_TARGETS"}
    if len(entity_ids) == 1:
        entity_id = next(iter(entity_ids))
        return {"status": "ATTRIBUTED", "entity_id": entity_id,
                "claim_ids": sorted(c["claim_id"] for c in eligible),
                "reason": "VERIFIED_REVIEWED_TIME_VALID_CLAIM"}
    return {"status": "UNKNOWN", "entity_id": None, "claim_ids": [],
            "reason": sorted(rejected_reasons)[0] if rejected_reasons else "NO_MATCHING_CLAIM"}


def aggregate_entity_flows(movements, claims, start_time_utc, end_time_utc,
                           known_at_utc):
    """Aggregate external flows by attributed entity without counting internal transfers.

    Event and claim validity intervals are inclusive for attribution; movement
    event window is [start_time_utc, end_time_utc). Claims are point-in-time:
    recorded_at_utc must be <= known_at_utc. Missing validity bounds abstain.
    """
    start = _parse_utc(start_time_utc)
    end = _parse_utc(end_time_utc)
    cutoff = _parse_utc(known_at_utc)
    if start is None or end is None or cutoff is None or start >= end:
        raise ValueError("time bounds must be canonical UTC timestamps and start < end")
    if isinstance(movements, (str, bytes)) or isinstance(claims, (str, bytes)):
        raise ValueError("movements and claims must be collections of objects")
    try:
        movement_items = list(movements)
        claim_items = list(claims)
    except TypeError as exc:
        raise ValueError("movements and claims must be iterable") from exc
    claim_errors = validate_claim_collection(claim_items)
    if claim_errors:
        raise ValueError("invalid attribution claim collection: " + "; ".join(claim_errors))
    claim_index = {claim["claim_id"]: claim for claim in claim_items}
    seen_ids = set()
    aggregates = {}
    stats = {
        "movements_received": len(movement_items),
        "movements_in_window": 0,
        "movements_included": 0,
        "excluded": defaultdict(int),
        "internal_transfers_excluded_from_external_flows": 0,
        "attributed_endpoints": 0,
        "unknown_endpoints": 0,
        "conflicted_endpoints": 0,
    }

    def bucket(entity_id, asset_id, symbol):
        key = (entity_id, asset_id)
        if key not in aggregates:
            aggregates[key] = {
                "entity_id": entity_id, "asset_id": asset_id, "symbol": symbol,
                "external_incoming": Decimal("0"), "external_outgoing": Decimal("0"),
                "external_net": Decimal("0"), "internal_transfer_volume": Decimal("0"),
                "external_incoming_count": 0, "external_outgoing_count": 0,
                "internal_transfer_count": 0, "movement_ids": [],
                "unknown_counterparty_incoming": Decimal("0"),
                "unknown_counterparty_outgoing": Decimal("0"),
            }
        return aggregates[key]

    for index, movement in enumerate(movement_items):
        if not isinstance(movement, dict):
            raise ValueError(f"movements[{index}] must be an object")
        movement_id = movement.get("movement_id")
        if not isinstance(movement_id, str) or not movement_id:
            raise ValueError(f"movements[{index}] has invalid movement_id")
        if movement_id in seen_ids:
            raise ValueError(f"duplicate movement_id: {movement_id}")
        seen_ids.add(movement_id)
        if movement.get("contract_version") != "1.0.0":
            stats["excluded"]["unsupported_contract"] += 1
            continue
        if movement.get("quality_status") not in {"VALID", "PARTIAL"}:
            stats["excluded"]["quality"] += 1
            continue
        if movement.get("recorded_at_utc") is None or _parse_utc(movement.get("recorded_at_utc")) is None:
            stats["excluded"]["recorded_time_invalid"] += 1
            continue
        if _parse_utc(movement["recorded_at_utc"]) > cutoff:
            stats["excluded"]["not_known_at_cutoff"] += 1
            continue
        event_time = _parse_utc(movement.get("event_time_utc"))
        if event_time is None:
            stats["excluded"]["event_time_unknown"] += 1
            continue
        if not (start <= event_time < end):
            stats["excluded"]["outside_event_window"] += 1
            continue
        stats["movements_in_window"] += 1
        transfer = movement.get("transfer")
        asset = movement.get("asset")
        if not isinstance(transfer, dict) or not isinstance(asset, dict):
            stats["excluded"]["malformed_transfer"] += 1
            continue
        if transfer.get("movement_type") != "TRANSFER":
            stats["excluded"]["not_transfer"] += 1
            continue
        if transfer.get("confirmation_status") != "CONFIRMED":
            stats["excluded"]["unconfirmed"] += 1
            continue
        amount_text = transfer.get("amount")
        if not isinstance(amount_text, str) or AMOUNT_PATTERN.fullmatch(amount_text) is None:
            stats["excluded"]["amount_unknown_or_invalid"] += 1
            continue
        try:
            amount = Decimal(amount_text)
        except InvalidOperation:
            stats["excluded"]["amount_unknown_or_invalid"] += 1
            continue
        if amount <= 0:
            stats["excluded"]["amount_not_positive"] += 1
            continue
        asset_id = asset.get("asset_id")
        symbol = asset.get("symbol")
        network_id = asset.get("network_id")
        if (asset_id, symbol, network_id) not in {
            ("bitcoin:btc", "BTC", "bitcoin-mainnet"),
            ("ethereum:eth", "ETH", "eip155:1"),
        } or transfer.get("unit") != symbol:
            stats["excluded"]["unsupported_asset"] += 1
            continue

        source = _resolve_address(transfer.get("from_address"), network_id, event_time, cutoff, claim_index)
        target = _resolve_address(transfer.get("to_address"), network_id, event_time, cutoff, claim_index)
        for resolution in (source, target):
            if resolution["status"] == "ATTRIBUTED":
                stats["attributed_endpoints"] += 1
            elif resolution["status"] in {"CONFLICT", "DISPUTED"}:
                stats["conflicted_endpoints"] += 1
            else:
                stats["unknown_endpoints"] += 1

        source_entity = source["entity_id"] if source["status"] == "ATTRIBUTED" else None
        target_entity = target["entity_id"] if target["status"] == "ATTRIBUTED" else None
        if source_entity is not None and source_entity == target_entity:
            item = bucket(source_entity, asset_id, symbol)
            item["internal_transfer_volume"] += amount
            item["internal_transfer_count"] += 1
            item["movement_ids"].append(movement_id)
            stats["internal_transfers_excluded_from_external_flows"] += 1
            stats["movements_included"] += 1
            continue

        if source_entity is not None:
            item = bucket(source_entity, asset_id, symbol)
            item["external_outgoing"] += amount
            item["external_net"] -= amount
            item["external_outgoing_count"] += 1
            if target_entity is None:
                item["unknown_counterparty_outgoing"] += amount
            item["movement_ids"].append(movement_id)
        if target_entity is not None:
            item = bucket(target_entity, asset_id, symbol)
            item["external_incoming"] += amount
            item["external_net"] += amount
            item["external_incoming_count"] += 1
            if source_entity is None:
                item["unknown_counterparty_incoming"] += amount
            item["movement_ids"].append(movement_id)
        stats["movements_included"] += 1

    rows = []
    for key in sorted(aggregates):
        item = aggregates[key]
        item["movement_ids"] = sorted(set(item["movement_ids"]))
        rows.append(item)
    stats["excluded"] = dict(sorted(stats["excluded"].items()))
    return {
        "contract_version": "1.0.0",
        "event_window_utc": {"start_inclusive": start_time_utc, "end_exclusive": end_time_utc},
        "known_at_utc": known_at_utc,
        "attribution_policy": {
            "accepted_predicates": ["CONTROLLED_BY", "OPERATED_BY"],
            "required_epistemic_status": "VERIFIED",
            "required_review_status": "REVIEWED",
            "required_supporting_evidence": True,
            "counter_evidence_allowed": False,
            "validity_bounds_required": True,
            "labels_custody_association_and_inference_are_not_entity_control",
        },
        "entities": rows,
        "statistics": stats,
        "limitations": [
            "Entity flows are transfer activity, not executed trades or beneficial ownership proof.",
            "Internal transfers are excluded from external net flow but reported separately.",
            "Unknown or conflicted endpoints are not assigned to an entity.",
            "The output is not an absolute balance or exposure snapshot.",
            "Accumulation/distribution is not classified by this function.",
            "Coverage is limited to the supplied movement records and claims.",
        ],
    }
