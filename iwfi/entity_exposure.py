"""Historical exposure metrics from point-in-time controlled-address snapshots.

Totals are emitted only when the address inventory and every address attribution
are explicitly complete. Otherwise only known-address exposure is reported.
"""
from __future__ import annotations

from collections import defaultdict
from datetime import datetime
from fractions import Fraction
import re

from iwfi.attribution_integrity import validate_claim_collection


UTC_PATTERN = re.compile(r"[0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{2}:[0-9]{2}:[0-9]{2}Z")
HASH_PATTERN = re.compile(r"(?:0x)?[0-9a-fA-F]{64}")


def _parse_utc(value):
    if not isinstance(value, str) or UTC_PATTERN.fullmatch(value) is None:
        return None
    try:
        return datetime.fromisoformat(value[:-1] + "+00:00")
    except ValueError:
        return None


def _resolve_control(address, network_id, snapshot_time, known_at, claim_index):
    eligible, disputed = [], []
    for claim in claim_index.values():
        subject = claim.get("subject")
        if not isinstance(subject, dict):
            continue
        if (subject.get("subject_type") != "ADDRESS"
                or subject.get("subject_id") != address
                or subject.get("network_id") != network_id):
            continue
        recorded = _parse_utc(claim.get("recorded_at_utc"))
        valid_from = _parse_utc(claim.get("valid_from_utc"))
        valid_to = _parse_utc(claim.get("valid_to_utc"))
        review = claim.get("review")
        reviewed_at = _parse_utc(review.get("reviewed_at_utc")) if isinstance(review, dict) else None
        if (recorded is None or valid_from is None or valid_to is None
                or reviewed_at is None or recorded > known_at or reviewed_at > known_at
                or valid_from > valid_to or not (valid_from <= snapshot_time <= valid_to)):
            continue
        if claim.get("epistemic_status") == "DISPUTED" or claim.get("review_status") == "DISPUTED":
            disputed.append(claim["claim_id"])
            continue
        if (claim.get("epistemic_status") != "VERIFIED"
                or claim.get("review_status") != "REVIEWED"
                or claim.get("predicate") != "CONTROLLED_BY"
                or claim.get("counter_evidence")
                or not claim.get("supporting_evidence)):
            continue
        target = claim.get("object")
        if not isinstance(target, dict) or target.get("object_type") != "ENTITY":
            continue
        entity_id = target.get("object_id")
        if isinstance(entity_id, str) and entity_id:
            eligible.append((claim["claim_id"], entity_id))
    if disputed:
        return {"status": "DISPUTED", "entity_id": None, "claim_ids": sorted(set(disputed))}
    entities = {entity for _, entity in eligible}
    if len(entities) > 1:
        return {"status": "CONFLICT", "entity_id": None,
                "claim_ids": sorted(claim_id for claim_id, _ in eligible)}
    if len(entities) == 1:
        entity_id = next(iter(entities))
        return {"status": "ATTRIBUTED", "entity_id": entity_id,
                "claim_ids": sorted(claim_id for claim_id, _ in eligible)}
    return {"status": "UNKNOWN", "entity_id": None, "claim_ids": []}


def aggregate_entity_exposure_history(snapshots, claims, known_at_utc):
    """Aggregate address balances by entity and calculate comparable snapshot deltas.

    A complete entity total requires a reviewed complete inventory and an
    admissible CONTROLLED_BY claim for every listed address at snapshot time.
    """
    cutoff = _parse_utc(known_at_utc)
    if cutoff is None:
        raise ValueError("known_at_utc must be a canonical UTC timestamp")
    if isinstance(snapshots, (str, bytes)) or isinstance(claims, (str, bytes)):
        raise ValueError("snapshots and claims must be collections")
    try:
        snapshot_items, claim_items = list(snapshots), list(claims)
    except TypeError as exc:
        raise ValueError("snapshots and claims must be iterable") from exc
    claim_errors = validate_claim_collection(claim_items)
    if claim_errors:
        raise ValueError("invalid attribution claim collection: " + "; ".join(claim_errors))
    claim_index = {claim["claim_id"]: claim for claim in claim_items}

    seen_ids = set()
    grouped = defaultdict(list)
    excluded = defaultdict(int)

    for index, snapshot in enumerate(snapshot_items):
        if not isinstance(snapshot, dict):
            raise ValueError(f"snapshots[{index}] must be an object")
        batch_id = snapshot.get("snapshot_batch_id")
        if not isinstance(batch_id, str) or not batch_id:
            raise ValueError(f"snapshots[{index}] has invalid snapshot_batch_id")
        if batch_id in seen_ids:
            raise ValueError(f"duplicate snapshot_batch_id: {batch_id}")
        seen_ids.add(batch_id)

        scope_entity_id = snapshot.get("scope_entity_id")
        if not isinstance(scope_entity_id, str) or not scope_entity_id:
            excluded["invalid_scope_entity_id"] += 1
            continue
        asset_id, network_id = snapshot.get("asset_id"), snapshot.get("network_id")
        expected = {
            "bitcoin:btc": ("bitcoin-mainnet", "satoshi"),
            "ethereum:eth": ("eip155:1", "wei"),
        }.get(asset_id)
        if expected is None or expected[0] != network_id:
            excluded["unsupported_asset_or_network"] += 1
            continue
        snapshot_time = _parse_utc(snapshot.get("snapshot_time_utc"))
        recorded = _parse_utc(snapshot.get("recorded_at_utc"))
        if snapshot_time is None or recorded is None:
            excluded["invalid_timestamp"] += 1
            continue
        if recorded > cutoff:
            excluded["not_known_at_cutoff"] += 1
            continue
        if (snapshot.get("canonicality") != "CANONICAL"
                or snapshot.get("confirmation_status") != "CONFIRMED"):
            excluded["not_canonical_and_confirmed"] += 1
            continue
        height, block_hash = snapshot.get("block_height"), snapshot.get("block_hash")
        addresses = snapshot.get("addresses")
        coverage = snapshot.get("inventory_coverage")
        if (not isinstance(height, int) or isinstance(height, bool) or height < 0
                or not isinstance(block_hash, str) or HASH_PATTERN.fullmatch(block_hash) is None
                or not isinstance(addresses, list) or not addresses
                or not isinstance(coverage, dict)):
            excluded["malformed_snapshot"] += 1
            continue

        seen_addresses = set()
        known_balance = 0
        attributed_count = 0
        unresolved_count = 0
        address_set = set()
        claim_ids = set()
        address_resolutions = []
        valid_records = True
        for record in addresses:
            if not isinstance(record, dict):
                valid_records = False
                break
            address = record.get("address")
            amount = record.get("balance_atomic")
            unit = record.get("unit")
            observation_id = record.get("source_observation_id")
            if (not isinstance(address, str) or not address
                    or address in seen_addresses
                    or not isinstance(amount, int) or isinstance(amount, bool) or amount < 0
                    or unit != expected[1]
                    or not isinstance(observation_id, str) or not observation_id):
                valid_records = False
                break
            seen_addresses.add(address)
            resolution = _resolve_control(address, network_id, snapshot_time, cutoff, claim_index)
            address_resolutions.append({
                "address": address,
                "balance_atomic": amount,
                "unit": unit,
                "source_observation_id": observation_id,
                "resolution_status": resolution["status"],
                "resolved_entity_id": resolution["entity_id"],
                "claim_ids": resolution["claim_ids"],
            })
            if resolution["status"] == "ATTRIBUTED" and resolution["entity_id"] == scope_entity_id:
                known_balance += amount
                attributed_count += 1
                address_set.add(address)
                claim_ids.update(resolution["claim_ids"])
            else:
                unresolved_count += 1
        if not valid_records:
            excluded["invalid_address_balance_record"] += 1
            continue

        expected_count = coverage.get("expected_address_count")
        observed_count = coverage.get("observed_address_count")
        inventory_unresolved = coverage.get("unresolved_address_count")
        reviewed_at = _parse_utc(coverage.get("reviewed_at_utc"))
        inventory_complete = (
            coverage.get("status") == "COMPLETE"
            and coverage.get("review_status") == "REVIEWED"
            and isinstance(coverage.get("evidence_ref"), str)
            and bool(coverage.get("evidence_ref"))
            and isinstance(coverage.get("reviewer_id"), str)
            and bool(coverage.get("reviewer_id"))
            and reviewed_at is not None
            and reviewed_at <= cutoff
            and isinstance(expected_count, int)
            and not isinstance(expected_count, bool)
            and isinstance(observed_count, int)
            and not isinstance(observed_count, bool)
            and isinstance(inventory_unresolved, int)
            and not isinstance(inventory_unresolved, bool)
            and expected_count == len(addresses)
            and observed_count == len(addresses)
            and inventory_unresolved == 0
            and unresolved_count == 0
            and attributed_count == len(addresses)
        )
        if inventory_complete:
            coverage_status = "COMPLETE"
            total_exposure = known_balance
        elif coverage.get("status") == "UNKNOWN":
            coverage_status = "UNKNOWN"
            total_exposure = None
        else:
            coverage_status = "PARTIAL"
            total_exposure = None

        grouped[(scope_entity_id, asset_id, expected[1])].append({
            "snapshot_batch_id": batch_id,
            "entity_id": scope_entity_id,
            "asset_id": asset_id,
            "network_id": network_id,
            "unit": expected[1],
            "snapshot_time_utc": snapshot["snapshot_time_utc"],
            "block_height": height,
            "block_hash": block_hash,
            "known_controlled_address_exposure_atomic": known_balance,
            "total_controlled_address_exposure_atomic": total_exposure,
            "coverage_status": coverage_status,
            "addresses_observed": len(addresses),
            "addresses_attributed": attributed_count,
            "addresses_unresolved": unresolved_count,
            "inventory_coverage": {
                "declared_status": coverage.get("status"),
                "computed_status": coverage_status,
                "expected_address_count": expected_count,
                "observed_address_count": observed_count,
                "declared_unresolved_address_count": inventory_unresolved,
                "computed_unresolved_address_count": unresolved_count,
                "evidence_ref": coverage.get("evidence_ref"),
                "review_status": coverage.get("review_status"),
                "reviewer_id": coverage.get("reviewer_id"),
                "reviewed_at_utc": coverage.get("reviewed_at_utc"),
            },
            "address_resolutions": address_resolutions,
            "claim_ids": sorted(claim_ids),
            "_address_set": address_set,
        })

    histories = []
    for key in sorted(grouped):
        rows = sorted(grouped[key], key=lambda row: (row["snapshot_time_utc"], row["snapshot_batch_id"]))
        seen_times = set()
        for row in rows:
            if row["snapshot_time_utc"] in seen_times:
                raise ValueError("duplicate snapshot time for same entity and asset")
            seen_times.add(row["snapshot_time_utc"])
        changes = []
        for previous, current in zip(rows, rows[1:]):
            same_address_set = previous["_address_set"] == current["_address_set"]
            known_delta = (
                current["known_controlled_address_exposure_atomic"] - previous["known_controlled_address_exposure_atomic"]
                if same_address_set and previous["_address_set"] and previous["coverage_status"] != "UNKNOWN"
                and current["coverage_status"] != "UNKNOWN" else None
            )
            total_delta = None
            relative_change = None
            direction = "NOT_CLASSIFIED"
            classification_status = "INCOMPLETE_COVERAGE"
            if (previous["coverage_status"] == "COMPLETE"
                    and current["coverage_status"] == "COMPLETE"):
                total_delta = current["total_controlled_address_exposure_atomic"] - previous["total_controlled_address_exposure_atomic"]
                if previous["total_controlled_address_exposure_atomic"] > 0:
                    relative_change = str(Fraction(total_delta, previous["total_controlled_address_exposure_atomic"]))
                direction = (
                    "NET_BALANCE_INCREASE" if total_delta > 0
                    else "NET_BALANCE_DECREASE" if total_delta < 0
                    else "FLAT"
                )
                classification_status = "NOT_CALIBRATED"
            changes.append({
                "from_snapshot_batch_id": previous["snapshot_batch_id"],
                "to_snapshot_batch_id": current["snapshot_batch_id"],
                "known_address_delta_atomic": known_delta,
                "total_controlled_address_delta_atomic": total_delta,
                "relative_controlled_address_change": relative_change,
                "candidate_direction": direction,
                "classification_status": classification_status,
                "same_attributed_address_set": same_address_set,
                "interpretation": "Net balance change only; not proof of purchases, sales, intent, or market accumulation/distribution.",
            })
        for row in rows:
            row.pop("_address_set", None)
        histories.append({
            "entity_id": key[0],
            "asset_id": key[1],
            "unit": key[2],
            "snapshots": rows,
            "changes": changes,
        })

    return {
        "contract_version": "1.0.0",
        "exposure_basis": "CONTROLLED_ADDRESS_BALANCES_ONLY",
        "known_at_utc": known_at_utc,
        "histories": histories,
        "excluded": dict(sorted(excluded.items())),
        "limitations": [
            "Known-address exposure is only the sum of addresses with admissible control claims.",
            "Total entity exposure is emitted only with reviewed complete inventory and complete address attribution.",
            "CONTROLLED_BY proves address control, not beneficial ownership or treasury ownership.",
            "Custodial customer assets must not be interpreted as the custodian's proprietary holdings.",
            "Candidate direction is a descriptive net balance change and is always NOT_CALIBRATED.",
            "No buy/sell, accumulation/distribution intent, or causal market signal is inferred.",
            "Snapshots and source observations supplied by the caller define the available coverage.",
        ],
    }
