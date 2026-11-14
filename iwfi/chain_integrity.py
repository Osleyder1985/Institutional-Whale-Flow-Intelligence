"""Pure, deterministic BTC/ETH chain-inclusion assessment.

Evaluates immutable observations only. No RPC, network access, persistence,
polling, or mutation of supplied records is performed.
"""
import hashlib
import json
from copy import deepcopy
from datetime import datetime, timedelta


SUPPORTED_NETWORKS = {"bitcoin-mainnet", "eip155:1"}
POLICY_VERSION = "2.0.0"
ASSESSMENTS = {
    "OBSERVED", "INCLUDED", "CANONICALITY_UNRESOLVED",
    "NOT_CANONICAL", "REOBSERVED", "FINALIZED", "UNKNOWN",
}


def _source(item):
    source = item.get("source")
    if not isinstance(source, dict):
        raise ValueError("every observation requires a source object")
    source_id = source.get("source_id")
    view_id = source.get("view_id")
    if not isinstance(source_id, str) or not source_id.strip():
        raise ValueError("source.source_id must be a non-empty string")
    if view_id is not None and (not isinstance(view_id, str) or not view_id.strip()):
        raise ValueError("source.view_id must be null or a non-empty string")
    return source_id, view_id


def _later(left, right):
    # Parse UTC timestamps instead of relying on lexical order: optional
    # fractional seconds make otherwise valid ISO-8601 strings non-sortable.
    a, b = left.get("observed_at_utc"), right.get("observed_at_utc")
    if not isinstance(a, str) or not isinstance(b, str):
        return False
    try:
        earlier = datetime.fromisoformat(a.replace("Z", "+00:00"))
        later = datetime.fromisoformat(b.replace("Z", "+00:00"))
    except ValueError:
        return False
    return earlier.utcoffset() == later.utcoffset() == timedelta(0) and later > earlier


def _fingerprint(network_id, transaction_id, records, status, reason):
    canonical_evidence = sorted(
        (deepcopy(item) for item in records),
        key=lambda item: item["observation_id"],
    )
    payload = {
        "policy_version": POLICY_VERSION,
        "network_id": network_id,
        "transaction_id": transaction_id,
        "evidence": canonical_evidence,
        "status": status,
        "reason_code": reason,
    }
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def assess_chain_observations(observations, supersedes_assessment_id=None):
    """Assess one transaction's inclusion history without conflating providers.

    REOBSERVED requires a strictly later ACTIVE observation from the same
    source and the same explicitly identified source view as the NOT_ACTIVE
    observation. Cross-source disagreement remains unresolved.

    Ethereum FINALIZED requires an independent finalized checkpoint plus
    positive ACTIVE evidence for the exact inclusion block from the same
    source view. Height comparison alone is never sufficient.
    """
    if supersedes_assessment_id is not None and (
        not isinstance(supersedes_assessment_id, str) or not supersedes_assessment_id.strip()
    ):
        raise ValueError("supersedes_assessment_id must be null or a non-empty string")
    if not isinstance(observations, (list, tuple)) or not observations:
        return {
            "status": "UNKNOWN", "network_id": None, "transaction_id": None,
            "policy_version": POLICY_VERSION, "supersedes_assessment_id": supersedes_assessment_id,
            "evidence_observation_ids": [], "inclusion_keys": [], "movement_event_locators": [],
            "reason_code": "NO_ADMISSIBLE_OBSERVATIONS",
            "assessment_fingerprint": _fingerprint(None, None, [], "UNKNOWN", "NO_ADMISSIBLE_OBSERVATIONS"),
        }

    records = deepcopy(list(observations))
    if any(not isinstance(item, dict) for item in records):
        raise ValueError("every chain observation must be an object")

    if any(item.get("network_id") not in SUPPORTED_NETWORKS for item in records):
        raise ValueError("observations must belong to exactly one supported network")
    networks = {item.get("network_id") for item in records}
    if len(networks) != 1:
        raise ValueError("observations must belong to exactly one supported network")
    network_id = next(iter(networks))

    observation_ids = [item.get("observation_id") for item in records]
    if any(not isinstance(value, str) or not value.strip() for value in observation_ids):
        raise ValueError("every observation requires a non-empty observation_id")
    if len(observation_ids) != len(set(observation_ids)):
        raise ValueError("observation_id values must be unique")

    for item in records:
        _source(item)
        if not isinstance(item.get("observed_at_utc"), str) or not item["observed_at_utc"].endswith("Z"):
            raise ValueError("observed_at_utc must be a UTC timestamp ending in Z")

    transaction_records = [item for item in records if item.get("observation_kind") != "FINALITY_CHECKPOINT"]
    checkpoints = [item for item in records if item.get("observation_kind") == "FINALITY_CHECKPOINT"]
    if not transaction_records:
        raise ValueError("at least one transaction observation is required")
    transaction_ids = {item.get("transaction_id") for item in transaction_records}
    if len(transaction_ids) != 1 or not isinstance(next(iter(transaction_ids)), str) or not next(iter(transaction_ids)).strip():
        raise ValueError("transaction observations must refer to exactly one transaction")
    transaction_id = next(iter(transaction_ids))
    if any(item.get("transaction_id") not in (None, transaction_id) for item in checkpoints):
        raise ValueError("finality checkpoints must be independent of transaction identity")

    evidence_ids = sorted(observation_ids)
    inclusions = [
        item for item in transaction_records
        if item.get("observation_kind") == "BLOCK_INCLUDED"
        and isinstance(item.get("inclusion"), dict)
    ]
    mempool = [item for item in transaction_records if item.get("observation_kind") == "MEMPOOL_SEEN"]

    def inclusion_key(item):
        inclusion = item["inclusion"]
        locator = item.get("event_locator")
        return (
            inclusion.get("block_height"), inclusion.get("block_hash"),
            inclusion.get("transaction_index"),
            locator.get("kind") if isinstance(locator, dict) else None,
            locator.get("value") if isinstance(locator, dict) else None,
        )

    keys = sorted(
        {inclusion_key(item) for item in inclusions},
        key=lambda x: (x[0], x[1], -1 if x[2] is None else x[2], x[3] or "", x[4] or ""),
    )
    serialized_keys = [
        {"block_height": h, "block_hash": bh, "transaction_index": ti,
         "event_locator": ({"kind": lk, "value": lv} if lk is not None else None)}
        for h, bh, ti, lk, lv in keys
    ]
    movement_locators = sorted({
        (item["event_locator"].get("kind"), item["event_locator"].get("value"))
        for item in transaction_records if isinstance(item.get("event_locator"), dict)
    })
    serialized_locators = [{"kind": kind, "value": value} for kind, value in movement_locators]

    def result(status, reason):
        return {
            "status": status,
            "network_id": network_id,
            "transaction_id": transaction_id,
            "policy_version": POLICY_VERSION,
            "supersedes_assessment_id": supersedes_assessment_id,
            "evidence_observation_ids": evidence_ids,
            "inclusion_keys": serialized_keys,
            "movement_event_locators": serialized_locators,
            "reason_code": reason,
            "assessment_fingerprint": _fingerprint(network_id, transaction_id, records, status, reason),
        }

    if not inclusions:
        if mempool:
            return result("OBSERVED", "MEMPOOL_SEEN_WITHOUT_BLOCK_INCLUSION")
        return result("UNKNOWN", "NO_BLOCK_OR_MEMPOOL_EVIDENCE")

    block_records = [
        item for item in transaction_records
        if item.get("observation_kind") in {"BLOCK_INCLUDED", "BLOCK_STATUS"}
        and isinstance(item.get("inclusion"), dict)
    ]
    by_block = {}
    for item in block_records:
        inclusion = item["inclusion"]
        key = (inclusion.get("block_height"), inclusion.get("block_hash"))
        by_block.setdefault(key, []).append(item)

    # A disagreement about the same block is unresolved, regardless of order.
    for block_items in by_block.values():
        statuses = {item.get("source_asserted_chain_status") for item in block_items}
        if "ACTIVE" in statuses and "NOT_ACTIVE" in statuses:
            return result("CANONICALITY_UNRESOLVED", "CONFLICTING_STATUS_FOR_SAME_BLOCK")

    if len(by_block) > 1:
        old_not_active = [
            item for item in block_records
            if item.get("source_asserted_chain_status") == "NOT_ACTIVE"
        ]
        later_active = [
            item for item in block_records
            if item.get("source_asserted_chain_status") == "ACTIVE"
        ]
        ordered_same_view = any(
            _source(old)[0] == _source(new)[0]
            and _source(old)[1] is not None
            and _source(old)[1] == _source(new)[1]
            and _later(old, new)
            and (old["inclusion"].get("block_height"), old["inclusion"].get("block_hash"))
                != (new["inclusion"].get("block_height"), new["inclusion"].get("block_hash"))
            for old in old_not_active for new in later_active
        )
        if ordered_same_view:
            return result("REOBSERVED", "SAME_SOURCE_VIEW_PRIOR_NONCANONICAL_THEN_LATER_ACTIVE_INCLUSION")
        return result("CANONICALITY_UNRESOLVED", "MULTIPLE_INCLUSIONS_WITHOUT_PROVEN_SAME_VIEW_REORG_SEQUENCE")

    (block_height, block_hash), block_items = next(iter(by_block.items()))
    statuses = {item.get("source_asserted_chain_status") for item in block_items}
    active_items = [item for item in block_items if item.get("source_asserted_chain_status") == "ACTIVE"]
    not_active_items = [item for item in block_items if item.get("source_asserted_chain_status") == "NOT_ACTIVE"]
    if not_active_items:
        return result("NOT_CANONICAL", "POSITIVE_EVIDENCE_BLOCK_NOT_ACTIVE")
    if not active_items:
        return result("CANONICALITY_UNRESOLVED", "INCLUSION_WITHOUT_POSITIVE_CANONICAL_MEMBERSHIP")

    if network_id == "eip155:1":
        for checkpoint in checkpoints:
            checkpoint_data = checkpoint.get("checkpoint")
            if not isinstance(checkpoint_data, dict) or checkpoint.get("source_asserted_head_tag") != "finalized":
                continue
            checkpoint_height = checkpoint_data.get("block_height")
            checkpoint_hash = checkpoint_data.get("block_hash")
            cp_source, cp_view = _source(checkpoint)
            for active in active_items:
                active_source, active_view = _source(active)
                active_height = active["inclusion"].get("block_height")
                if (
                    cp_source == active_source
                    and cp_view is not None and cp_view == active_view
                    and isinstance(checkpoint_height, int) and not isinstance(checkpoint_height, bool)
                    and isinstance(active_height, int) and checkpoint_height >= active_height
                    and isinstance(checkpoint_hash, str) and checkpoint_hash
                    and _later(active, checkpoint)
                ):
                    return result("FINALIZED", "SAME_SOURCE_VIEW_ACTIVE_INCLUSION_COVERED_BY_LATER_FINALIZED_CHECKPOINT")

    return result("INCLUDED", "POSITIVE_CANONICAL_MEMBERSHIP_WITHOUT_ETHEREUM_FINALITY_PROOF")
