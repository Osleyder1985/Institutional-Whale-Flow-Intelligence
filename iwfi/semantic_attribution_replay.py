"""Deterministic semantic replay for frozen execution-participant inputs."""
import hashlib
import json
import re
from datetime import datetime

from iwfi.temporal_execution_attribution import resolve_execution_participants_as_of

_ALGORITHM_ID = "iwfi.temporal_execution_attribution.resolve_execution_participants_as_of"
_ALGORITHM_VERSION = "1.0.0"
_CANONICALIZATION = "IWFI-JSON-C14N-1"
_UTC = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z$")


def _canonical_bytes(value):
    return json.dumps(
        value, sort_keys=True, separators=(",", ":"),
        ensure_ascii=False, allow_nan=False,
    ).encode("utf-8")


def _hash(value):
    return hashlib.sha256(_canonical_bytes(value)).hexdigest()


def _valid_utc(value):
    if not isinstance(value, str) or not _UTC.fullmatch(value):
        return False
    try:
        datetime.strptime(value, "%Y-%m-%dT%H:%M:%SZ")
        return True
    except ValueError:
        return False


def replay_execution_participants(
    *, trade, claim_registry, actor_registry, observation_ids,
    knowledge_cutoff_utc,
):
    """Re-run the versioned temporal resolver from exact, caller-supplied inputs.

    Input bundles are treated as immutable snapshots by the caller. This function
    hashes each input and the generated semantic result; it does not fetch data.
    """
    if not _valid_utc(knowledge_cutoff_utc):
        raise ValueError("knowledge_cutoff_utc must be strict UTC")
    if not isinstance(trade, dict) or not isinstance(claim_registry, dict) or not isinstance(actor_registry, dict):
        raise ValueError("trade and registries must be objects")
    if not isinstance(observation_ids, list) or any(
        not isinstance(item, str) or not item.strip() for item in observation_ids
    ):
        raise ValueError("observation_ids must be a list of non-empty strings")
    inputs = {
        "trade": trade,
        "claim_registry": claim_registry,
        "actor_registry": actor_registry,
        "observation_ids": observation_ids,
    }
    input_hashes = {name: _hash(value) for name, value in inputs.items()}
    result = resolve_execution_participants_as_of(
        claim_registry, trade, knowledge_cutoff_utc, actor_registry, observation_ids
    )
    replay = {
        "replay_contract_version": "1.0.0",
        "algorithm_id": _ALGORITHM_ID,
        "algorithm_version": _ALGORITHM_VERSION,
        "canonicalization_version": _CANONICALIZATION,
        "knowledge_cutoff_utc": knowledge_cutoff_utc,
        "valid_time_utc": trade.get("event_time_utc"),
        "input_hashes": input_hashes,
        "result": result,
    }
    replay["result_hash"] = _hash(result)
    replay["replay_hash"] = _hash(replay)
    return replay


def verify_execution_replay(
    *, replay, trade, claim_registry, actor_registry, observation_ids,
):
    """Verify input binding and re-run the semantic engine offline."""
    if not isinstance(replay, dict):
        return {"status": "INVALID_REPLAY_RECORD"}
    unsigned = {key: value for key, value in replay.items() if key != "replay_hash"}
    try:
        if replay.get("replay_hash") != _hash(unsigned):
            return {"status": "REPLAY_RECORD_HASH_MISMATCH"}
        expected_inputs = {
            "trade": _hash(trade),
            "claim_registry": _hash(claim_registry),
            "actor_registry": _hash(actor_registry),
            "observation_ids": _hash(observation_ids),
        }
    except (TypeError, ValueError):
        return {"status": "NON_CANONICAL_INPUT"}
    if replay.get("input_hashes") != expected_inputs:
        return {"status": "REPLAY_INPUT_MISMATCH"}
    try:
        regenerated = replay_execution_participants(
            trade=trade, claim_registry=claim_registry,
            actor_registry=actor_registry, observation_ids=observation_ids,
            knowledge_cutoff_utc=replay.get("knowledge_cutoff_utc"),
        )
    except (TypeError, ValueError):
        return {"status": "REPLAY_EXECUTION_FAILED"}
    if (
        regenerated.get("result_hash") != replay.get("result_hash")
        or regenerated.get("result") != replay.get("result")
        or regenerated.get("algorithm_id") != replay.get("algorithm_id")
        or regenerated.get("algorithm_version") != replay.get("algorithm_version")
    ):
        return {"status": "SEMANTIC_REPLAY_MISMATCH"}
    return {
        "status": "SEMANTIC_REPLAY_VERIFIED",
        "result_hash": regenerated["result_hash"],
        "input_hashes": expected_inputs,
    }
