"""Detached Ed25519 signatures for exact IWFI audit ZIP bytes.

The signature sidecar is stored separately from the ZIP to avoid a circular
archive-hash dependency. Verification requires an independently trusted public
key; a key embedded in the sidecar is never trusted.
"""
import hashlib
import json

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import (
    Ed25519PrivateKey, Ed25519PublicKey,
)

from iwfi.audit_package_zip import verify_audit_package_zip

_CANON = "IWFI-JSON-C14N-1"
_ALGORITHM = "Ed25519"


def _canonical(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"),
                      ensure_ascii=False, allow_nan=False).encode("utf-8")


def _sha(payload):
    return hashlib.sha256(payload).hexdigest()


def _public_fingerprint(public_key):
    der = public_key.public_bytes(
        encoding=serialization.Encoding.DER,
        format=serialization.PublicFormat.SubjectPublicKeyInfo)
    return _sha(der)


def _load_private(pem):
    key = serialization.load_pem_private_key(pem, password=None)
    if not isinstance(key, Ed25519PrivateKey):
        raise ValueError("Ed25519 private key required")
    return key


def _load_public(pem):
    key = serialization.load_pem_public_key(pem)
    if not isinstance(key, Ed25519PublicKey):
        raise ValueError("Ed25519 public key required")
    return key


def sign_audit_package_archive(*, archive_bytes, package_manifest_hash,
                               private_key_pem):
    """Sign exact ZIP bytes and their declared inventory-manifest hash."""
    if not isinstance(archive_bytes, bytes) or not archive_bytes:
        raise ValueError("non-empty archive bytes are required")
    if (not isinstance(package_manifest_hash, str)
            or len(package_manifest_hash) != 64
            or any(char not in "0123456789abcdef" for char in package_manifest_hash)):
        raise ValueError("package_manifest_hash must be lowercase SHA-256 hex")
    private = _load_private(private_key_pem)
    body = {
        "signature_version": "1.0.0",
        "signature_algorithm": _ALGORITHM,
        "archive_hash_algorithm": "SHA-256",
        "archive_sha256": _sha(archive_bytes),
        "package_manifest_hash": package_manifest_hash,
        "canonicalization_version": _CANON,
        "key_fingerprint_sha256": _public_fingerprint(private.public_key()),
    }
    return {**body, "signature_hex": private.sign(_canonical(body)).hex()}


def verify_signed_audit_package_archive(*, archive_bytes, signature,
                                        trusted_public_key_pem,
                                        expected_reconstruction_manifest_hash):
    """Verify trusted Ed25519 signature, exact ZIP bytes and package inventory."""
    def fail(reason):
        return {"status": "SIGNATURE_INVALID", "reason": reason}
    if not isinstance(archive_bytes, bytes) or not isinstance(signature, dict):
        return {"status": "INVALID_INPUT", "reason": "ARCHIVE_AND_SIGNATURE_REQUIRED"}
    try:
        if signature.get("signature_version") != "1.0.0":
            return fail("UNSUPPORTED_SIGNATURE_VERSION")
        if signature.get("signature_algorithm") != _ALGORITHM:
            return fail("UNSUPPORTED_SIGNATURE_ALGORITHM")
        if signature.get("archive_hash_algorithm") != "SHA-256":
            return fail("UNSUPPORTED_ARCHIVE_HASH")
        if signature.get("canonicalization_version") != _CANON:
            return fail("UNSUPPORTED_CANONICALIZATION")
        public = _load_public(trusted_public_key_pem)
        if signature.get("key_fingerprint_sha256") != _public_fingerprint(public):
            return fail("TRUSTED_KEY_FINGERPRINT_MISMATCH")
        if signature.get("archive_sha256") != _sha(archive_bytes):
            return fail("ARCHIVE_HASH_MISMATCH")
        signed_body = {key: value for key, value in signature.items()
                       if key != "signature_hex"}
        signature_hex = signature.get("signature_hex")
        if not isinstance(signature_hex, str) or len(signature_hex) != 128:
            return fail("SIGNATURE_MISSING_OR_MALFORMED")
        public.verify(bytes.fromhex(signature_hex), _canonical(signed_body))
    except (InvalidSignature, ValueError, TypeError, KeyError):
        return fail("SIGNATURE_OR_FORMAT_INVALID")
    package = verify_audit_package_zip(
        archive_bytes=archive_bytes,
        expected_reconstruction_manifest_hash=expected_reconstruction_manifest_hash)
    if package.get("status") != "AUDIT_PACKAGE_VERIFIED":
        return {"status": "PACKAGE_INVALID", "package_result": package}
    if package.get("manifest_hash") != signature.get("package_manifest_hash"):
        return {"status": "PACKAGE_INVALID", "reason": "PACKAGE_MANIFEST_HASH_MISMATCH"}
    return {"status": "SIGNED_AUDIT_PACKAGE_VERIFIED",
            "archive_sha256": signature["archive_sha256"],
            "package_manifest_hash": signature["package_manifest_hash"],
            "key_fingerprint_sha256": signature["key_fingerprint_sha256"],
            "package_result": package}
