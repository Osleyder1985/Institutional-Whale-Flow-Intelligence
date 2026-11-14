"""Evidence-gated Bitcoin UTXO accounting and entity address deltas.

Inputs and outputs are accounted independently. The implementation never
pairs a particular input with a particular output.
"""
from __future__ import annotations

from collections import defaultdict
from datetime import datetime
import re

from iwfi.attribution_integrity import validate_claim_collection


UTC_PATTERN = re.compile(r"[0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{2}:[0-9]{2}:[0-9]{2}Z")
TXID_PATTERN = re.compile(r"[0-9a-fA-F]{64}")


def _parse_utc(value):
    if not isinstance(value, str) or UTC_PATTERN.fullmatch(value) is None:
        return None
    try:
        return datetime.fromisoformat(value[:-1] + "+00:00")
    except ValueError:
        return None


def _claim_resolution(address, event_time, known_at, claim_index):
    if not isinstance(address, str) or not address:
        return {"status": "UNKNOWN", "entity_id": None, "claim_ids": []}
    eligible, disputed, rejected = [], [], []
    for claim in claim_index.values():
        subject = claim.get("subject")
        if not isinstance(subject, dict):
            continue
        if subject.get("subject_type") != "ADDRESS":
            continue
        if subject.get("network_id") != "bitcoin-mainnet" or subject.get("subject_id") != address:
            continue
        recorded = _parse_utc(claim.get("recorded_at_utc"))
        start = _parse_utc(claim.get("valid_from_utc"))
        end = _parse_utc(claim.get("valid_to_utc"))
        if recorded is None or start is None or end is None or recorded > known_at:
            continue
        if start > end or event_time < start or event_time > end:
            continue
        if claim.get("epistemic_status") == "DISPUTED" or claim.get("review_status") == "DISPUTED":
            disputed.append(claim["claim_id"])
            continue
        if claim.get("epistemic_status") != "VERIFIED" or claim.get("review_status") != "REVIEWED":
            rejected.append(claim["claim_id"])
            continue
        if claim.get("predicate") != "CONTROLLED_BY":
            rejected.append(claim["claim_id"])
            continue
        if claim.get("counter_evidence") or not claim.get("supporting_evidence"):
            rejected.append(claim["claim_id"])
            continue
        target = claim.get("object")
        if not isinstance(target, dict) or target.get("object_type") != "ENTITY":
            rejected.append(claim["claim_id"])
            continue
        entity_id = target.get("object_id")
        if not isinstance(entity_id, str) or not entity_id:
            rejected.append(claim["claim_id"])
            continue
        eligible.append((claim["claim_id"], entity_id))

    if disputed:
        return {"status": "DISPUTED", "entity_id": None, "claim_ids": sorted(set(disputed))}
    entities = {entity_id for _, entity_id in eligible}
    if len(entities) > 1:
        return {"status": "CONFLICT", "entity_id": None,
                "claim_ids": sorted(claim_id for claim_id, _ in eligible)}
    if len(entities) == 1:
        entity_id = next(iter(entities))
        return {"status": "ATTRIBUTED", "entity_id": entity_id,
                "claim_ids": sorted(claim_id for claim_id, _ in eligible)}
    return {"status": "UNKNOWN", "entity_id": None, "claim_ids": []}


def aggregate_bitcoin_entity_deltas(transactions, claims, start_time_utc,
                                    end_time_utc, known_at_utc):
    """Aggregate observed address-set deltas by entity over a half-open UTC window.

    Entity values are outputs attributed to an entity minus inputs attributed to
    that entity. This is an observed address-set delta, not a complete entity
    balance or a matched input-to-output transfer graph.
    """
    start, end, cutoff = map(_parse_utc, (start_time_utc, end_time_utc, known_at_utc))
    if start is None or end is None or cutoff is None or start >= end:
        raise ValueError("time bounds must be canonical UTC timestamps and start < end")
    if isinstance(transactions, (str, bytes)) or isinstance(claims, (str, bytes)):
        raise ValueError("transactions and claims must be collections")
    try:
        tx_items, claim_items = list(transactions), list(claims)
    except TypeError as exc:
        raise ValueError("transactions and claims must be iterable") from exc
    claim_errors = validate_claim_collection(claim_items)
    if claim_errors:
        raise ValueError("invalid attribution claim collection: " + "; ".join(claim_errors))
    claim_index = {item["claim_id"]: item for item in claim_items}
    seen_txids = set()
    entity_totals = {}
    stats = {
        "transactions_received": len(tx_items),
        "transactions_in_window": 0,
        "transactions_included": 0,
        "transactions_excluded": defaultdict(int),
        "inputs_attributed": 0,
        "outputs_attributed": 0,
        "inputs_unknown": 0,
        "outputs_unknown": 0,
        "inputs_conflicted_or_disputed": 0,
        "outputs_conflicted_or_disputed": 0,
        "fee_sats_reported_not_attributed": 0,
    }

    def entity_bucket(entity_id):
        if entity_id not in entity_totals:
            entity_totals[entity_id] = {
                "entity_id": entity_id,
                "input_sats": 0,
                "output_sats": 0,
                "observed_address_delta_sats": 0,
                "attributed_input_count": 0,
                "attributed_output_count": 0,
                "claim_ids": set(),
                "transaction_ids": set(),
            }
        return entity_totals[entity_id]

    for index, tx in enumerate(tx_items):
        if not isinstance(tx, dict):
            raise ValueError(f"transactions[{index}] must be an object")
        txid = tx.get("transaction_id")
        if not isinstance(txid, str) or TXID_PATTERN.fullmatch(txid) is None:
            raise ValueError(f"transactions[{index}] has invalid transaction_id")
        txid = txid.lower()
        if txid in seen_txids:
            raise ValueError(f"duplicate transaction_id: {txid}")
        seen_txids.add(txid)
        if tx.get("contract_version") != "1.0.0" or tx.get("network_id") != "bitcoin-mainnet":
            stats["transactions_excluded"]["unsupported_contract_or_network"] += 1
            continue
        if tx.get("canonicality") != "CANONICAL" or tx.get("confirmation_status") != "CONFIRMED":
            stats["transactions_excluded"]["not_canonical_and_confirmed"] += 1
            continue
        recorded = _parse_utc(tx.get("recorded_at_utc"))
        event_time = _parse_utc(tx.get("event_time_utc"))
        if recorded is None or event_time is None:
            stats["transactions_excluded"]["invalid_timestamp"] += 1
            continue
        if recorded > cutoff:
            stats["transactions_excluded"]["not_known_at_cutoff"] += 1
            continue
        if not (start <= event_time < end):
            stats["transactions_excluded"]["outside_event_window"] += 1
            continue
        stats["transactions_in_window"] += 1

        block_height, block_hash = tx.get("block_height"), tx.get("block_hash")
        inputs, outputs = tx.get("inputs"), tx.get("outputs")
        fee = tx.get("fee_sats")
        if (not isinstance(block_height, int) or isinstance(block_height, bool) or block_height < 0
                or not isinstance(block_hash, str) or TXID_PATTERN.fullmatch(block_hash) is None
                or not isinstance(fee, int) or isinstance(fee, bool) or fee < 0
                or not isinstance(inputs, list) or not inputs
                or not isinstance(outputs, list) or not outputs):
            stats["transactions_excluded"]["malformed_accounting_fields"] += 1
            continue

        valid = True
        input_ids, output_ids = set(), set()
        input_total = output_total = 0
        for item in inputs:
            if not isinstance(item, dict):
                valid = False
                break
            vin, prev_txid, prev_vout, amount = (
                item.get("vin"), item.get("previous_txid"),
                item.get("previous_vout"), item.get("amount_sats")
            )
            if (not isinstance(vin, int) or isinstance(vin, bool) or vin < 0
                    or vin in input_ids or not isinstance(prev_txid, str)
                    or TXID_PATTERN.fullmatch(prev_txid) is None
                    or not isinstance(prev_vout, int) or isinstance(prev_vout, bool) or prev_vout < 0
                    or not isinstance(amount, int) or isinstance(amount, bool) or amount < 0):
                valid = False
                break
            input_ids.add(vin)
            input_total += amount
        if not valid:
            stats["transactions_excluded"]["invalid_input"] += 1
            continue
        for item in outputs:
            if not isinstance(item, dict):
                valid = False
                break
            vout, amount = item.get("vout"), item.get("amount_sats")
            if (not isinstance(vout, int) or isinstance(vout, bool) or vout < 0
                    or vout in output_ids or not isinstance(amount, int)
                    or isinstance(amount, bool) or amount < 0):
                valid = False
                break
            output_ids.add(vout)
            output_total += amount
        if not valid:
            stats["transactions_excluded"]["invalid_output"] += 1
            continue
        if input_total != output_total + fee:
            stats["transactions_excluded"]["value_conservation_failure"] += 1
            continue

        for side, records in (("input", inputs), ("output", outputs)):
            for record in records:
                resolution = _claim_resolution(record.get("address"), event_time, cutoff, claim_index)
                amount = record["amount_sats"]
                if resolution["status"] == "ATTRIBUTED":
                    entity = entity_bucket(resolution["entity_id"])
                    if side == "input":
                        entity["input_sats"] += amount
                        entity["attributed_input_count"] += 1
                    else:
                        entity["output_sats"] += amount
                        entity["attributed_output_count"] += 1
                    entity["claim_ids"].update(resolution["claim_ids"])
                    entity["transaction_ids"].add(txid)
                    stats[f"{side}s_attributed"] += 1
                elif resolution["status"] in {"CONFLICT", "DISPUTED"}:
                    stats[f"{side}s_conflicted_or_disputed"] += 1
                else:
                    stats[f"{side}s_unknown"] += 1
        stats["fee_sats_reported_not_attributed"] += fee
        stats["transactions_included"] += 1

    entities = []
    for entity_id in sorted(entity_totals):
        item = entity_totals[entity_id]
        item["observed_address_delta_sats"] = item["output_sats"] - item["input_sats"]
        item["claim_ids"] = sorted(item["claim_ids"])
        item["transaction_ids"] = sorted(item["transaction_ids"])
        entities.append(item)
    stats["transactions_excluded"] = dict(sorted(stats["transactions_excluded"].items()))
    return {
        "contract_version": "1.0.0",
        "network_id": "bitcoin-mainnet",
        "event_window_utc": {
            "start_inclusive": start_time_utc,
            "end_exclusive": end_time_utc,
        },
        "known_at_utc": known_at_utc,
        "entities": entities,
        "statistics": stats,
        "limitations": [
            "Observed address-set delta is not a complete entity balance or beneficial ownership estimate.",
            "Inputs and outputs are accounted independently; no input-to-output pairing is inferred.",
            "Fees are reported once per transaction and are not allocated to an entity.",
            "Unknown, conflicted, disputed, or missing addresses remain unattributed.",
            "A transaction with incomplete endpoint attribution can contribute partial address-set deltas.",
            "This output is not a trade, buy/sell event, or accumulation/distribution classification.",
            "Coverage is limited to the supplied canonical transactions and reviewed claims.",
        ],
    }
