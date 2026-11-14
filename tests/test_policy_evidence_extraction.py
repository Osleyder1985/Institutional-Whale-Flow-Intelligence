import hashlib
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from scripts.extract_policy_evidence import (
    BUNDLE_NAME,
    MANIFEST_NAME,
    EvidenceExtractionError,
    build_extraction_bundle,
    write_bundle,
)


class PolicyEvidenceExtractionTests(unittest.TestCase):
    def _fixture(self, root: Path, filename="terms.md", body=b"# Section 4.1 Permitted use\nPersonal research and non-commercial use.\n"):
        digest = hashlib.sha256(body).hexdigest()
        (root / filename).write_bytes(body)
        manifest = {
            "manifest_version": "1.0.0",
            "storage_scope": "LOCAL_ONLY",
            "external_upload_performed": False,
            "external_sync_performed": False,
            "authorization_status": "NOT_GRANTED",
            "legal_review_status": "NOT_PERFORMED",
            "documents": [{
                "document_id": "fixture_terms",
                "provider": "Fixture",
                "requested_url": "https://example.invalid/terms",
                "final_url": "https://example.invalid/terms",
                "retrieved_at_utc": "2026-11-14T00:00:00Z",
                "sha256": digest,
                "bytes_written": len(body),
                "local_filename": filename,
                "evidence_status": "CAPTURED_UNREVIEWED",
                "authorization_status": "NOT_GRANTED",
            }],
        }
        (root / MANIFEST_NAME).write_text(json.dumps(manifest), encoding="utf-8")
        return manifest

    def test_text_document_integrity_and_structural_locators(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            self._fixture(root)
            bundle = build_extraction_bundle(root)
            self.assertTrue(bundle["technical_integrity_verified"])
            self.assertEqual(bundle["bundle_scope"], "LOCAL_ONLY")
            self.assertEqual(bundle["authorization_status"], "NOT_GRANTED")
            self.assertEqual(bundle["legal_review_status"], "NOT_PERFORMED")
            document = bundle["documents"][0]
            self.assertIn("Personal research", document["text"])
            self.assertTrue(any(x["kind"] == "section_heading" for x in document["structural_locators"]))
            self.assertTrue(any(x["kind"] == "topic_locator" for x in document["structural_locators"]))

    def test_sha256_mismatch_is_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            manifest = self._fixture(root)
            manifest["documents"][0]["sha256"] = "0" * 64
            (root / MANIFEST_NAME).write_text(json.dumps(manifest), encoding="utf-8")
            with self.assertRaisesRegex(EvidenceExtractionError, "SNAPSHOT_SHA256_MISMATCH"):
                build_extraction_bundle(root)

    def test_byte_count_mismatch_is_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            manifest = self._fixture(root)
            manifest["documents"][0]["bytes_written"] += 1
            (root / MANIFEST_NAME).write_text(json.dumps(manifest), encoding="utf-8")
            with self.assertRaisesRegex(EvidenceExtractionError, "SNAPSHOT_BYTE_COUNT_MISMATCH"):
                build_extraction_bundle(root)

    def test_incomplete_manifest_is_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            manifest = {
                "storage_scope": "LOCAL_ONLY",
                "external_upload_performed": False,
                "external_sync_performed": False,
                "documents": [],
            }
            (root / MANIFEST_NAME).write_text(json.dumps(manifest), encoding="utf-8")
            with self.assertRaisesRegex(EvidenceExtractionError, "EVIDENCE_DOCUMENT_SET_EMPTY"):
                build_extraction_bundle(root)

    def test_path_traversal_filename_is_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            manifest = self._fixture(root)
            manifest["documents"][0]["local_filename"] = r"..\\outside.md"
            (root / MANIFEST_NAME).write_text(json.dumps(manifest), encoding="utf-8")
            with self.assertRaisesRegex(EvidenceExtractionError, "SNAPSHOT_FILENAME_INVALID"):
                build_extraction_bundle(root)

    def test_output_bundle_is_never_overwritten(self):
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / BUNDLE_NAME
            output.write_text("previous", encoding="utf-8")
            with self.assertRaisesRegex(EvidenceExtractionError, "OUTPUT_BUNDLE_ALREADY_EXISTS"):
                write_bundle({"bundle_version": "1.0.0"}, output)
            self.assertEqual(output.read_text(encoding="utf-8"), "previous")

    def test_pdf_requires_optional_pypdf_dependency(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            self._fixture(root, filename="terms.pdf", body=b"%PDF-fake")
            with patch.dict("sys.modules", {"pypdf": None}):
                with self.assertRaisesRegex(EvidenceExtractionError, "PDF_EXTRACTION_REQUIRES_PYPDF_INSTALLATION"):
                    build_extraction_bundle(root)


if __name__ == "__main__":
    unittest.main()
