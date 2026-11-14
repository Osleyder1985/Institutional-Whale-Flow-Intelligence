import hashlib
import json
import tempfile
import unittest
from pathlib import Path
from urllib.error import HTTPError

from scripts.observe_policy_sources import (
    ObservationError, AllowlistedRedirectHandler, observe_source,
    run_observations, write_observation,
)


class FakeResponse:
    status = 200
    def __init__(self, body, headers=None, url="https://raw.githubusercontent.com/policy_a/policy.txt"):
        self.body = body
        self.headers = headers or {}
        self.url = url
    def read(self, size=-1):
        data, self.body = self.body[:size], self.body[size:]
        return data
    def geturl(self):
        return self.url
    def getcode(self):
        return self.status
    def __enter__(self):
        return self
    def __exit__(self, *args):
        return False


class FakeOpener:
    def __init__(self, response=None, error=None):
        self.response, self.error = response, error
    def open(self, request, timeout=0):
        if self.error:
            raise self.error
        return self.response


def source(baseline=None):
    item = {
        "document_id": "policy_a", "provider": "Example",
        "url": "https://raw.githubusercontent.com/policy_a/policy.txt", "filename": "policy.txt",
        "observed_version": "v1", "url_is_mutable": True,
        "redistribution_status": "NOT_ASSESSED",
    }
    if baseline:
        item["baseline_sha256"] = baseline
    return item


class PolicySourceObservationTests(unittest.TestCase):
    def test_identical_bytes_are_unchanged_even_if_etag_changes(self):
        body = b"policy-v1"
        record = observe_source(
            source(hashlib.sha256(body).hexdigest()),
            FakeOpener(FakeResponse(body, {"ETag": '"new-etag"'})),
            observed_at="2026-11-14T00:00:00Z",
        )
        self.assertEqual(record["change_status"], "UNCHANGED")
        self.assertEqual(record["etag"], '"new-etag"')
        self.assertEqual(record["sha256"], hashlib.sha256(body).hexdigest())

    def test_changed_bytes_are_flagged_without_replacing_baseline(self):
        baseline = hashlib.sha256(b"old").hexdigest()
        record = observe_source(source(baseline), FakeOpener(FakeResponse(b"new")))
        self.assertEqual(record["change_status"], "CONTENT_CHANGED")
        self.assertEqual(record["baseline_sha256"], baseline)
        self.assertNotEqual(record["sha256"], baseline)

    def test_no_baseline_is_not_assumed_unchanged(self):
        record = observe_source(source(), FakeOpener(FakeResponse(b"first")))
        self.assertEqual(record["change_status"], "BASELINE_NOT_ESTABLISHED")

    def test_source_unavailable_is_review_required_not_revocation(self):
        error = HTTPError("https://raw.githubusercontent.com/policy_a/policy.txt", 404, "Not Found", {}, None)
        record = observe_source(source("a" * 64), FakeOpener(error=error))
        self.assertEqual(record["observation_status"], "SOURCE_UNAVAILABLE")
        self.assertEqual(record["change_status"], "REVIEW_REQUIRED")
        self.assertEqual(record["baseline_sha256"], "a" * 64)

    def test_content_length_mismatch_rejected(self):
        with self.assertRaisesRegex(ObservationError, "CONTENT_LENGTH_MISMATCH"):
            observe_source(source(), FakeOpener(FakeResponse(b"abc", {"Content-Length": "4"})))

    def test_final_url_host_change_rejected(self):
        with self.assertRaisesRegex(ObservationError, "FINAL_URL_NOT_ALLOWLISTED"):
            observe_source(source(), FakeOpener(FakeResponse(b"x", url="https://evil.example/file")))

    def test_observation_is_never_overwritten(self):
        with tempfile.TemporaryDirectory() as directory:
            record = observe_source(source(), FakeOpener(FakeResponse(b"x")), observed_at="2026-11-14T00:00:00Z")
            write_observation(record, directory)
            with self.assertRaisesRegex(ObservationError, "OBSERVATION_ALREADY_EXISTS"):
                write_observation(record, directory)

    def test_registry_rejects_unregistered_source_id(self):
        with tempfile.TemporaryDirectory() as directory:
            registry = Path(directory) / "registry.json"
            registry.write_text(json.dumps({"manifest_version":"1.0.0","documents":[source()]}))
            with self.assertRaisesRegex(ObservationError, "SOURCE_ID_NOT_REGISTERED"):
                run_observations(registry, Path(directory)/"out", ["other"])

    def test_authorization_states_are_never_promoted(self):
        record = observe_source(source(), FakeOpener(FakeResponse(b"x")))
        self.assertEqual(record["authorization_status"], "NOT_GRANTED")
        self.assertEqual(record["legal_review_status"], "NOT_PERFORMED")


if __name__ == "__main__":
    unittest.main()
