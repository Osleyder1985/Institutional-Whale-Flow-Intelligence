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
            self.assertIn("onedrive", result["risk_details"][0])

    def test_symlinked_ancestor_is_flagged_before_path_resolution(self):
        with tempfile.TemporaryDirectory() as temp:
            base = Path(temp)
            target = base / "actual-storage"
            target.mkdir()
            child = target / "artifacts"
            child.mkdir()
            alias = base / "redirected-storage"
            try:
                alias.symlink_to(target, target_is_directory=True)
            except (OSError, NotImplementedError) as exc:
                self.skipTest(f"directory symlinks unavailable in this environment: {exc}")

            result = inspect_storage_root(alias / "artifacts")
            self.assertEqual(result["sync_verification"], "NOT_VERIFIED")
            self.assertEqual(result["sync_risk"], "RISK_DETECTED")
            self.assertTrue(result["reparse_point_ancestors"])
            self.assertTrue(any("redirected-storage" in item for item in result["reparse_point_ancestors"]))
            self.assertFalse(result["capture_authorized"])

    def test_missing_path_blocks(self):
        with tempfile.TemporaryDirectory() as temp:
            missing = Path(temp) / "not-created"
            with self.assertRaisesRegex(ValueError, "already exist"):
                inspect_storage_root(missing)


if __name__ == "__main__":
    unittest.main()
