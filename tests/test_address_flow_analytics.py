"""Tests for point-in-time address flow aggregation."""
import copy
import json
import unittest
from pathlib import Path

from iwfi.address_flow_analytics import AddressFlowAnalyticsError, summarize_address_flows

ROOT = Path(__file__).resolve().parent


def movement(identifier="m-1", *, asset_id="bitcoin:btc", symbol="BTC",
             network_id="bitcoin-mainnet", unit="BTC", amount="2.5",
             sender="bc1qsender", receiver="bc1qreceiver",
             event="2026-11-10T12:00:00Z", recorded="2026-11-10T12:00:05Z",
             confirmation="CONFIRMED", quality="VALID"):
    return {
        "contract_version": "1.0.0", "movement_id": identifier,
        "asset": {"asset_id": asset_id, "symbol": symbol, "network_id": network_id},
        "event_time_utc": event, "recorded_at_utc": recorded,
        "transfer": {
            "movement_type": "TRANSFER", "amount": amount, "unit": unit,
            "from_address": sender, "to_address": receiver,
            "transaction_id": "tx-" + identifier,
            "confirmation_status": confirmation, "event_locator": None,
        },
        "source_observation_ids": ["obs-" + identifier],
        "attribution_resolutions": [], "quality_status": quality, "limitations": [],
    }


class AddressFlowAnalyticsTests(unittest.TestCase):
    def setUp(self):
        self.start = "2026-11-10T00:00:00Z"
        self.end = "2026-11-12T00:00:00Z"
        self.cutoff = "2026-11-12T00:00:00Z"

    def analyze(self, rows):
        return summarize_address_flows(rows, self.start, self.end, self.cutoff)

    def test_existing_fixture_counts_confirmed_btc_and_excludes_unknown_eth(self):
        fixture = json.loads((ROOT / "fixtures" / "movement-ledger.json").read_text(encoding="utf-8"))
        result = self.analyze(fixture)
        self.assertEqual(result["movement_counts"]["included_confirmed_movements"], 1)
        self.assertEqual(result["movement_counts"]["excluded_by_reason"]["confirmation_not_confirmed"], 1)
        by_address = {item["address"]: item for item in result["addresses"]}
        self.assertEqual(by_address["bc1qsource"]["net_flow_delta"], "-1.25000000")
        self.assertEqual(by_address["bc1qexchangeexample"]["net_flow_delta"], "1.25000000")

    def test_multiple_transfers_produce_exact_in_out_and_net_delta(self):
        rows = [
            movement("a", amount="3", sender="wallet", receiver="counterparty"),
            movement("b", amount="1.25", sender="counterparty", receiver="wallet"),
        ]
        wallet = next(item for item in self.analyze(rows)["addresses"] if item["address"] == "wallet")
        self.assertEqual((wallet["incoming_amount"], wallet["outgoing_amount"], wallet["net_flow_delta"]),
                         ("1.25", "3", "-1.75"))
        self.assertEqual((wallet["incoming_movement_count"], wallet["outgoing_movement_count"]), (1, 1))

    def test_event_window_is_start_inclusive_and_end_exclusive(self):
        result = self.analyze([
            movement("at-start", event=self.start),
            movement("at-end", event=self.end),
        ])
        self.assertEqual(result["movement_counts"]["within_event_window"], 1)
        self.assertEqual(result["movement_counts"]["included_confirmed_movements"], 1)

    def test_late_record_is_not_visible_before_known_at_cutoff(self):
        result = self.analyze([movement(recorded="2026-11-12T00:00:01Z")])
        self.assertEqual(result["addresses"], [])
        self.assertEqual(result["movement_counts"]["excluded_by_reason"]["not_known_at_cutoff"], 1)

    def test_pending_unknown_confirmation_and_quarantined_records_are_excluded(self):
        result = self.analyze([
            movement("pending", confirmation="PENDING"),
            movement("unknown", confirmation="UNKNOWN"),
            movement("quarantined", quality="QUARANTINED"),
        ])
        self.assertEqual(result["addresses"], [])
        self.assertEqual(result["movement_counts"]["excluded_by_reason"]["confirmation_not_confirmed"], 2)
        self.assertEqual(result["movement_counts"]["excluded_by_reason"]["quality_not_admissible"], 1)

    def test_missing_amount_is_excluded_not_treated_as_zero(self):
        result = self.analyze([movement(amount=None)])
        self.assertEqual(result["addresses"], [])
        self.assertEqual(result["movement_counts"]["excluded_by_reason"]["amount_unknown"], 1)

    def test_unknown_endpoint_counts_known_side_and_exposes_coverage_gap(self):
        result = self.analyze([movement(sender=None, receiver="known-wallet")])
        self.assertEqual(result["addresses"][0]["net_flow_delta"], "2.5")
        self.assertEqual(result["movement_counts"]["excluded_by_reason"]["from_address_unknown"], 1)

    def test_same_address_transfer_preserves_gross_flow_and_zero_net(self):
        item = self.analyze([movement(sender="same", receiver="same", amount="4")])["addresses"][0]
        self.assertEqual((item["incoming_amount"], item["outgoing_amount"], item["net_flow_delta"]),
                         ("4", "4", "0"))

    def test_evm_address_case_is_normalized(self):
        row = movement("eth", asset_id="ethereum:eth", symbol="ETH",
                       network_id="eip155:1", unit="ETH", sender="0xAbC", receiver="0xDEF")
        result = self.analyze([row])
        self.assertEqual({item["address"] for item in result["addresses"]}, {"0xabc", "0xdef"})

    def test_duplicate_movement_ids_fail_closed(self):
        row = movement()
        with self.assertRaisesRegex(AddressFlowAnalyticsError, "duplicate movement_id"):
            self.analyze([row, copy.deepcopy(row)])

    def test_invalid_decimal_and_inconsistent_asset_are_rejected(self):
        with self.assertRaisesRegex(AddressFlowAnalyticsError, "canonical decimal"):
            self.analyze([movement(amount="01.0")])
        with self.assertRaisesRegex(AddressFlowAnalyticsError, "unit is inconsistent"):
            self.analyze([movement(unit="ETH")])

    def test_invalid_or_reversed_window_is_rejected(self):
        with self.assertRaises(AddressFlowAnalyticsError):
            summarize_address_flows([], self.end, self.start, self.cutoff)
        with self.assertRaises(AddressFlowAnalyticsError):
            summarize_address_flows([], "2026-11-10T00:00:00+00:00", self.end, self.cutoff)


if __name__ == "__main__":
    unittest.main()
