"""Synthetic fixtures for the offline Binance Vision archive validator."""
import hashlib
import tempfile
import unittest
import zipfile
from pathlib import Path

from iwfi.binance_vision_archive_validator import (
    ArchiveValidationError,
    validate_archive,
)


class BinanceVisionArchiveValidatorTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)

    def tearDown(self):
        self.temp.cleanup()

    def _make_archive(self, symbol="BTCUSDT", day="2026-11-12", rows=None, extra=None):
        filename = f"{symbol}-aggTrades-{day}.zip"
        csv_name = f"{symbol}-aggTrades-{day}.csv"
        zip_path = self.root / filename
        if rows is None:
            # Synthetic row only; it is not Binance production data.
            rows = ["1,100.25,0.01,10,10,1794441600000000,False,True"]
        with zipfile.ZipFile(zip_path, "w", compression=zipfile.ZIP_DEFLATED) as zipped:
            zipped.writestr(csv_name, "\n".join(rows) + "\n")
            if extra:
                for name, payload in extra.items():
                    zipped.writestr(name, payload)
        checksum_path = self.root / f"{filename}.CHECKSUM"
        checksum = hashlib.sha256(zip_path.read_bytes()).hexdigest()
        checksum_path.write_text(f"{checksum}  {filename}\n", encoding="utf-8")
        return zip_path, checksum_path

    def test_valid_btc_microsecond_archive(self):
        zip_path, checksum = self._make_archive()
        result = validate_archive(zip_path, checksum, "BTCUSDT", "2026-11-12")
        self.assertEqual(result["rows_validated"], 1)
        self.assertEqual(result["timestamp_unit"], "microseconds")
        self.assertEqual(result["actor_attribution"], "UNKNOWN")
        self.assertFalse(result["participant_identity_inferred"])

    def test_valid_eth_microsecond_archive(self):
        zip_path, checksum = self._make_archive(
            symbol="ETHUSDT",
            rows=["7,3200.10,0.25,70,72,1794441600000001,true,false"],
        )
        result = validate_archive(zip_path, checksum, "ETHUSDT", "2026-11-12")
        self.assertEqual(result["symbol"], "ETHUSDT")
        self.assertEqual(result["rows_validated"], 1)

    def test_pre_2025_archive_uses_milliseconds(self):
        zip_path, checksum = self._make_archive(
            day="2024-12-31",
            rows=["1,100.25,0.01,10,10,1735603200000,False,True"],
        )
        result = validate_archive(zip_path, checksum, "BTCUSDT", "2024-12-31")
        self.assertEqual(result["timestamp_unit"], "milliseconds")

    def test_boundary_2025_01_01_uses_microseconds(self):
        zip_path, checksum = self._make_archive(
            day="2025-01-01",
            rows=["1,100.25,0.01,10,10,1735689600000000,False,True"],
        )
        result = validate_archive(zip_path, checksum, "BTCUSDT", "2025-01-01")
        self.assertEqual(result["timestamp_unit"], "microseconds")

    def test_checksum_mismatch_blocks_before_parse(self):
        zip_path, checksum = self._make_archive()
        checksum.write_text(("0" * 64) + "\n", encoding="utf-8")
        with self.assertRaisesRegex(ArchiveValidationError, "checksum mismatch"):
            validate_archive(zip_path, checksum, "BTCUSDT", "2026-11-12")

    def test_wrong_csv_column_count_is_rejected(self):
        zip_path, checksum = self._make_archive(rows=["1,100,0.1,10,10,1794441600000000,False"])
        with self.assertRaisesRegex(ArchiveValidationError, "expected 8 columns"):
            validate_archive(zip_path, checksum, "BTCUSDT", "2026-11-12")

    def test_out_of_day_timestamp_is_rejected(self):
        zip_path, checksum = self._make_archive(
            rows=["1,100,0.1,10,10,1794528000000000,False,True"]
        )
        with self.assertRaisesRegex(ArchiveValidationError, "outside expected UTC day"):
            validate_archive(zip_path, checksum, "BTCUSDT", "2026-11-12")

    def test_invalid_decimal_and_boolean_are_rejected(self):
        cases = [
            "1,1e2,0.1,10,10,1794441600000000,False,True",
            "1,100,0.1,10,10,1794441600000000,BUY,True",
            "1,100,0,10,10,1794441600000000,False,True",
        ]
        for row in cases:
            with self.subTest(row=row):
                zip_path, checksum = self._make_archive(rows=[row])
                with self.assertRaises(ArchiveValidationError):
                    validate_archive(zip_path, checksum, "BTCUSDT", "2026-11-12")

    def test_first_trade_id_cannot_exceed_last_trade_id(self):
        zip_path, checksum = self._make_archive(
            rows=["1,100,0.1,11,10,1794441600000000,False,True"]
        )
        with self.assertRaisesRegex(ArchiveValidationError, "first_trade_id exceeds"):
            validate_archive(zip_path, checksum, "BTCUSDT", "2026-11-12")

    def test_zip_with_extra_entry_is_rejected(self):
        zip_path, checksum = self._make_archive(extra={"unexpected.txt": "not allowed"})
        with self.assertRaisesRegex(ArchiveValidationError, "exactly one CSV"):
            validate_archive(zip_path, checksum, "BTCUSDT", "2026-11-12")

    def test_zip_with_wrong_member_path_is_rejected(self):
        zip_path, checksum = self._make_archive(extra=None)
        with zipfile.ZipFile(zip_path, "w") as zipped:
            zipped.writestr("../BTCUSDT-aggTrades-2026-11-12.csv",
                            "1,100,0.1,10,10,1794441600000000,False,True\n")
        checksum.write_text(hashlib.sha256(zip_path.read_bytes()).hexdigest(), encoding="utf-8")
        with self.assertRaisesRegex(ArchiveValidationError, "must contain only"):
            validate_archive(zip_path, checksum, "BTCUSDT", "2026-11-12")

    def test_checksum_filename_must_match(self):
        zip_path, checksum = self._make_archive()
        digest = hashlib.sha256(zip_path.read_bytes()).hexdigest()
        checksum.write_text(f"{digest}  another.zip\n", encoding="utf-8")
        with self.assertRaisesRegex(ArchiveValidationError, "filename does not match"):
            validate_archive(zip_path, checksum, "BTCUSDT", "2026-11-12")


    def test_corrupt_zip_is_rejected_after_checksum_matches(self):
        zip_path = self.root / "BTCUSDT-aggTrades-2026-11-12.zip"
        zip_path.write_bytes(b"this is not a zip archive")
        checksum = self.root / (zip_path.name + ".CHECKSUM")
        checksum.write_text(
            hashlib.sha256(zip_path.read_bytes()).hexdigest(), encoding="utf-8"
        )
        with self.assertRaisesRegex(ArchiveValidationError, "corrupt ZIP"):
            validate_archive(zip_path, checksum, "BTCUSDT", "2026-11-12")

    def test_empty_csv_is_rejected(self):
        zip_path, checksum = self._make_archive(rows=[])
        with self.assertRaisesRegex(ArchiveValidationError, "no data rows"):
            validate_archive(zip_path, checksum, "BTCUSDT", "2026-11-12")

    def test_filename_must_match_symbol_and_date(self):
        zip_path, checksum = self._make_archive()
        with self.assertRaisesRegex(ArchiveValidationError, "archive filename must be"):
            validate_archive(zip_path, checksum, "ETHUSDT", "2026-11-12")


if __name__ == "__main__":
    unittest.main()
