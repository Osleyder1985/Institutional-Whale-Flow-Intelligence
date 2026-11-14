import hashlib
import io
import json
import unittest
import zipfile

from iwfi.audit_package_manifest import build_audit_package_manifest
from iwfi.audit_package_zip import (
    MANIFEST_PATH, RETENTION_PATH, build_audit_package_zip, verify_audit_package_zip,
)

ROOT_HASH = hashlib.sha256(b"synthetic reconstruction manifest").hexdigest()
EVALUATED = "2026-11-14T13:00:00Z"


def fixture():
    payloads = {
        "reconstruction/manifest-v1.2.json": b"synthetic reconstruction manifest",
        "claims/root-claim.json": b'{"claim_id":"synthetic"}',
        "registry/actor-registry.json": b'{"contract_version":"1.2.0"}',
        "snapshots/evidence-001.bin": b"synthetic evidence bytes",
    }
    roles = {
        "reconstruction/manifest-v1.2.json": ("RECONSTRUCTION_MANIFEST", "application/json"),
        "claims/root-claim.json": ("ROOT_CLAIM", "application/json"),
        "registry/actor-registry.json": ("ACTOR_REGISTRY", "application/json"),
        "snapshots/evidence-001.bin": ("EVIDENCE_SNAPSHOT", "application/octet-stream"),
    }
    artifacts = [
        {"path": path, "role": roles[path][0], "media_type": roles[path][1], "content": content}
        for path, content in payloads.items()
    ]
    manifest = build_audit_package_manifest(
        package_id="synthetic-audit-package",
        reconstruction_manifest_hash=ROOT_HASH, artifacts=artifacts)
    return manifest, payloads


def authorization_context(manifest, evaluated_at=EVALUATED):
    authorizations, policies, lineage = [], [], {}
    for index, item in enumerate(manifest["artifacts"]):
        source = "source:" + item["path"]
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
            "status": "ACTIVE",
            "valid_from_utc": "2026-01-01T00:00:00Z",
            "expires_at_utc": "2027-01-01T00:00:00Z",
            "allowed_actions": ["RETAIN_LOCAL"],
            "prohibited_actions": [],
        })
    return {
        "package_mode": "LOCAL_ONLY",
        "evaluated_at_utc": evaluated_at,
        "artifact_authorizations": authorizations,
        "source_policies": policies,
        "source_lineage": lineage,
    }


def build(manifest, payloads, context=None):
    return build_audit_package_zip(
        manifest=manifest, artifacts_by_path=payloads,
        authorization_context=context or authorization_context(manifest))


class AuditPackageZipTests(unittest.TestCase):
    def _manifest(self, archive):
        with zipfile.ZipFile(io.BytesIO(archive), "r") as source:
            return json.loads(source.read(MANIFEST_PATH).decode("utf-8"))

    def verify(self, archive, context=None, expected=ROOT_HASH):
        try:
            manifest = self._manifest(archive)
        except zipfile.BadZipFile:
            return verify_audit_package_zip(
                archive_bytes=archive,
                expected_reconstruction_manifest_hash=expected,
                authorization_context=context or {})
        return verify_audit_package_zip(
            archive_bytes=archive,
            expected_reconstruction_manifest_hash=expected,
            authorization_context=context or authorization_context(manifest))

    def test_export_is_byte_for_byte_reproducible_and_local_only(self):
        manifest, payloads = fixture()
        first = build(manifest, payloads)
        second = build(manifest, payloads)
        self.assertEqual(first, second)
        result = self.verify(first)
        self.assertEqual(result["status"], "AUDIT_PACKAGE_VERIFIED")
        self.assertEqual(result["retention_status"], "RETENTION_AUTHORIZED")
        self.assertEqual(result["package_mode"], "LOCAL_ONLY")
        with zipfile.ZipFile(io.BytesIO(first), "r") as archive:
            decision = json.loads(archive.read(RETENTION_PATH).decode("utf-8"))
        self.assertEqual(len(decision["authorization_evidence"]["artifact_authorizations"]), 4)
        schema_path = __import__("pathlib").Path(__file__).resolve().parents[1] / "schemas" / "audit-package-retention-decision-v1.0.schema.json"
        import json as json_module
        schema = json_module.loads(schema_path.read_text(encoding="utf-8"))
        Draft202012Validator.check_schema(schema)
        Draft202012Validator(schema).validate(decision)

    def test_reconstruction_manifest_payload_must_be_included_and_bound(self):
        artifacts = [{
            "path": "claims/root-claim.json", "role": "ROOT_CLAIM",
            "media_type": "application/json", "content": b'{"claim_id":"synthetic"}'
        }]
        manifest = build_audit_package_manifest(
            package_id="missing-root-manifest",
            reconstruction_manifest_hash=ROOT_HASH, artifacts=artifacts)
        with self.assertRaisesRegex(ValueError, "reconstruction manifest artifact"):
            build_audit_package_zip(
                manifest=manifest,
                artifacts_by_path={"claims/root-claim.json": b'{"claim_id":"synthetic"}'},
                authorization_context=authorization_context(manifest))

    def test_inventory_must_verify_before_export(self):
        manifest, payloads = fixture()
        payloads["claims/root-claim.json"] += b"tamper"
        with self.assertRaisesRegex(ValueError, "inventory must verify"):
            build(manifest, payloads)

    def test_missing_artifact_authorization_rejects_package(self):
        manifest, payloads = fixture()
        context = authorization_context(manifest)
        context["artifact_authorizations"].pop()
        with self.assertRaisesRegex(ValueError, "ARTIFACT_AUTHORIZATION_INVENTORY_MISMATCH"):
            build(manifest, payloads, context)

    def test_expired_artifact_authorization_rejects_package(self):
        manifest, payloads = fixture()
        context = authorization_context(manifest)
        context["artifact_authorizations"][0]["expires_at_utc"] = "2026-11-14T12:00:00Z"
        with self.assertRaisesRegex(ValueError, "EXPIRED_OR_NOT_YET_VALID"):
            build(manifest, payloads, context)

    def test_incomplete_artifact_authorization_rejects_package(self):
        manifest, payloads = fixture()
        context = authorization_context(manifest)
        del context["artifact_authorizations"][0]["expires_at_utc"]
        with self.assertRaisesRegex(ValueError, "AUTHORIZATION_INCOMPLETE"):
            build(manifest, payloads, context)

    def test_contradictory_source_policy_rejects_package(self):
        manifest, payloads = fixture()
        context = authorization_context(manifest)
        context["source_policies"][0]["prohibited_actions"] = ["RETAIN_LOCAL"]
        with self.assertRaisesRegex(ValueError, "CONTRADICTORY_SOURCE_POLICY"):
            build(manifest, payloads, context)

    def test_transitive_source_policy_is_required(self):
        manifest, payloads = fixture()
        context = authorization_context(manifest)
        child = context["artifact_authorizations"][0]["source_ids"][0]
        context["source_lineage"][child] = ["upstream:missing-policy"]
        context["source_lineage"]["upstream:missing-policy"] = []
        with self.assertRaisesRegex(ValueError, "SOURCE_POLICY_MISSING"):
            build(manifest, payloads, context)

    def test_external_distribution_or_sync_permission_is_rejected(self):
        manifest, payloads = fixture()
        context = authorization_context(manifest)
        context["source_policies"][0]["allowed_actions"].append("DISTRIBUTE")
        with self.assertRaisesRegex(ValueError, "EXTERNAL_DISTRIBUTION_OR_SYNC"):
            build(manifest, payloads, context)

    def test_non_local_package_mode_is_rejected(self):
        manifest, payloads = fixture()
        context = authorization_context(manifest)
        context["package_mode"] = "DISTRIBUTION"
        with self.assertRaisesRegex(ValueError, "PACKAGE_MODE_NOT_LOCAL_ONLY"):
            build(manifest, payloads, context)

    def test_policy_change_after_package_creation_fails_verification(self):
        manifest, payloads = fixture()
        context = authorization_context(manifest)
        archive = build(manifest, payloads, context)
        changed = authorization_context(manifest)
        changed["source_policies"][0]["rights_ref"] = "changed-rights-reference"
        result = self.verify(archive, changed)
        self.assertEqual(result["reason"], "RETENTION_AUTHORIZATION_FAILED")
        self.assertEqual(result["retention_result"]["reason"], "AUTHORIZATION_OR_POLICY_CHANGED")

    def test_expiry_after_package_creation_fails_verification(self):
        manifest, payloads = fixture()
        archive = build(manifest, payloads)
        later = authorization_context(manifest, evaluated_at="2027-01-01T00:00:00Z")
        result = self.verify(archive, later)
        self.assertEqual(result["reason"], "RETENTION_AUTHORIZATION_FAILED")
        self.assertIn("EXPIRED", result["retention_result"]["reason"])

    def test_archive_mutation_and_truncation_fail(self):
        manifest, payloads = fixture()
        archive = build(manifest, payloads)
        self.assertNotEqual(self.verify(archive[:-12])["status"], "AUDIT_PACKAGE_VERIFIED")
        changed = bytearray(archive)
        changed[len(changed) // 2] ^= 0x01
        self.assertNotEqual(self.verify(bytes(changed))["status"], "AUDIT_PACKAGE_VERIFIED")

    def test_wrong_reconstruction_binding_fails(self):
        manifest, payloads = fixture()
        archive = build(manifest, payloads)
        other = hashlib.sha256(b"another reconstruction").hexdigest()
        result = self.verify(archive, expected=other)
        self.assertEqual(result["reason"], "INVENTORY_VERIFICATION_FAILED")

    def test_duplicate_archive_entries_fail(self):
        manifest, payloads = fixture()
        archive = build(manifest, payloads)
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
        archive = build(manifest, payloads)
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

    def test_control_manifest_paths_are_reserved(self):
        manifest, payloads = fixture()
        payloads[RETENTION_PATH] = b"shadow"
        with self.assertRaisesRegex(ValueError, "reserved"):
            build(manifest, payloads)


if __name__ == "__main__":
    unittest.main()
