import copy
import hashlib
import io
import unittest
import zipfile

from iwfi.audit_package_manifest import build_audit_package_manifest
from iwfi.audit_package_zip import (
    MANIFEST_PATH, build_audit_package_zip, verify_audit_package_zip,
)


ROOT_HASH = hashlib.sha256(b"synthetic reconstruction manifest").hexdigest()


def fixture():
    payloads = {
        "claims/root-claim.json": b'{"claim_id":"synthetic"}',
        "registry/actor-registry.json": b'{"contract_version":"1.2.0"}',
        "snapshots/evidence-001.bin": b"synthetic evidence bytes",
    }
    artifacts = [
        {"path": path, "role": role, "media_type": media_type, "content": content}
        for (path, role, media_type, content) in [
            ("reconstruction/manifest-v1.2.json", "RECONSTRUCTION_MANIFEST", "application/json", payloads["reconstruction/manifest-v1.2.json"]),
            ("claims/root-claim.json", "ROOT_CLAIM", "application/json", payloads["claims/root-claim.json"]),
            ("registry/actor-registry.json", "ACTOR_REGISTRY", "application/json", payloads["registry/actor-registry.json"]),
            ("snapshots/evidence-001.bin", "EVIDENCE_SNAPSHOT", "application/octet-stream", payloads["snapshots/evidence-001.bin"]),
        ]
    ]
    manifest = build_audit_package_manifest(
        package_id="synthetic-audit-package",
        reconstruction_manifest_hash=ROOT_HASH, artifacts=artifacts)
    return manifest, payloads


class AuditPackageZipTests(unittest.TestCase):
    def verify(self, archive):
        return verify_audit_package_zip(
            archive_bytes=archive,
            expected_reconstruction_manifest_hash=ROOT_HASH)

    def test_export_is_byte_for_byte_reproducible(self):
        manifest, payloads = fixture()
        first = build_audit_package_zip(manifest=manifest, artifacts_by_path=payloads)
        second = build_audit_package_zip(manifest=manifest, artifacts_by_path=payloads)
        self.assertEqual(first, second)
        self.assertEqual(self.verify(first)["status"], "AUDIT_PACKAGE_VERIFIED")

    def test_reconstruction_manifest_payload_must_be_included_and_bound(self):
        artifacts = [
            {"path": "claims/root-claim.json", "role": "ROOT_CLAIM",
             "media_type": "application/json", "content": b'{"claim_id":"synthetic"}'}
        ]
        manifest = build_audit_package_manifest(
            package_id="missing-root-manifest",
            reconstruction_manifest_hash=ROOT_HASH, artifacts=artifacts)
        with self.assertRaisesRegex(ValueError, "reconstruction manifest artifact"):
            build_audit_package_zip(manifest=manifest, artifacts_by_path={
                "claims/root-claim.json": b'{"claim_id":"synthetic"}'})

    def test_inventory_must_verify_before_export(self):
        manifest, payloads = fixture()
        payloads["claims/root-claim.json"] += b"tamper"
        with self.assertRaisesRegex(ValueError, "must verify"):
            build_audit_package_zip(manifest=manifest, artifacts_by_path=payloads)

    def test_archive_mutation_and_truncation_fail(self):
        manifest, payloads = fixture()
        archive = build_audit_package_zip(manifest=manifest, artifacts_by_path=payloads)
        self.assertNotEqual(self.verify(archive[:-12])["status"], "AUDIT_PACKAGE_VERIFIED")
        changed = bytearray(archive)
        changed[len(changed) // 2] ^= 0x01
        self.assertNotEqual(self.verify(bytes(changed))["status"], "AUDIT_PACKAGE_VERIFIED")

    def test_wrong_reconstruction_binding_fails(self):
        manifest, payloads = fixture()
        archive = build_audit_package_zip(manifest=manifest, artifacts_by_path=payloads)
        other = hashlib.sha256(b"another reconstruction").hexdigest()
        result = verify_audit_package_zip(
            archive_bytes=archive, expected_reconstruction_manifest_hash=other)
        self.assertEqual(result["reason"], "INVENTORY_VERIFICATION_FAILED")

    def test_duplicate_archive_entries_fail(self):
        manifest, payloads = fixture()
        archive = build_audit_package_zip(manifest=manifest, artifacts_by_path=payloads)
        duplicate = io.BytesIO()
        with zipfile.ZipFile(io.BytesIO(archive), "r") as source:
            with zipfile.ZipFile(duplicate, "w", compression=zipfile.ZIP_STORED) as target:
                for info in source.infolist():
                    target.writestr(info, source.read(info))
                target.writestr(MANIFEST_PATH, source.read(MANIFEST_PATH))
        self.assertEqual(self.verify(duplicate.getvalue())["reason"],
                         "DUPLICATE_ARCHIVE_ENTRY")

    def test_path_traversal_archive_entry_is_rejected(self):
        manifest, payloads = fixture()
        archive = build_audit_package_zip(manifest=manifest, artifacts_by_path=payloads)
        altered = io.BytesIO()
        with zipfile.ZipFile(io.BytesIO(archive), "r") as source:
            with zipfile.ZipFile(altered, "w", compression=zipfile.ZIP_STORED) as target:
                for info in source.infolist():
                    name = "../escape.bin" if info.filename == "claims/root-claim.json" else info.filename
                    rewritten = zipfile.ZipInfo(name, date_time=info.date_time)
                    rewritten.compress_type = info.compress_type
                    rewritten.create_system = info.create_system
                    rewritten.external_attr = info.external_attr
                    target.writestr(rewritten, source.read(info))
        self.assertEqual(self.verify(altered.getvalue())["reason"], "UNSAFE_ARCHIVE_PATH")

    def test_manifest_cannot_be_supplied_as_an_artifact(self):
        manifest, payloads = fixture()
        payloads[MANIFEST_PATH] = b"shadow"
        with self.assertRaisesRegex(ValueError, "reserved"):
            build_audit_package_zip(manifest=manifest, artifacts_by_path=payloads)


if __name__ == "__main__":
    unittest.main()
