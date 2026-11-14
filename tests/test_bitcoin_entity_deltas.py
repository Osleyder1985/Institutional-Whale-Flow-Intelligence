"""Bitcoin UTXO entity-delta tests; all records here are synthetic software fixtures."""
import json
import unittest
from pathlib import Path

from iwfi.bitcoin_entity_deltas import aggregate_bitcoin_entity_deltas


START = "2026-11-01T00:00:00Z"
END = "2026-11-03T00:00:00Z"
CUTOFF = "2026-11-03T00:00:00Z"
EVENT = "2026-11-02T12:00:00Z"
TXID = "a" * 64
BLOCK = "b" * 64


def claim(claim_id, address, entity, *, status="VERIFIED", review="REVIEWED",
          predicate="CONTROLLED_BY", recorded="2026-11-01T00:00:00Z",
          valid_from="2026-01-01T00:00:00Z", valid_to="2026-12-31T23:59:59Z",
          counter=None):
    return {
        "contract_version": "1.0.0",
        "claim_id": claim_id,
        "subject": {"subject_type": "ADDRESS", "subject_id": address,
                    "network_id": "bitcoin-mainnet"},
        "predicate": predicate,
        "object": {"object_type": "ENTITY", "object_id": entity, "network_id": None},
        "epistemic_status": status,
        "claim_source": {"provider": "reviewed-source", "endpoint": "address-control",
                         "record_id": claim_id, "observation_ids": []},
        "supporting_evidence": [{"evidence_type": "OFFICIAL_PUBLICATION",
                                 "evidence_ref": "evidence:" + claim_id,
                                 "source": "official-source", "observation_id": None}],
        "counter_evidence": counter or [],
        "recorded_at_utc": recorded,
        "valid_from_utc": valid_from,
        "valid_to_utc": valid_to,
        "supersedes_claim_id": None,
        "review_status": review,
        "rationale": "Synthetic test record only.",
        "review": {"reviewer_id": "test-reviewer", "reviewed_at_utc": recorded},
    }


def transaction(txid=TXID, inputs=None, outputs=None, fee=10):
    return {
        "contract_version": "1.0.0",
        "transaction_id": txid,
        "network_id": "bitcoin-mainnet",
        "block_height": 900000,
        "block_hash": BLOCK,
        "event_time_utc": EVENT,
        "recorded_at_utc": "2026-11-02T12:00:05Z",
        "canonicality": "CANONICAL",
        "confirmation_status": "CONFIRMED",
        "inputs": inputs if inputs is not None else [
            {"vin": 0, "previous_txid": "1" * 64, "previous_vout": 0,
             "address": "bc1qentitya1", "amount_sats": 1000}
        ],
        "outputs": outputs if outputs is not None else [
            {"vout": 0, "address": "bc1qentitya2", "amount_sats": 990}
        ],
        "fee_sats": fee,
        "source_observation_ids": ["real-source-observation-placeholder"],
    }


def aggregate(transactions, claims):
    return aggregate_bitcoin_entity_deltas(transactions, claims, START, END, CUTOFF)


class BitcoinEntityDeltaTests(unittest.TestCase):
    def test_same_entity_inputs_and_outputs_net_to_fee_without_pairing(self):
        tx = transaction(
            inputs=[
                {"vin": 0, "previous_txid": "1" * 64, "previous_vout": 0,
                 "address": "bc1qentitya1", "amount_sats": 700},
                {"vin": 1, "previous_txid": "2" * 64, "previous_vout": 1,
                 "address": "bc1qentitya2", "amount_sats": 300},
            ],
            outputs=[
                {"vout": 0, "address": "bc1qentitya3", "amount_sats": 800},
                {"vout": 1, "address": "bc1qentitya4", "amount_sats": 190},
            ],
            fee=10,
        )
        claims = [
            claim("c1", "bc1qentitya1", "entity-a"),
            claim("c2", "bc1qentitya2", "entity-a"),
            claim("c3", "bc1qentitya3", "entity-a"),
            claim("c4", "bc1qentitya4", "entity-a"),
        ]
        result = aggregate([tx], claims)
        entity = result["entities"][0]
        self.assertEqual(entity["input_sats"], 1000)
        self.assertEqual(entity["output_sats"], 990)
        self.assertEqual(entity["observed_address_delta_sats"], -10)
        self.assertEqual(result["statistics"]["fee_sats_reported_not_attributed"], 10)

    def test_distinct_entities_receive_independent_input_and_output_deltas(self):
        tx = transaction(
            inputs=[{"vin": 0, "previous_txid": "1" * 64, "previous_vout": 0,
                     "address": "bc1qentitya", "amount_sats": 1000}],
            outputs=[{"vout": 0, "address": "bc1qentityb", "amount_sats": 990}],
            fee=10,
        )
        result = aggregate([tx], [
            claim("c1", "bc1qentitya", "entity-a"),
            claim("c2", "bc1qentityb", "entity-b"),
        ])
        by_id = {item["entity_id"]: item for item in result["entities"]}
        self.assertEqual(by_id["entity-a"]["observed_address_delta_sats"], -1000)
        self.assertEqual(by_id["entity-b"]["observed_address_delta_sats"], 990)

    def test_unknown_input_does_not_get_guessed(self):
        tx = transaction(
            inputs=[{"vin": 0, "previous_txid": "1" * 64, "previous_vout": 0,
                     "address": None, "amount_sats": 1000}],
            outputs=[{"vout": 0, "address": "bc1qentityb", "amount_sats": 990}],
            fee=10,
        )
        result = aggregate([tx], [claim("c1", "bc1qentityb", "entity-b")])
        entity = result["entities"][0]
        self.assertEqual(entity["observed_address_delta_sats"], 990)
        self.assertEqual(result["statistics"]["inputs_unknown"], 1)

    def test_conflicted_address_is_not_attributed(self):
        tx = transaction()
        result = aggregate([tx], [
            claim("c1", "bc1qentitya1", "entity-a"),
            claim("c2", "bc1qentitya1", "entity-b"),
        ])
        self.assertEqual(result["entities"], [])
        self.assertEqual(result["statistics"]["inputs_conflicted_or_disputed"], 1)

    def test_disputed_claim_blocks_attribution(self):
        tx = transaction()
        result = aggregate([tx], [
            claim("c1", "bc1qentitya1", "entity-a", status="DISPUTED",
                  review="DISPUTED",
                  counter=[{"evidence_type": "OTHER", "evidence_ref": "counter",
                            "source": "review", "observation_id": None}])
        ])
        self.assertEqual(result["entities"], [])
        self.assertEqual(result["statistics"]["inputs_conflicted_or_disputed"], 1)

    def test_provider_label_is_not_economic_control(self):
        tx = transaction()
        result = aggregate([tx], [
            claim("c1", "bc1qentitya1", "entity-a", status="PROVIDER_LABELLED",
                  review="UNREVIEWED")
        ])
        self.assertEqual(result["entities"], [])
        self.assertEqual(result["statistics"]["inputs_unknown"], 1)

    def test_claim_recorded_after_cutoff_is_not_used(self):
        tx = transaction()
        result = aggregate([tx], [
            claim("c1", "bc1qentitya1", "entity-a",
                  recorded="2026-11-03T00:00:01Z")
        ])
        self.assertEqual(result["entities"], [])

    def test_noncanonical_or_unconfirmed_transaction_is_excluded(self):
        tx = transaction()
        tx["canonicality"] = "UNKNOWN"
        result = aggregate([tx], [])
        self.assertEqual(result["entities"], [])
        self.assertEqual(result["statistics"]["transactions_excluded"]["not_canonical_and_confirmed"], 1)

    def test_value_conservation_failure_is_excluded(self):
        tx = transaction(fee=9)
        result = aggregate([tx], [])
        self.assertEqual(result["entities"], [])
        self.assertEqual(result["statistics"]["transactions_excluded"]["value_conservation_failure"], 1)

    def test_duplicate_transaction_ids_fail_closed(self):
        tx = transaction()
        with self.assertRaisesRegex(ValueError, "duplicate transaction_id"):
            aggregate([tx, tx], [])

    def test_duplicate_vin_and_vout_indices_are_excluded(self):
        tx = transaction(
            inputs=[
                {"vin": 0, "previous_txid": "1" * 64, "previous_vout": 0,
                 "address": "bc1qentitya1", "amount_sats": 500},
                {"vin": 0, "previous_txid": "2" * 64, "previous_vout": 0,
                 "address": "bc1qentitya2", "amount_sats": 500},
            ],
            outputs=[
                {"vout": 0, "address": "bc1qentitya3", "amount_sats": 990},
                {"vout": 0, "address": "bc1qentitya4", "amount_sats": 0},
            ],
        )
        result = aggregate([tx], [])
        self.assertEqual(result["statistics"]["transactions_excluded"]["invalid_input"], 1)

    def test_schema_accepts_valid_synthetic_transaction(self):
        from jsonschema import Draft202012Validator, FormatChecker
        root = Path(__file__).resolve().parent.parent
        schema = json.loads((root / "schemas" / "bitcoin-utxo-transaction.schema.json").read_text(encoding="utf-8"))
        errors = list(Draft202012Validator(schema, format_checker=FormatChecker()).iter_errors(transaction()))
        self.assertEqual(errors, [])


if __name__ == "__main__":
    unittest.main()
