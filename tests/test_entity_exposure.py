"""Historical exposure tests; all balance snapshots are synthetic software fixtures."""
import json
import unittest
from pathlib import Path

from iwfi.entity_exposure import aggregate_entity_exposure_history


CUTOFF = "2026-11-15T00:00:00Z"
REVIEWED = "2026-10-01T00:00:00Z"


def claim(claim_id, address, entity="entity-a", *, network="bitcoin-mainnet",
          recorded=REVIEWED, reviewed=REVIEWED, valid_from="2022-01-01T00:00:00Z",
          valid_to="2027-01-01T00:00:00Z", status="VERIFIED", review_status="REVIEWED",
          predicate="CONTROLLED_BY", counter=None):
    return {
        "contract_version": "1.0.0",
        "claim_id": claim_id,
        "subject": {"subject_type": "ADDRESS", "subject_id": address, "network_id": network},
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
        "review_status": review_status,
        "rationale": "Synthetic test claim only.",
        "review": {"reviewer_id": "test-reviewer" if review_status != "UNREVIEWED" else None,
                   "reviewed_at_utc": reviewed if review_status != "UNREVIEWED" else None},
    }


def snapshot(batch_id, time, balances, *, coverage="COMPLETE", expected=None,
             unresolved=0, scope="entity-a", asset="bitcoin:btc",
             network="bitcoin-mainnet", unit="satoshi"):
    addresses = [
        {"address": address, "balance_atomic": amount, "unit": unit,
         "source_observation_id": f"obs-{batch_id}-{index}"}
        for index, (address, amount) in enumerate(balances)
    ]
    count = len(addresses)
    return {
        "contract_version": "1.0.0",
        "snapshot_batch_id": batch_id,
        "scope_entity_id": scope,
        "asset_id": asset,
        "network_id": network,
        "snapshot_time_utc": time,
        "recorded_at_utc": "2026-11-02T00:00:00Z",
        "block_height": 900000 + count,
        "block_hash": "b" * 64,
        "canonicality": "CANONICAL",
        "confirmation_status": "CONFIRMED",
        "inventory_coverage": {
            "status": coverage,
            "expected_address_count": expected if expected is not None else count,
            "observed_address_count": count,
            "unresolved_address_count": unresolved,
            "evidence_ref": "inventory-evidence:" + batch_id if coverage == "COMPLETE" else None,
            "review_status": "REVIEWED" if coverage == "COMPLETE" else "UNREVIEWED",
            "reviewer_id": "test-inventory-reviewer" if coverage == "COMPLETE" else None,
            "reviewed_at_utc": REVIEWED if coverage == "COMPLETE" else None,
        },
        "addresses": addresses,
    }


def aggregate(snapshots, claims):
    return aggregate_entity_exposure_history(snapshots, claims, CUTOFF)


class EntityExposureTests(unittest.TestCase):
    def test_complete_inventory_produces_total_exposure_and_candidate_direction(self):
        claims = [
            claim("c1", "bc1qaddress1"),
            claim("c2", "bc1qaddress2"),
        ]
        first = snapshot("s1", "2026-11-01T00:00:00Z",
                         [("bc1qaddress1", 1000), ("bc1qaddress2", 2000)])
        second = snapshot("s2", "2026-11-02T00:00:00Z",
                          [("bc1qaddress1", 1500), ("bc1qaddress2", 2000)])
        result = aggregate([first, second], claims)
        history = result["histories"][0]
        self.assertEqual(history["snapshots"][0]["total_controlled_address_exposure_atomic"], 3000)
        self.assertEqual(history["snapshots"][1]["total_controlled_address_exposure_atomic"], 3500)
        change = history["changes"][0]
        self.assertEqual(change["total_controlled_address_delta_atomic"], 500)
        self.assertEqual(change["relative_controlled_address_change"], "1/6")
        self.assertEqual(change["candidate_direction"], "NET_BALANCE_INCREASE")
        self.assertEqual(change["classification_status"], "NOT_CALIBRATED")

    def test_partial_inventory_emits_known_address_exposure_but_not_total(self):
        claims = [claim("c1", "bc1qaddress1")]
        item = snapshot("s1", "2026-11-01T00:00:00Z",
                        [("bc1qaddress1", 1000)], coverage="PARTIAL")
        result = aggregate([item], claims)
        row = result["histories"][0]["snapshots"][0]
        self.assertEqual(row["known_controlled_address_exposure_atomic"], 1000)
        self.assertIsNone(row["total_controlled_address_exposure_atomic"])
        self.assertEqual(row["coverage_status"], "PARTIAL")

    def test_complete_inventory_with_unattributed_address_is_downgraded(self):
        item = snapshot("s1", "2026-11-01T00:00:00Z",
                        [("bc1qaddress1", 1000), ("bc1qunknown", 500)])
        result = aggregate([item], [claim("c1", "bc1qaddress1")])
        row = result["histories"][0]["snapshots"][0]
        self.assertEqual(row["known_controlled_address_exposure_atomic"], 1000)
        self.assertIsNone(row["total_controlled_address_exposure_atomic"])
        self.assertEqual(row["coverage_status"], "PARTIAL")
        self.assertEqual(row["addresses_unresolved"], 1)

    def test_conflicting_claims_prevent_total_exposure(self):
        item = snapshot("s1", "2026-11-01T00:00:00Z", [("bc1qaddress1", 1000)])
        result = aggregate([item], [
            claim("c1", "bc1qaddress1", "entity-a"),
            claim("c2", "bc1qaddress1", "entity-b"),
        ])
        self.assertIsNone(result["histories"][0]["snapshots"][0]["total_controlled_address_exposure_atomic"])

    def test_future_claim_review_is_not_used_at_knowledge_cutoff(self):
        item = snapshot("s1", "2026-11-01T00:00:00Z", [("bc1qaddress1", 1000)])
        future = claim("c1", "bc1qaddress1", reviewed="2026-11-16T00:00:00Z")
        result = aggregate([item], [future])
        row = result["histories"][0]["snapshots"][0]
        self.assertEqual(row["known_controlled_address_exposure_atomic"], 0)
        self.assertIsNone(row["total_controlled_address_exposure_atomic"])

    def test_open_inventory_without_reviewed_evidence_is_never_complete(self):
        item = snapshot("s1", "2026-11-01T00:00:00Z", [("bc1qaddress1", 1000)])
        item["inventory_coverage"]["reviewed_at_utc"] = None
        item["inventory_coverage"]["reviewer_id"] = None
        result = aggregate([item], [claim("c1", "bc1qaddress1")])
        self.assertIsNone(result["histories"][0]["snapshots"][0]["total_controlled_address_exposure_atomic"])

    def test_known_address_delta_requires_same_attributed_address_set(self):
        claims = [
            claim("c1", "bc1qaddress1"),
            claim("c2", "bc1qaddress2"),
        ]
        first = snapshot("s1", "2026-11-01T00:00:00Z", [("bc1qaddress1", 1000)],
                         coverage="PARTIAL")
        second = snapshot("s2", "2026-11-02T00:00:00Z",
                          [("bc1qaddress2", 1200)],
                          coverage="PARTIAL")
        result = aggregate([first, second], claims)
        change = result["histories"][0]["changes"][0]
        self.assertEqual(change["known_address_delta_atomic"], None)
        self.assertEqual(change["candidate_direction"], "NOT_CLASSIFIED")

    def test_eth_snapshot_uses_wei_and_separate_network(self):
        item = snapshot("eth-s1", "2026-11-01T00:00:00Z",
                         [("0x0000000000000000000000000000000000000001", 10**18)],
                         asset="ethereum:eth", network="eip155:1", unit="wei")
        claims = [claim("eth-c1", "0x0000000000000000000000000000000000000001",
                        network="eip155:1")]
        result = aggregate([item], claims)
        row = result["histories"][0]["snapshots"][0]
        self.assertEqual(row["unit"], "wei")
        self.assertEqual(row["known_controlled_address_exposure_atomic"], 10**18)

    def test_duplicate_snapshot_ids_fail_closed(self):
        item = snapshot("same", "2026-11-01T00:00:00Z", [("bc1qaddress1", 1000)])
        with self.assertRaisesRegex(ValueError, "duplicate snapshot_batch_id"):
            aggregate([item, item], [claim("c1", "bc1qaddress1")])

    def test_duplicate_snapshot_time_for_entity_and_asset_fails(self):
        first = snapshot("s1", "2026-11-01T00:00:00Z", [("bc1qaddress1", 1000)])
        second = snapshot("s2", "2026-11-01T00:00:00Z", [("bc1qaddress1", 1100)])
        with self.assertRaisesRegex(ValueError, "duplicate snapshot time"):
            aggregate([first, second], [claim("c1", "bc1qaddress1")])

    def test_schema_rejects_btc_snapshot_with_wei_unit(self):
        from jsonschema import Draft202012Validator, FormatChecker
        root = Path(__file__).resolve().parent.parent
        schema = json.loads((root / "schemas" / "entity-exposure-snapshot.schema.json").read_text(encoding="utf-8"))
        item = snapshot("s1", "2026-11-01T00:00:00Z", [("bc1qaddress1", 1000)])
        item["addresses"][0]["unit"] = "wei"
        errors = list(Draft202012Validator(schema, format_checker=FormatChecker()).iter_errors(item))
        self.assertTrue(errors)

    def test_snapshot_schema_accepts_valid_synthetic_snapshot(self):
        from jsonschema import Draft202012Validator, FormatChecker
        root = Path(__file__).resolve().parent.parent
        schema = json.loads((root / "schemas" / "entity-exposure-snapshot.schema.json").read_text(encoding="utf-8"))
        item = snapshot("s1", "2026-11-01T00:00:00Z", [("bc1qaddress1", 1000)])
        self.assertEqual(list(Draft202012Validator(schema, format_checker=FormatChecker()).iter_errors(item)), [])

    def test_real_binance_claim_only_contributes_at_exact_documented_instant(self):
        root = Path(__file__).resolve().parent.parent
        real_claim = json.loads((root / "data" / "attribution-claims" / "binance-btc-34xp-control-2022-11-22.json").read_text(encoding="utf-8"))
        item = snapshot("s1", "2022-11-22T23:59:59Z",
                        [(real_claim["subject"]["subject_id"], 123456)],
                        coverage="PARTIAL", scope="entity-binance")
        result = aggregate_entity_exposure_history(
            [item], [real_claim], "2026-11-15T00:00:00Z"
        )
        row = result["histories"][0]["snapshots"][0]
        self.assertEqual(row["known_controlled_address_exposure_atomic"], 123456)
        self.assertIsNone(row["total_controlled_address_exposure_atomic"])
        item["snapshot_time_utc"] = "2022-11-23T00:00:00Z"
        result_after = aggregate_entity_exposure_history(
            [item], [real_claim], "2026-11-15T00:00:00Z"
        )
        self.assertEqual(result_after["histories"][0]["snapshots"][0]["known_controlled_address_exposure_atomic"], 0)


if __name__ == "__main__":
    unittest.main()
