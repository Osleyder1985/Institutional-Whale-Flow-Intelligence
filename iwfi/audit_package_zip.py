"""Deterministic, offline ZIP export and verification for IWFI audit packages.

The ZIP contains a canonical inventory manifest and the exact inventoried
artifact bytes. ZIP_STORED avoids compressor-version differences across hosts.
No filesystem extraction, network access, or source capture is performed.
"""
from io import BytesIO
import json
import stat
import zipfile

from iwfi.audit_package_manifest import (
    verify_audit_package_manifest, _validate_path,
)

MANIFEST_PATH = "audit-package-manifest.json"
_ARCHIVE_COMPRESSION = zipfile.ZIP_STORED
_FIXED_TIMESTAMP = (1980, 1, 1, 0, 0, 0)


def _canonical(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"),
                      ensure_ascii=False, allow_nan=False).encode("utf-8")


def build_audit_package_zip(*, manifest, artifacts_by_path):
    """Return deterministic ZIP bytes for a previously built inventory manifest."""
    if not isinstance(manifest, dict) or not isinstance(artifacts_by_path, dict):
        raise ValueError("manifest and artifact mapping are required")
    if MANIFEST_PATH in artifacts_by_path:
        raise ValueError("artifact path is reserved for the package manifest")
    expected_hash = manifest.get("reconstruction_manifest_hash")
    checked = verify_audit_package_manifest(
        manifest=manifest, artifacts_by_path=artifacts_by_path,
        expected_reconstruction_manifest_hash=expected_hash)
    if checked.get("status") != "AUDIT_PACKAGE_VERIFIED":
        raise ValueError("audit package inventory must verify before export")
    output = BytesIO()
    with zipfile.ZipFile(output, "w", compression=_ARCHIVE_COMPRESSION,
                         allowZip64=True) as archive:
        entries = [(MANIFEST_PATH, _canonical(manifest))]
        entries.extend(sorted(artifacts_by_path.items()))
        for path, content in entries:
            if path != MANIFEST_PATH:
                _validate_path(path)
            info = zipfile.ZipInfo(path, date_time=_FIXED_TIMESTAMP)
            info.compress_type = _ARCHIVE_COMPRESSION
            info.create_system = 3
            info.external_attr = (stat.S_IFREG | 0o644) << 16
            info.flag_bits |= 0x800
            info.extra = b""
            info.comment = b""
            archive.writestr(info, content)
    return output.getvalue()


def verify_audit_package_zip(*, archive_bytes,
                             expected_reconstruction_manifest_hash):
    """Verify ZIP structure, exact inventory and bytes without extracting files."""
    def fail(reason, **extra):
        return {"status": "INTEGRITY_FAILED", "reason": reason, **extra}
    if not isinstance(archive_bytes, bytes):
        return {"status": "INVALID_INPUT", "reason": "ARCHIVE_BYTES_REQUIRED"}
    try:
        with zipfile.ZipFile(BytesIO(archive_bytes), "r") as archive:
            if archive.comment:
                return fail("ARCHIVE_COMMENT_NOT_ALLOWED")
            infos = archive.infolist()
            names = [item.filename for item in infos]
            if len(names) != len(set(names)):
                return fail("DUPLICATE_ARCHIVE_ENTRY")
            if MANIFEST_PATH not in names:
                return fail("PACKAGE_MANIFEST_MISSING")
            payloads = {}
            manifest_bytes = None
            for info in infos:
                name = info.filename
                if info.is_dir() or info.flag_bits & 0x1:
                    return fail("DIRECTORY_OR_ENCRYPTED_ENTRY_NOT_ALLOWED",
                                path=name)
                if name != MANIFEST_PATH:
                    try:
                        _validate_path(name)
                    except ValueError:
                        return fail("UNSAFE_ARCHIVE_PATH", path=name)
                if info.compress_type != _ARCHIVE_COMPRESSION:
                    return fail("UNSUPPORTED_COMPRESSION", path=name)
                if info.date_time != _FIXED_TIMESTAMP:
                    return fail("NONDETERMINISTIC_TIMESTAMP", path=name)
                mode = (info.external_attr >> 16) & 0xFFFF
                if stat.S_ISLNK(mode) or (mode and not stat.S_ISREG(mode)):
                    return fail("NON_REGULAR_FILE_ENTRY", path=name)
                content = archive.read(info)
                if len(content) != info.file_size:
                    return fail("ARCHIVE_SIZE_MISMATCH", path=name)
                if name == MANIFEST_PATH:
                    manifest_bytes = content
                else:
                    payloads[name] = content
            try:
                manifest = json.loads(manifest_bytes.decode("utf-8"))
            except (UnicodeDecodeError, json.JSONDecodeError, TypeError):
                return fail("PACKAGE_MANIFEST_INVALID_JSON")
            if _canonical(manifest) != manifest_bytes:
                return fail("PACKAGE_MANIFEST_NOT_CANONICAL")
            verified = verify_audit_package_manifest(
                manifest=manifest, artifacts_by_path=payloads,
                expected_reconstruction_manifest_hash=expected_reconstruction_manifest_hash)
            if verified.get("status") != "AUDIT_PACKAGE_VERIFIED":
                return fail("INVENTORY_VERIFICATION_FAILED",
                            inventory_result=verified)
            return {"status": "AUDIT_PACKAGE_VERIFIED",
                    "package_id": manifest.get("package_id"),
                    "manifest_hash": manifest.get("manifest_hash"),
                    "artifact_count": verified.get("artifact_count"),
                    "archive_entry_count": len(infos)}
    except (zipfile.BadZipFile, EOFError, RuntimeError, OSError, ValueError):
        return fail("ARCHIVE_INVALID_OR_TRUNCATED")
