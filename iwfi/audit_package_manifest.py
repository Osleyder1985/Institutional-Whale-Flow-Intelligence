"""Portable, offline audit-package inventory manifest (not an archive writer)."""
import hashlib
import json
import re

_CANON = "IWFI-JSON-C14N-1"
_HASH = re.compile(r"^[a-f0-9]{64}$")
_RESERVED = {"CON", "PRN", "AUX", "NUL"} | {
    f"{prefix}{n}" for prefix in ("COM", "LPT") for n in range(1, 10)
}


def _canonical(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"),
                      ensure_ascii=False, allow_nan=False).encode("utf-8")


def _sha(payload):
    return hashlib.sha256(payload).hexdigest()


def _validate_path(path):
    if not isinstance(path, str) or not path or path.startswith("/") or "\\" in path or ":" in path:
        raise ValueError("artifact path must be a safe relative POSIX path")
    if any(ord(char) < 32 or ord(char) == 127 for char in path):
        raise ValueError("artifact path contains control characters")
    parts = path.split("/")
    if any(part in {"", ".", ".."} or part.endswith((".", " ")) for part in parts):
        raise ValueError("artifact path contains unsafe segment")
    if any(part.split(".")[0].upper() in _RESERVED for part in parts):
        raise ValueError("artifact path uses a reserved Windows device name")
    return path


def build_audit_package_manifest(*, package_id, reconstruction_manifest_hash, artifacts):
    """Freeze an exact path inventory and SHA-256 of each supplied artifact byte string."""
    if not isinstance(package_id, str) or not package_id.strip():
        raise ValueError("package_id is required")
    if not isinstance(reconstruction_manifest_hash, str) or not _HASH.fullmatch(reconstruction_manifest_hash):
        raise ValueError("reconstruction_manifest_hash must be lowercase SHA-256 hex")
    if not isinstance(artifacts, list) or not artifacts:
        raise ValueError("at least one artifact is required")
    entries, seen, folded = [], set(), set()
    for artifact in artifacts:
        if not isinstance(artifact, dict):
            raise ValueError("artifact entry must be an object")
        path = _validate_path(artifact.get("path"))
        role, media_type, content = artifact.get("role"), artifact.get("media_type"), artifact.get("content")
        if not isinstance(role, str) or not role.strip():
            raise ValueError("artifact role is required")
        if not isinstance(media_type, str) or not media_type.strip():
            raise ValueError("artifact media_type is required")
        if not isinstance(content, bytes):
            raise ValueError("artifact content must be exact bytes")
        if path in seen or path.casefold() in folded:
            raise ValueError("duplicate or case-colliding artifact path")
        seen.add(path)
        folded.add(path.casefold())
        entries.append({"path": path, "role": role, "media_type": media_type,
                        "size_bytes": len(content), "hash_algorithm": "SHA-256",
                        "sha256": _sha(content)})
    entries.sort(key=lambda item: item["path"])
    manifest = {
        "manifest_version": "1.0.0",
        "package_id": package_id,
        "reconstruction_manifest_hash": reconstruction_manifest_hash,
        "canonicalization_version": _CANON,
        "artifacts": entries,
        "manifest_hash_algorithm": "SHA-256",
    }
    manifest["manifest_hash"] = _sha(_canonical(manifest))
    return manifest


def verify_audit_package_manifest(*, manifest, artifacts_by_path,
                                  expected_reconstruction_manifest_hash):
    """Verify exact inventory and bytes; no filesystem traversal or extraction occurs."""
    def fail(reason, details=None):
        return {"status": "INTEGRITY_FAILED", "reason": reason, "artifacts": details or []}
    if not isinstance(manifest, dict) or not isinstance(artifacts_by_path, dict):
        return {"status": "INVALID_INPUT", "reason": "OBJECTS_REQUIRED"}
    if manifest.get("manifest_version") != "1.0.0":
        return fail("UNSUPPORTED_MANIFEST_VERSION")
    if manifest.get("canonicalization_version") != _CANON:
        return fail("UNSUPPORTED_CANONICALIZATION")
    unsigned = {k: v for k, v in manifest.items() if k != "manifest_hash"}
    if manifest.get("manifest_hash") != _sha(_canonical(unsigned)):
        return fail("MANIFEST_HASH_MISMATCH")
    if manifest.get("reconstruction_manifest_hash") != expected_reconstruction_manifest_hash:
        return fail("RECONSTRUCTION_MANIFEST_BINDING_MISMATCH")
    entries = manifest.get("artifacts")
    if not isinstance(entries, list) or not entries:
        return fail("ARTIFACT_INVENTORY_REQUIRED")
    expected, folded, results = {}, set(), []
    for entry in entries:
        if not isinstance(entry, dict):
            return fail("INVALID_ARTIFACT_ENTRY")
        try:
            path = _validate_path(entry.get("path"))
        except ValueError:
            return fail("UNSAFE_ARTIFACT_PATH")
        if path in expected or path.casefold() in folded:
            return fail("DUPLICATE_ARTIFACT_PATH")
        folded.add(path.casefold())
        if entry.get("hash_algorithm") != "SHA-256" or not isinstance(entry.get("sha256"), str) or not _HASH.fullmatch(entry["sha256"]):
            return fail("INVALID_ARTIFACT_HASH")
        if not isinstance(entry.get("size_bytes"), int) or isinstance(entry.get("size_bytes"), bool) or entry["size_bytes"] < 0:
            return fail("INVALID_ARTIFACT_SIZE")
        expected[path] = entry
    if set(artifacts_by_path) != set(expected):
        return fail("ARTIFACT_INVENTORY_MISMATCH", [
            {"missing": sorted(set(expected) - set(artifacts_by_path)),
             "extra": sorted(set(artifacts_by_path) - set(expected))}])
    for path, entry in sorted(expected.items()):
        content = artifacts_by_path[path]
        if not isinstance(content, bytes):
            results.append({"path": path, "status": "INVALID_ARTIFACT_BYTES"})
        elif len(content) != entry["size_bytes"]:
            results.append({"path": path, "status": "SIZE_MISMATCH"})
        elif _sha(content) != entry["sha256"]:
            results.append({"path": path, "status": "HASH_MISMATCH"})
        else:
            results.append({"path": path, "status": "HASH_VERIFIED"})
    if any(item["status"] != "HASH_VERIFIED" for item in results):
        return fail("ARTIFACT_VERIFICATION_FAILED", results)
    return {"status": "AUDIT_PACKAGE_VERIFIED",
            "manifest_hash_status": "HASH_VERIFIED",
            "reconstruction_manifest_hash": expected_reconstruction_manifest_hash,
            "artifact_count": len(results), "artifacts": results}
