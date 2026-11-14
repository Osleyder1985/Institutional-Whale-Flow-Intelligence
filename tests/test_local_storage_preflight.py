"""Tests for read-only local storage preflight."""
import tempfile
import unittest
from pathlib import Path

from iwfi.local_storage_preflight import inspect_storage_root


class LocalStoragePreflightTests(unittest.TestCase):
    def test_reports_measured_capacity_without_claiming_sync_verification(self):
        with tempfile.TemporaryDirectory() as temp:
            result = inspect_storage_root(temp)
            self.assertEqual(result["sync_verification"], "NOT_VERIFIED")
            self.assertFalse(result["capture_authorized"])
            self.assertGreater(result["total_bytes"], 0)
            self.assertGreaterEqual(result["free_bytes"], 0)
            self.assertIn("path", result)

    def test_sync_named_directory_is_flagged(self):
        with tempfile.TemporaryDirectory() as temp:
            sync_dir = Path(temp) / "OneDrive"
            sync_dir.mkdir()
            result = inspect_storage_root(sync_dir)
            self.assertEqual(result["sync_risk"], "RISK_DETECTED")
            self.assertIn("OneDrive", result["risk_details"][0])

    def test_missing_path_blocks(self):
        with tempfile.TemporaryDirectory() as temp:
            missing = Path(temp) / "not-created"
            with self.assertRaisesRegex(ValueError, "already exist"):
                inspect_storage_root(missing)


if __name__ == "__main__":
    unittest.main()
