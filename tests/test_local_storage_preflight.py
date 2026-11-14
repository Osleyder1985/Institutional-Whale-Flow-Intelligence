"""Tests for read-only local storage preflight."""
import contextlib
import io
import json
import tempfile
import unittest
from pathlib import Path

from iwfi.local_storage_preflight import inspect_storage_root, main


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
            self.assertIn("onedrive", result["risk_details"][0])

    def test_missing_path_blocks(self):
        with tempfile.TemporaryDirectory() as temp:
            missing = Path(temp) / "not-created"
            with self.assertRaisesRegex(ValueError, "already exist"):
                inspect_storage_root(missing)

    def test_cli_emits_machine_readable_report(self):
        with tempfile.TemporaryDirectory() as temp:
            output = io.StringIO()
            with contextlib.redirect_stdout(output):
                result = main(["--path", temp])
            self.assertEqual(result, 0)
            report = json.loads(output.getvalue())
            self.assertFalse(report["capture_authorized"])
            self.assertEqual(report["sync_verification"], "NOT_VERIFIED")


if __name__ == "__main__":
    unittest.main()
