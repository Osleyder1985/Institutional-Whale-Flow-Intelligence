import json
import unittest
from pathlib import Path

from jsonschema import Draft202012Validator

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from iwfi.signed_audit_package import (
    sign_audit_package, verify_audit_package_signature,
)


def keypair():
    private = Ed25519PrivateKey.generate()
    return (
        private.private_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PrivateFormat.PKCS8,
            encryption_algorithm=serialization.NoEncryption()),
        private.public_key().public_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PublicFormat.SubjectPublicKeyInfo),
    )


class SignedAuditPackageTests(unittest.TestCase):
    def setUp(self):
        self.private, self.public = keypair()
        self.archive = b"synthetic deterministic IWFI ZIP bytes"

    def sign(self):
        return sign_audit_package(
            archive_bytes=self.archive,
            private_key_pem=self.private,
            issued_at_utc="2026-11-14T12:00:00Z")

    def test_detached_signature_verifies_with_pinned_public_key(self):
        signature = self.sign()
        result = verify_audit_package_signature(
            archive_bytes=self.archive, signature_envelope=signature,
            trusted_public_key_pem=self.public)
        self.assertEqual(result["status"], "SIGNATURE_VERIFIED")

    def test_archive_mutation_is_detected(self):
        signature = self.sign()
        result = verify_audit_package_signature(
            archive_bytes=self.archive + b"x", signature_envelope=signature,
            trusted_public_key_pem=self.public)
        self.assertEqual(result["reason"], "ARCHIVE_SIZE_MISMATCH")

    def test_wrong_public_key_is_rejected(self):
        signature = self.sign()
        _, other_public = keypair()
        result = verify_audit_package_signature(
            archive_bytes=self.archive, signature_envelope=signature,
            trusted_public_key_pem=other_public)
        self.assertEqual(result["reason"], "TRUSTED_KEY_FINGERPRINT_MISMATCH")

    def test_signature_body_tampering_is_detected(self):
        signature = self.sign()
        signature["issued_at_utc"] = "2026-11-15T12:00:00Z"
        result = verify_audit_package_signature(
            archive_bytes=self.archive, signature_envelope=signature,
            trusted_public_key_pem=self.public)
        self.assertEqual(result["reason"], "SIGNATURE_OR_FORMAT_INVALID")

    def test_invalid_timestamp_is_rejected(self):
        with self.assertRaises(ValueError):
            sign_audit_package(
                archive_bytes=self.archive, private_key_pem=self.private,
                issued_at_utc="2026-11-14T12:00:00+00:00")

    def test_wrong_archive_bytes_type_is_rejected(self):
        with self.assertRaises(ValueError):
            sign_audit_package(
                archive_bytes="not bytes", private_key_pem=self.private,
                issued_at_utc="2026-11-14T12:00:00Z")

    def test_signature_schema_is_valid_and_envelope_conforms(self):
        signature = self.sign()
        schema_path = Path(__file__).resolve().parents[1] / "schemas" / "signed-audit-package-v1.0.schema.json"
        schema = json.loads(schema_path.read_text(encoding="utf-8"))
        Draft202012Validator.check_schema(schema)
        Draft202012Validator(schema, format_checker=Draft202012Validator.FORMAT_CHECKER).validate(signature)


if __name__ == "__main__":
    unittest.main()
