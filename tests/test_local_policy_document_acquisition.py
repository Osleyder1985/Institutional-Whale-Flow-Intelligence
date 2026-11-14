import copy
import hashlib
import json
import tempfile
import unittest
from pathlib import Path
from urllib.error import URLError
from unittest.mock import patch

from scripts.acquire_policy_documents import (
    AcquisitionError,
    DOCUMENTS,
    EXPECTED_DOCUMENT_IDS,
    MANIFEST_NAME,
    _download_one,
    _validate_document_id,
    _validate_url,
    acquire,
    load_source_manifest_payload,
)


class FakeResponse:
    def __init__(self, body=b"official-document", status=200, url=None, headers=None):
        self.body = body
        self.status = status
        self.url = url or DOCUMENTS["cc_by_nc_sa_4_0_legal_code"]["url"]
        self.headers = headers or {"Content-Type": "text/plain", "Content-Length": str(len(body)),
                                   "ETag": '"abc"', "Last-Modified": "Sat, 14 Nov 2026 00:00:00 GMT"}
        self.offset = 0

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False

    def read(self, size):
        block = self.body[self.offset:self.offset + size]
        self.offset += len(block)
        return block

    def getcode(self):
        return self.status

    def geturl(self):
        return self.url


class FailingResponse(FakeResponse):
    def read(self, size):
        if self.offset:
            raise URLError("simulated interrupted transfer")
        block = self.body[:4]
        self.offset = len(block)
        return block


class FakeOpener:
    def __init__(self, response):
        self.response = response

    def open(self, request, timeout):
        return self.response


class LocalDocumentAcquisitionTests(unittest.TestCase):
    def test_only_registered_document_ids_are_accepted(self):
        with self.assertRaisesRegex(AcquisitionError, "DOCUMENT_ID_NOT_ALLOWLISTED"):
            _validate_document_id("arbitrary_url")

    def test_only_exact_https_urls_are_accepted(self):
        with self.assertRaisesRegex(AcquisitionError, "URL_NOT_ALLOWLISTED"):
            _validate_url("http://creativecommons.org/licenses/by-nc-sa/4.0/legalcode.txt")
        with self.assertRaisesRegex(AcquisitionError, "URL_NOT_ALLOWLISTED"):
            _validate_url("https://evil.example/document.txt")
        with self.assertRaisesRegex(AcquisitionError, "URL_NOT_ALLOWLISTED"):
            _validate_url("https://creativecommons.org/other.txt")

    def test_source_manifest_must_be_complete_and_unique(self):
        from scripts.acquire_policy_documents import SOURCE_MANIFEST_PATH
        payload = json.loads(SOURCE_MANIFEST_PATH.read_text(encoding="utf-8"))
        incomplete = copy.deepcopy(payload)
        incomplete["documents"].pop()
        with self.assertRaisesRegex(AcquisitionError, "SOURCE_MANIFEST_INCOMPLETE"):
            load_source_manifest_payload(incomplete)
        duplicated = copy.deepcopy(payload)
        duplicated["documents"].append(copy.deepcopy(duplicated["documents"][0]))
        with self.assertRaisesRegex(AcquisitionError, "SOURCE_MANIFEST_DUPLICATE_ID"):
            load_source_manifest_payload(duplicated)

    def test_capture_hash_matches_independent_hash_of_exact_bytes(self):
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory)
            body = b"\x00original\xffbytes\n"
            response = FakeResponse(body=body)
            record = _download_one("cc_by_nc_sa_4_0_legal_code", output, FakeOpener(response))
            stored = (output / DOCUMENTS["cc_by_nc_sa_4_0_legal_code"]["filename"]).read_bytes()
            self.assertEqual(stored, body)
            self.assertEqual(record["sha256"], hashlib.sha256(stored).hexdigest())
            self.assertEqual(record["bytes_written"], len(body))
            self.assertEqual(record["authorization_status"], "NOT_GRANTED")

    def test_redirect_to_non_allowlisted_host_is_rejected_before_capture(self):
        with tempfile.TemporaryDirectory() as directory:
            response = FakeResponse(url="https://evil.example/payload")
            with self.assertRaisesRegex(AcquisitionError, "URL_NOT_ALLOWLISTED"):
                _download_one("cc_by_nc_sa_4_0_legal_code", Path(directory), FakeOpener(response))
            self.assertEqual(list(Path(directory).iterdir()), [])

    def test_non_200_response_is_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            with self.assertRaisesRegex(AcquisitionError, "HTTP_STATUS_NOT_SUCCESS"):
                _download_one("cc_by_nc_sa_4_0_legal_code", Path(directory),
                              FakeOpener(FakeResponse(status=206)))
            self.assertEqual(list(Path(directory).iterdir()), [])

    def test_content_length_mismatch_is_rejected_and_partial_file_removed(self):
        with tempfile.TemporaryDirectory() as directory:
            response = FakeResponse(headers={"Content-Length": "999", "Content-Type": "text/plain"})
            with self.assertRaisesRegex(AcquisitionError, "CONTENT_LENGTH_MISMATCH"):
                _download_one("cc_by_nc_sa_4_0_legal_code", Path(directory), FakeOpener(response))
            self.assertEqual(list(Path(directory).iterdir()), [])

    def test_interrupted_transfer_removes_partial_snapshot(self):
        with tempfile.TemporaryDirectory() as directory:
            with self.assertRaisesRegex(AcquisitionError, "NETWORK_RETRIEVAL_FAILED"):
                _download_one("cc_by_nc_sa_4_0_legal_code", Path(directory),
                              FakeOpener(FailingResponse()))
            self.assertEqual(list(Path(directory).iterdir()), [])

    def test_expected_sha256_mismatch_rejects_snapshot(self):
        with tempfile.TemporaryDirectory() as directory:
            with patch.dict(DOCUMENTS["cc_by_nc_sa_4_0_legal_code"], {"expected_sha256": "0" * 64}):
                with self.assertRaisesRegex(AcquisitionError, "EXPECTED_SHA256_MISMATCH"):
                    _download_one("cc_by_nc_sa_4_0_legal_code", Path(directory), FakeOpener(FakeResponse()))
            self.assertEqual(list(Path(directory).iterdir()), [])

    def test_existing_snapshot_is_never_overwritten(self):
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory)
            destination = output / DOCUMENTS["cc_by_nc_sa_4_0_legal_code"]["filename"]
            destination.write_bytes(b"previous-snapshot")
            with self.assertRaisesRegex(AcquisitionError, "SNAPSHOT_ALREADY_EXISTS"):
                _download_one("cc_by_nc_sa_4_0_legal_code", output, FakeOpener(FakeResponse()))
            self.assertEqual(destination.read_bytes(), b"previous-snapshot")

    def test_existing_manifest_prevents_any_network_request(self):
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory)
            (output / MANIFEST_NAME).write_text("{}", encoding="utf-8")
            with patch("scripts.acquire_policy_documents._download_one") as download:
                with self.assertRaisesRegex(AcquisitionError, "OUTPUT_MANIFEST_ALREADY_EXISTS"):
                    acquire(["cc_by_nc_sa_4_0_legal_code"], output)
                download.assert_not_called()

    def test_empty_or_duplicate_selection_is_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            with self.assertRaisesRegex(AcquisitionError, "DOCUMENT_SELECTION_EMPTY"):
                acquire([], directory)
            with self.assertRaisesRegex(AcquisitionError, "DUPLICATE_DOCUMENT_ID"):
                acquire(["cc_by_nc_sa_4_0_legal_code"] * 2, directory)

    def test_manifest_marks_capture_as_unreviewed_and_not_authorized(self):
        with tempfile.TemporaryDirectory() as directory:
            with patch("scripts.acquire_policy_documents._download_one") as download:
                download.return_value = {
                    "document_id": "cc_by_nc_sa_4_0_legal_code",
                    "sha256": "a" * 64,
                    "authorization_status": "NOT_GRANTED",
                    "evidence_status": "CAPTURED_UNREVIEWED",
                }
                manifest_path, manifest = acquire(["cc_by_nc_sa_4_0_legal_code"], directory)
            parsed = json.loads(manifest_path.read_text(encoding="utf-8"))
            self.assertEqual(parsed["storage_scope"], "LOCAL_ONLY")
            self.assertFalse(parsed["external_upload_performed"])
            self.assertFalse(parsed["external_sync_performed"])
            self.assertEqual(parsed["legal_review_status"], "NOT_PERFORMED")
            self.assertEqual(manifest["documents"][0]["authorization_status"], "NOT_GRANTED")


if __name__ == "__main__":
    unittest.main()
