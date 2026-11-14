import hashlib
import tempfile
import unittest
import zipfile
from pathlib import Path

from iwfi.binance_spot_flow_metrics import SpotFlowMetricsError, process_archive


class BinanceSpotFlowMetricsTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)

    def tearDown(self):
        self.temp.cleanup()

    def make_archive(self, rows, symbol="BTCUSDT", day="2026-11-13"):
        name = f"{symbol}-aggTrades-{day}.zip"
        csv_name = f"{symbol}-aggTrades-{day}.csv"
        archive_path = self.root / name
        with zipfile.ZipFile(archive_path, "w", compression=zipfile.ZIP_DEFLATED) as archive:
            archive.writestr(csv_name, "".join(",".join(row) + "\n" for row in rows))
        checksum_path = self.root / f"{name}.CHECKSUM"
        checksum_path.write_text(hashlib.sha256(archive_path.read_bytes()).hexdigest() + "  " + name + "\n")
        return archive_path, checksum_path

    def test_buyer_taker_and_seller_taker_are_classified_correctly(self):
        rows = [
            ["1", "100.10", "0.25", "1", "1", "1794528000000000", "false", "true"],
            ["2", "100.20", "0.50", "2", "2", "1794528001000000", "true", "true"],
        ]
        archive, checksum = self.make_archive(rows)
        result = process_archive(archive, checksum, "BTCUSDT", "2026-11-13")
        bucket = result["buckets"][0]
        self.assertEqual(bucket["taker_buy_base_qty"], "0.25")
        self.assertEqual(bucket["taker_sell_base_qty"], "0.50")
        self.assertEqual(bucket["signed_base_volume_delta"], "-0.25")
        self.assertEqual(bucket["taker_buy_quote_qty"], "25.0250")
        self.assertEqual(bucket["taker_sell_quote_qty"], "50.1000")
        self.assertEqual(result["participant_identity"], "UNKNOWN")
        self.assertEqual(result["institutional_attribution"], "NOT_ESTABLISHED")

    def test_eth_microsecond_data_is_supported(self):
        rows = [["7", "3200.10", "0.125", "70", "72", "1794528000000001", "false", "true"]]
        archive, checksum = self.make_archive(rows, symbol="ETHUSDT")
        result = process_archive(archive, checksum, "ETHUSDT", "2026-11-13")
        self.assertEqual(result["symbol"], "ETHUSDT")
        self.assertEqual(result["timestamp_unit"], "microseconds")
        self.assertEqual(result["buckets"][0]["taker_buy_quote_qty"], "400.01250")

    def test_interval_buckets_preserve_cumulative_delta_and_unobserved_gaps(self):
        rows = [
            ["1", "10", "1", "1", "1", "1794528000000000", "false", "true"],
            ["2", "10", "2", "2", "2", "1794528000000000", "true", "true"],
            ["3", "11", "1", "3", "3", "1794528060000000", "false", "true"],
        ]
        archive, checksum = self.make_archive(rows)
        result = process_archive(archive, checksum, "BTCUSDT", "2026-11-13", 60)
        self.assertEqual(result["observed_interval_count"], 2)
        self.assertEqual(result["unobserved_interval_count"], 1438)
        self.assertEqual(result["buckets"][0]["signed_base_volume_delta"], "-1")
        self.assertEqual(result["buckets"][1]["cumulative_signed_base_volume"], "0")
        self.assertIn("ZERO_ACTIVITY_NOT_PROVEN", result["unobserved_interval_semantics"])

    def test_invalid_interval_is_rejected(self):
        rows = [["1", "10", "1", "1", "1", "1794528000000000", "false", "true"]]
        archive, checksum = self.make_archive(rows)
        with self.assertRaisesRegex(SpotFlowMetricsError, "divide 86400"):
            process_archive(archive, checksum, "BTCUSDT", "2026-11-13", 61)

    def test_non_monotonic_aggregate_trade_ids_are_rejected(self):
        rows = [
            ["2", "10", "1", "2", "2", "1794528000000000", "false", "true"],
            ["1", "10", "1", "1", "1", "1794528001000000", "false", "true"],
        ]
        archive, checksum = self.make_archive(rows)
        with self.assertRaisesRegex(SpotFlowMetricsError, "strictly increasing"):
            process_archive(archive, checksum, "BTCUSDT", "2026-11-13")

    def test_non_monotonic_timestamps_are_rejected(self):
        rows = [
            ["1", "10", "1", "1", "1", "1794528001000000", "false", "true"],
            ["2", "10", "1", "2", "2", "1794528000000000", "false", "true"],
        ]
        archive, checksum = self.make_archive(rows)
        with self.assertRaisesRegex(SpotFlowMetricsError, "timestamps must be nondecreasing"):
            process_archive(archive, checksum, "BTCUSDT", "2026-11-13")

    def test_checksum_mismatch_is_rejected_before_metrics(self):
        rows = [["1", "10", "1", "1", "1", "1794528000000000", "false", "true"]]
        archive, checksum = self.make_archive(rows)
        checksum.write_text("0" * 64)
        with self.assertRaisesRegex(SpotFlowMetricsError, "archive validation failed"):
            process_archive(archive, checksum, "BTCUSDT", "2026-11-13")

    def test_exact_decimal_notional_does_not_use_binary_float(self):
        rows = [["1", "0.1", "0.2", "1", "1", "1794528000000000", "false", "true"]]
        archive, checksum = self.make_archive(rows)
        result = process_archive(archive, checksum, "BTCUSDT", "2026-11-13")
        self.assertEqual(result["buckets"][0]["taker_buy_quote_qty"], "0.02")


if __name__ == "__main__":
    unittest.main()
