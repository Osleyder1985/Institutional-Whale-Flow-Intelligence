import copy
import hashlib
import json
import unittest

from iwfi.audit_package_manifest import (
    build_audit_package_manifest, verify_audit_package_manifest,
)


ROOT_HASH = hashlib.sha256(b"synthetic reconstruction manifest").hexdigest()


def fixture():
    artifacts = [
        {"path": "claims/root-claim.json", "role": "ROOT_CLAIM",
         "media_type": "application/json", "content": b'{"claim_id":"synthetic"}'},
        {"path": "registry/actor-registry.json", "role": "ACTOR_REGISTRY",
         "media_type": "application/json", "content": b'{"contract_version":"1.2.0"}'},
        {"path": "snapshots/evidence-001.bin", "role": "EVIDENCE_SNAPSHOT",
         "media_type": "application/octet-stream", "content": b"synthetic evidence bytes"},
    ]
    manifest = build_audit_package_manifest(
        package_id="synthetic-audit-package", reconstruction_manifest_hash=ROOT_HASH,
        artifacts=artifacts)
    payloads = {item["path"]: item["content"] for item in artifacts}
    return manifest, payloads


class AuditPackageManifestTests(unittest.TestCase):
    def verify(self, manifest, payloads, expected=ROOT_HASH):
        return verify_audit_package_manifest(
            manifest=manifest, artifacts_by_path=payloads,
            expected_reconstruction_manifest_hash=expected)

    def test_exact_inventory_and_bytes_verify(self):
        manifest, payloads = fixture()
        result = self.verify(manifest, payloads)
        self.assertEqual(result["status"], "AUDIT_PACKAGE_VERIFIED")
        self.assertEqual(result["artifact_count"], 3)

    def test_payload_mutation_fails(self):
        manifest, payloads = fixture()
        payloads["claims/root-claim.json"] += b" "
        self.assertEqual(self.verify(manifest, payloads)["reason"],
                         "ARTIFACT_VERIFICATION_FAILED")

    def test_missing_or_extra_artifact_fails(self):
        manifest, payloads = fixture()
        payloads.pop("snapshots/evidence-001.bin")
        self.assertEqual(self.verify(manifest, payloads)["reason"],
                         "ARTIFACT_INVENTORY_MISMATCH")
        manifest, payloads = fixture()
        payloads["extra.txt"] = b"unlisted"
        self.assertEqual(self.verify(manifest, payloads)["reason"],
                         "ARTIFACT_INVENTORY_MISMATCH")

    def test_reconstruction_manifest_binding_is_required(self):
        manifest, payloads = fixture()
        other = hashlib.sha256(b"other root").hexdigest()
        self.assertEqual(self.verify(manifest, payloads, other)["reason"],
                         "RECONSTRUCTION_MANIFEST_BINDING_MISMATCH")

    def test_manifest_tampering_fails(self):
        manifest, payloads = fixture()
        changed = copy.deepcopy(manifest)
        changed["artifacts"][0]["role"] = "SUBSTITUTED"
        self.assertEqual(self.verify(changed, payloads)["reason"], "MANIFEST_HASH_MISMATCH")

    def test_duplicate_and_case_colliding_paths_are_rejected(self):
        with self.assertRaisesRegex(ValueError, "duplicate or case-colliding"):
            build_audit_package_manifest(
                package_id="p", reconstruction_manifest_hash=ROOT_HASH,
                artifacts=[
                    {"path":"Evidence/a.bin","role":"A","media_type":"x","content":b"a"},
                    {"path":"evidence/A.bin","role":"B","media_type":"x","content":b"b"},
                ])

    def test_path_traversal_and_windows_reserved_names_are_rejected(self):
        for path in ("../secret", "/absolute", "folder/../../secret",
                     "folder\\file.bin", "CON/secret.txt", "folder/name. "):
            with self.subTest(path=path):
                with self.assertRaises(ValueError):
                    build_audit_package_manifest(
                        package_id="p", reconstruction_manifest_hash=ROOT_HASH,
                        artifacts=[{"path":path,"role":"X","media_type":"x","content":b"x"}])

    def test_invalid_content_type_is_rejected(self):
        with self.assertRaisesRegex(ValueError, "exact bytes"):
            build_audit_package_manifest(
                package_id="p", reconstruction_manifest_hash=ROOT_HASH,
                artifacts=[{"path":"a.bin","role":"X","media_type":"x","content":"not bytes"}])


if __name__ == "__main__":
    unittest.main()
