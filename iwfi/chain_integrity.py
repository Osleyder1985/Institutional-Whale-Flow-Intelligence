"""Pure, deterministic BTC/ETH chain-inclusion assessment.

This module evaluates supplied immutable observations only. It performs no RPC,
network access, persistence, polling, or mutation of its inputs.
"""
from copy import deepcopy


SUPPORTED_NETWORKS = {"bitcoin-mainnet", "eip155:1"}
ASSESSMENTS = {
    "OBSERVED", "INCLUDED", "CANONICALITY_UNRESOLVED",
    "NOT_CANONICAL", "REOBSERVED", "FINALIZED", "UNKNOWN",
}


def assess_chain_observations(observations):
    """Return a deterministic assessment for one transaction's observations.

    Source assertions are never silently reconciled. Distinct inclusion blocks
    are REOBSERVED only when there is positive evidence that an earlier block
    is not active and another block is active; otherwise the result is unresolved.
    """
    if not isinstance(observations, (list, tuple)) or not observations:
        return {
            "status": "UNKNOWN",
            "network_id": None,
            "transaction_id": None,
            "evidence_observation_ids": [],
            "inclusion_keys": [],
            "reason_code": "NO_ADMISSIBLE_OBSERVATIONS",
        }

    records = deepcopy(list(observations))
    if any(not isinstance(item, dict) for item in records):
        raise ValueError("every chain observation must be an object")

    network_ids = {item.get("network_id") for item in records}
    transaction_ids = {item.get("transaction_id") for item in records}
    if len(network_ids) != 1 or next(iter(network_ids)) not in SUPPORTED_NETWORKS:
        raise ValueError("observations must belong to exactly one supported network")
    if len(transaction_ids) != 1 or not next(iter(transaction_ids)):
        raise ValueError("observations must refer to exactly one transaction")

    network_id = next(iter(network_ids))
    transaction_id = next(iter(transaction_ids))
    observation_ids = [item.get("observation_id") for item in records]
    if any(not isinstance(value, str) or not value for value in observation_ids):
        raise ValueError("every observation requires a non-empty observation_id")
    if len(observation_ids) != len(set(observation_ids)):
        raise ValueError("observation_id values must be unique")

    evidence_ids = sorted(observation_ids)
    inclusions = [
        item for item in records
        if item.get("observation_kind") == "BLOCK_INCLUDED"
        and isinstance(item.get("inclusion"), dict)
    ]
    mempool = [item for item in records if item.get("observation_kind") == "MEMPOOL_SEEN"]

    def inclusion_key(item):
        inclusion = item["inclusion"]
        return (
            inclusion.get("block_height"),
            inclusion.get("block_hash"),
            inclusion.get("transaction_index"),
        )

    keys = sorted({inclusion_key(item) for item in inclusions}, key=lambda x: (x[0], x[1], -1 if x[2] is None else x[2]))
    serialized_keys = [
        {"block_height": height, "block_hash": block_hash, "transaction_index": index}
        for height, block_hash, index in keys
    ]

    def result(status, reason):
        return {
            "status": status,
            "network_id": network_id,
            "transaction_id": transaction_id,
            "evidence_observation_ids": evidence_ids,
            "inclusion_keys": serialized_keys,
            "reason_code": reason,
        }

    if not inclusions:
        if mempool:
            return result("OBSERVED", "MEMPOOL_SEEN_WITHOUT_BLOCK_INCLUSION")
        return result("UNKNOWN", "NO_BLOCK_OR_MEMPOOL_EVIDENCE")

    blocks = {}
    block_records = [
        item for item in records
        if item.get("observation_kind") in {"BLOCK_INCLUDED", "BLOCK_STATUS"}
        and isinstance(item.get("inclusion"), dict)
    ]
    for item in block_records:
        block_hash = item["inclusion"].get("block_hash")
        blocks.setdefault(block_hash, []).append(item)

    if len(blocks) > 1:
        statuses = {
            block_hash: {item.get("source_asserted_chain_status") for item in block_items}
            for block_hash, block_items in blocks.items()
        }
        contradictory_same_block = any(
            "ACTIVE" in values and "NOT_ACTIVE" in values for values in statuses.values()
        )
        old_not_active = [
            item for item in block_records
            if item.get("source_asserted_chain_status") == "NOT_ACTIVE"
        ]
        later_active = [
            item for item in block_records
            if item.get("source_asserted_chain_status") == "ACTIVE"
        ]
        has_ordered_reinclusion = (
            old_not_active and later_active
            and max(item.get("observed_at_utc", "") for item in later_active)
            > min(item.get("observed_at_utc", "") for item in old_not_active)
        )
        if has_ordered_reinclusion and not contradictory_same_block:
            return result("REOBSERVED", "PRIOR_NONCANONICAL_BLOCK_AND_LATER_ACTIVE_INCLUSION")
        return result("CANONICALITY_UNRESOLVED", "MULTIPLE_BLOCK_INCLUSIONS_WITHOUT_CLEAR_REORG_SEQUENCE")

    block_hash, block_items = next(iter(blocks.items()))
    block_statuses = {item.get("source_asserted_chain_status") for item in block_items}
    if "ACTIVE" in block_statuses and "NOT_ACTIVE" in block_statuses:
        return result("CANONICALITY_UNRESOLVED", "SOURCES_CONFLICT_ON_SAME_BLOCK")
    if "NOT_ACTIVE" in block_statuses:
        return result("NOT_CANONICAL", "SOURCE_POSITIVELY_REPORTS_BLOCK_NOT_ACTIVE")

    if network_id == "eip155:1":
        inclusion_height = block_items[0]["inclusion"].get("block_height")
        inclusion_sources = {
            item.get("source", {}).get("source_id")
            for item in inclusions if item["inclusion"].get("block_hash") == block_hash
            and isinstance(item.get("source"), dict)
        }
        for checkpoint in records:
            if checkpoint.get("observation_kind") != "FINALITY_CHECKPOINT":
                continue
            if checkpoint.get("source_asserted_head_tag") != "finalized":
                continue
            checkpoint_block = checkpoint.get("inclusion")
            if not isinstance(checkpoint_block, dict):
                continue
            checkpoint_height = checkpoint_block.get("block_height")
            checkpoint_source = checkpoint.get("source", {}).get("source_id")
            if (
                isinstance(checkpoint_height, int)
                and isinstance(inclusion_height, int)
                and checkpoint_height >= inclusion_height
                and checkpoint_source in inclusion_sources
                and checkpoint_block.get("block_hash")
            ):
                return result("FINALIZED", "SAME_SOURCE_FINALIZED_CHECKPOINT_COVERS_INCLUSION")

    return result("INCLUDED", "BLOCK_INCLUSION_WITHOUT_FINALITY_PROOF")
