import copy
import hashlib
import json
import unittest
from pathlib import Path

from jsonschema import Draft202012Validator

from iwfi.audit_package_manifest import build_audit_package_manifest
from iwfi.audit_package_zip import build_audit_package_zip
from iwfi.signed_journal_checkpoints import generate_ed25519_keypair
from iwfi.audit_package_signature import (
    sign_audit_package_archive, verify_signed_audit_package_archive,
)

ROOT_HASH = hashlib.sha256(b"synthetic reconstruction manifest").hexdigest()


def package_fixture():
    items = [
        ("reconstruction/manifest-v1.2.json", "RECONSTRUCTION_MANIFEST", "application/json", b"synthetic reconstruction manifest"),
        ("claims/root-claim.json", "ROOT_CLAIM", "application/json", b'{"claim_id":"synthetic"}'),
        ("snapshots/evidence.bin", "EVIDENCE_SNAPSHOT", "application/octet-stream", b"synthetic evidence"),
    ]
    manifest = build_audit_package_manifest(
        package_id="signed-synthetic-package",
        reconstruction_manifest_hash=ROOT_HASH,
        artifacts=[{"path": p, "role": r, "media_type": m,
                    "source_ids": ["source:" + p], "content": b}
                   for p, r, m, b in items])
    payloads = {p: b for p, _, _, b in items}
    authorizations, policies, lineage = [], [], {}
    for index, item in enumerate(manifest["artifacts"]):
        source = item["source_ids"][0]
        lineage[source] = []
        authorizations.append({
            "authorization_id": "auth-" + str(index),
            "artifact_path": item["path"],
            "artifact_sha256": item["sha256"],
            "source_ids": [source],
            "action": "RETAIN_LOCAL",
            "status": "AUTHORIZED",
            "valid_from_utc": "2026-01-01T00:00:00Z",
            "expires_at_utc": "2027-01-01T00:00:00Z",
        })
        policies.append({
            "policy_id": "policy-" + str(index),
            "policy_version": "1.0",
            "source_id": source,
            "rights_ref": "synthetic-rights:" + str(index),
            "issuer": "Synthetic test issuer",
            "document_ref": "synthetic-policy-document:" + str(index),
            "document_sha256": hashlib.sha256(("synthetic policy " + str(index)).encode()).hexdigest(),
            "retrieved_at_utc": "2026-11-13T00:00:00Z",
            "reviewed_at_utc": "2026-11-13T12:00:00Z",
            "review_status": "VERIFIED",
            "reviewer_id": "synthetic-reviewer",
            "review_scope": ["RETAIN_LOCAL", "HISTORICAL_SNAPSHOTS"],
            "status": "ACTIVE",
            "valid_from_utc": "2026-01-01T00:00:00Z",
            "expires_at_utc": "2027-01-01T00:00:00Z",
            "allowed_actions": ["RETAIN_LOCAL"],
            "prohibited_actions": [],
        })
    context = {
        "package_mode": "LOCAL_ONLY",
        "evaluated_at_utc": "2026-11-14T13:00:00Z",
        "artifact_authorizations": authorizations,
        "source_policies": policies,
        "source_lineage": lineage,
    }
    archive = build_audit_package_zip(
        manifest=manifest, artifacts_by_path=payloads,
        authorization_context=context)
    return manifest, archive, context


class AuditPackageSignatureTests(unittest.TestCase):
    def setUp(self):
        self.keys = generate_ed25519_keypair()
        self.manifest, self.archive, self.authorization_context = package_fixture()
        self.signature = sign_audit_package_archive(
            archive_bytes=self.archive,
            package_manifest_hash=self.manifest["manifest_hash"],
            private_key_pem=self.keys["private_key_pem"])

    def verify(self, archive=None, signature=None, public_key=None, context=None):
        return verify_signed_audit_package_archive(
            archive_bytes=self.archive if archive is None else archive,
            signature=self.signature if signature is None else signature,
            trusted_public_key_pem=self.keys["public_key_pem"] if public_key is None else public_key,
            expected_reconstruction_manifest_hash=ROOT_HASH,
            authorization_context=self.authorization_context if context is None else context)

    def test_detached_signature_verifies_archive_and_inventory(self):
        self.assertEqual(self.verify()["status"], "SIGNED_AUDIT_PACKAGE_VERIFIED")

    def test_signature_conforms_to_versioned_json_schema(self):
        schema_path = Path(__file__).resolve().parents[1] / "schemas" / "audit-package-signature-v1.0.schema.json"
        schema = json.loads(schema_path.read_text(encoding="utf-8"))
        Draft202012Validator.check_schema(schema)
        Draft202012Validator(schema).validate(self.signature)

    def test_archive_byte_mutation_is_rejected(self):
        changed = self.archive + b"tamper"
        self.assertEqual(self.verify(archive=changed)["reason"], "ARCHIVE_HASH_MISMATCH")

    def test_wrong_trusted_key_is_rejected(self):
        other = generate_ed25519_keypair()
        self.assertEqual(self.verify(public_key=other["public_key_pem"])["reason"],
                         "TRUSTED_KEY_FINGERPRINT_MISMATCH")

    def test_signature_metadata_tampering_is_rejected(self):
        changed = copy.deepcopy(self.signature)
        changed["package_manifest_hash"] = "f" * 64
        self.assertEqual(self.verify(signature=changed)["reason"],
                         "SIGNATURE_OR_FORMAT_INVALID")

    def test_invalid_zip_with_valid_signature_is_not_accepted(self):
        bad_archive = b"not a zip archive"
        signature = sign_audit_package_archive(
            archive_bytes=bad_archive,
            package_manifest_hash=self.manifest["manifest_hash"],
            private_key_pem=self.keys["private_key_pem"])
        self.assertEqual(self.verify(archive=bad_archive, signature=signature)["status"],
                         "PACKAGE_INVALID")

    def test_signature_verification_rechecks_retention_policy(self):
        changed = dict(self.authorization_context)
        changed["source_policies"] = [dict(item) for item in self.authorization_context["source_policies"]]
        changed["source_policies"][0]["rights_ref"] = "revoked-or-changed-policy"
        result = self.verify(context=changed)
        self.assertEqual(result["status"], "PACKAGE_INVALID")
        self.assertEqual(result["package_result"]["reason"], "RETENTION_AUTHORIZATION_FAILED")


if __name__ == "__main__":
    unittest.main()
