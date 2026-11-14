"""Point-in-time address flow deltas from normalized BTC/ETH movements."""
from __future__ import annotations

from collections import defaultdict
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
import re
from typing import Any, Iterable

_ASSETS = {
    "bitcoin:btc": ("BTC", "bitcoin-mainnet"),
    "ethereum:eth": ("ETH", "eip155:1"),
}
_UTC = re.compile(r"^[0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{2}:[0-9]{2}:[0-9]{2}Z$")
_AMOUNT = re.compile(r"^(?:0|[1-9][0-9]*)(?:\.[0-9]+)?$")


class AddressFlowAnalyticsError(ValueError):
    """Invalid analysis window, movement identity, or canonical input."""


def _parse_utc(value: Any, field: str) -> datetime:
    if not isinstance(value, str) or _UTC.fullmatch(value) is None:
        raise AddressFlowAnalyticsError(f"{field} must be a UTC timestamp ending in Z")
    try:
        return datetime.strptime(value, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)
    except ValueError as exc:
        raise AddressFlowAnalyticsError(f"{field} is not a valid UTC timestamp") from exc


def _decimal_amount(value: Any, movement_id: str) -> Decimal | None:
    if value is None:
        return None
    if not isinstance(value, str) or _AMOUNT.fullmatch(value) is None:
        raise AddressFlowAnalyticsError(f"{movement_id}: amount is not a canonical decimal string")
    try:
        amount = Decimal(value)
    except InvalidOperation as exc:
        raise AddressFlowAnalyticsError(f"{movement_id}: invalid amount") from exc
    if not amount.is_finite():
        raise AddressFlowAnalyticsError(f"{movement_id}: amount must be finite")
    return amount


def _address_key(address: str, network_id: str) -> str:
    # EVM addresses are case-insensitive; Bitcoin Base58 addresses are not.
    return address.lower() if network_id == "eip155:1" else address


def summarize_address_flows(
    movements: Iterable[dict[str, Any]],
    start_time_utc: str,
    end_time_utc: str,
    known_at_utc: str,
) -> dict[str, Any]:
    """Aggregate confirmed address flows for [start, end), as known at cutoff.

    The net flow delta is not a wallet balance, trade, ownership, or intent claim.
    """
    start = _parse_utc(start_time_utc, "start_time_utc")
    end = _parse_utc(end_time_utc, "end_time_utc")
    cutoff = _parse_utc(known_at_utc, "known_at_utc")
    if start >= end:
        raise AddressFlowAnalyticsError("analysis window must satisfy start_time_utc < end_time_utc")
    try:
        rows = list(movements)
    except TypeError as exc:
        raise AddressFlowAnalyticsError("movements must be an iterable") from exc

    seen_ids: set[str] = set()
    buckets: dict[tuple[str, str], dict[str, Any]] = {}
    excluded: defaultdict[str, int] = defaultdict(int)
    within_window = known_by_cutoff = eligible_movements = 0

    for index, movement in enumerate(rows):
        if not isinstance(movement, dict):
            raise AddressFlowAnalyticsError(f"movements[{index}] must be an object")
        if movement.get("contract_version") != "1.0.0":
            raise AddressFlowAnalyticsError(f"movements[{index}]: unsupported contract_version")
        movement_id = movement.get("movement_id")
        if not isinstance(movement_id, str) or not movement_id:
            raise AddressFlowAnalyticsError(f"movements[{index}] has no movement_id")
        if movement_id in seen_ids:
            raise AddressFlowAnalyticsError(f"duplicate movement_id: {movement_id}")
        seen_ids.add(movement_id)

        asset, transfer = movement.get("asset"), movement.get("transfer")
        if not isinstance(asset, dict) or not isinstance(transfer, dict):
            raise AddressFlowAnalyticsError(f"{movement_id}: asset and transfer must be objects")
        asset_id = asset.get("asset_id")
        expected = _ASSETS.get(asset_id)
        if expected is None or (asset.get("symbol"), asset.get("network_id")) != expected:
            raise AddressFlowAnalyticsError(f"{movement_id}: unsupported or inconsistent asset identity")
        if transfer.get("movement_type") != "TRANSFER" or transfer.get("unit") != expected[0]:
            raise AddressFlowAnalyticsError(f"{movement_id}: movement type or unit is inconsistent")

        recorded = _parse_utc(movement.get("recorded_at_utc"), f"{movement_id}.recorded_at_utc")
        event_value = movement.get("event_time_utc")
        if event_value is None:
            excluded["event_time_unknown"] += 1
            continue
        event = _parse_utc(event_value, f"{movement_id}.event_time_utc")
        if not start <= event < end:
            continue
        within_window += 1
        if recorded > cutoff:
            excluded["not_known_at_cutoff"] += 1
            continue
        known_by_cutoff += 1

        if movement.get("quality_status") not in {"VALID", "PARTIAL"}:
            excluded["quality_not_admissible"] += 1
            continue
        if transfer.get("confirmation_status") != "CONFIRMED":
            excluded["confirmation_not_confirmed"] += 1
            continue
        amount = _decimal_amount(transfer.get("amount"), movement_id)
        if amount is None:
            excluded["amount_unknown"] += 1
            continue

        sender, receiver = transfer.get("from_address"), transfer.get("to_address")
        if sender is not None and (not isinstance(sender, str) or not sender):
            raise AddressFlowAnalyticsError(f"{movement_id}: invalid from_address")
        if receiver is not None and (not isinstance(receiver, str) or not receiver):
            raise AddressFlowAnalyticsError(f"{movement_id}: invalid to_address")
        if sender is None and receiver is None:
            excluded["both_addresses_unknown"] += 1
            continue

        eligible_movements += 1
        network_id = expected[1]

        def bucket_for(address: str) -> dict[str, Any]:
            key = (asset_id, _address_key(address, network_id))
            if key not in buckets:
                buckets[key] = {
                    "asset_id": asset_id, "symbol": expected[0], "network_id": network_id,
                    "address": _address_key(address, network_id),
                    "incoming": Decimal("0"), "outgoing": Decimal("0"),
                    "incoming_count": 0, "outgoing_count": 0,
                }
            return buckets[key]

        if sender is not None:
            bucket = bucket_for(sender)
            bucket["outgoing"] += amount
            bucket["outgoing_count"] += 1
        else:
            excluded["from_address_unknown"] += 1
        if receiver is not None:
            bucket = bucket_for(receiver)
            bucket["incoming"] += amount
            bucket["incoming_count"] += 1
        else:
            excluded["to_address_unknown"] += 1

    addresses = []
    for key in sorted(buckets):
        item = buckets[key]
        addresses.append({
            "asset_id": item["asset_id"],
            "symbol": item["symbol"],
            "network_id": item["network_id"],
            "address": item["address"],
            "incoming_amount": format(item["incoming"], "f"),
            "outgoing_amount": format(item["outgoing"], "f"),
            "net_flow_delta": format(item["incoming"] - item["outgoing"], "f"),
            "incoming_movement_count": item["incoming_count"],
            "outgoing_movement_count": item["outgoing_count"],
        })

    return {
        "contract_version": "1.0.0",
        "metric": "CONFIRMED_ADDRESS_TRANSFER_FLOW_DELTA",
        "analysis_window": {
            "start_time_utc_inclusive": start_time_utc,
            "end_time_utc_exclusive": end_time_utc,
        },
        "known_at_utc": known_at_utc,
        "movement_counts": {
            "received": len(rows),
            "within_event_window": within_window,
            "known_by_cutoff": known_by_cutoff,
            "included_confirmed_movements": eligible_movements,
            "excluded_by_reason": dict(sorted(excluded.items())),
        },
        "addresses": addresses,
        "limitations": [
            "net_flow_delta_is_not_a_wallet_balance",
            "transfers_are_not_executed_trades",
            "address_identity_and_beneficial_ownership_are_not_inferred",
            "no_wallet_clustering_or_internal_entity_transfer_elimination",
            "coverage_is_limited_to_supplied_movement_records",
            "missing_values_are_excluded_not_zero_filled",
        ],
    }
