"""Acquire and seal official policy documents locally; never upload or approve them.

Usage:
    python scripts/acquire_policy_documents.py --output-dir <private-local-directory>

Only the three reviewed HTTPS source URLs below are accepted. Downloads are streamed
without an arbitrary size cap. Each file is written atomically and never overwritten.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import tempfile
from datetime import datetime, timezone
from urllib.error import HTTPError, URLError
from urllib.parse import urlparse
from urllib.request import HTTPRedirectHandler, Request, build_opener


DOCUMENTS = {
    "binance_vision_dataset_terms_v1": {
        "url": "https://raw.githubusercontent.com/binance/binance-public-data/master/TERMS_AND_CONDITIONS.md",
        "filename": "binance_vision_dataset_terms_v1.md",
        "provider": "Binance",
        "version_observed": "1.0 (document states Last Updated: 2026-08-26)",
        "source_url_mutable": True,
    },
    "cc_by_nc_sa_4_0_legal_code": {
        "url": "https://creativecommons.org/licenses/by-nc-sa/4.0/legalcode.txt",
        "filename": "cc_by_nc_sa_4_0_legalcode.txt",
        "provider": "Creative Commons",
        "version_observed": "4.0",
        "source_url_mutable": True,
    },
    "binance_terms_of_use_adgm_2026_01_05": {
        "url": "https://bin.bnbstatic.com/static/cms/cg08ou2ak0tn7mcplvfg/file/9958035d95bff024a86a662fb4fdba45527d55a936e2cb9ed1d7ddf205ca082d.pdf",
        "filename": "binance_terms_of_use_adgm_2026_01_05.pdf",
        "provider": "Binance / ADGM entities identified in document",
        "version_observed": "Effective Date: 2026-01-05; applicability to this user still requires review",
        "source_url_mutable": True,
    },
}
ALLOWED_HOSTS = {"raw.githubusercontent.com", "creativecommons.org", "bin.bnbstatic.com"}
CHUNK_SIZE = 1024 * 1024
MANIFEST_NAME = "policy-document-evidence-manifest-v1.0.json"


class AcquisitionError(RuntimeError):
    pass


class SafeRedirectHandler(HTTPRedirectHandler):
    """Reject redirect targets outside the fixed HTTPS host allowlist."""

    def redirect_request(self, req, fp, code, msg, headers, newurl):
        parsed = urlparse(newurl)
        if parsed.scheme != "https" or parsed.hostname not in ALLOWED_HOSTS:
            raise AcquisitionError("UNSAFE_REDIRECT_TARGET")
        if parsed.username or parsed.password:
            raise AcquisitionError("REDIRECT_CREDENTIALS_FORBIDDEN")
        return super().redirect_request(req, fp, code, msg, headers, newurl)


def _utc_now():
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _validate_document_id(document_id):
    if document_id not in DOCUMENTS:
        raise AcquisitionError("DOCUMENT_ID_NOT_ALLOWLISTED")
    return DOCUMENTS[document_id]


def _validate_url(url):
    parsed = urlparse(url)
    if (parsed.scheme != "https" or parsed.hostname not in ALLOWED_HOSTS
            or parsed.username or parsed.password or parsed.fragment):
        raise AcquisitionError("URL_NOT_ALLOWLISTED")
    if url not in {item["url"] for item in DOCUMENTS.values()}:
        raise AcquisitionError("URL_NOT_ALLOWLISTED")


def _write_json_exclusive(path, payload):
    path = Path(path)
    if path.exists():
        raise AcquisitionError("OUTPUT_MANIFEST_ALREADY_EXISTS")
    data = (json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n").encode("utf-8")
    fd, temporary = tempfile.mkstemp(prefix=".manifest-", suffix=".tmp", dir=str(path.parent))
    try:
        with os.fdopen(fd, "wb") as stream:
            stream.write(data)
            stream.flush()
            os.fsync(stream.fileno())
        os.link(temporary, path)
    except FileExistsError as exc:
        raise AcquisitionError("OUTPUT_MANIFEST_ALREADY_EXISTS") from exc
    finally:
        try:
            os.unlink(temporary)
        except FileNotFoundError:
            pass


def _download_one(document_id, output_dir, opener=None):
    spec = _validate_document_id(document_id)
    _validate_url(spec["url"])
    destination = output_dir / spec["filename"]
    if destination.exists():
        raise AcquisitionError("SNAPSHOT_ALREADY_EXISTS")
    opener = opener or build_opener(SafeRedirectHandler())
    request = Request(spec["url"], headers={"User-Agent": "IWFI-local-policy-evidence-acquirer/1.0"})
    temporary_path = None
    digest = hashlib.sha256()
    byte_count = 0
    try:
        with opener.open(request, timeout=60) as response:
            status = getattr(response, "status", None) or response.getcode()
            if status != 200:
                raise AcquisitionError("HTTP_STATUS_NOT_SUCCESS")
            final_url = response.geturl()
            _validate_url(final_url)
            headers = response.headers
            fd, temporary_path = tempfile.mkstemp(prefix=".capture-", suffix=".part", dir=str(output_dir))
            with os.fdopen(fd, "wb") as output:
                while True:
                    block = response.read(CHUNK_SIZE)
                    if not block:
                        break
                    output.write(block)
                    digest.update(block)
                    byte_count += len(block)
                output.flush()
                os.fsync(output.fileno())
            content_length = headers.get("Content-Length")
            if content_length is not None and int(content_length) != byte_count:
                raise AcquisitionError("CONTENT_LENGTH_MISMATCH")
            sha256 = digest.hexdigest()
            os.link(temporary_path, destination)
            return {
                "document_id": document_id,
                "provider": spec["provider"],
                "requested_url": spec["url"],
                "final_url": final_url,
                "source_url_mutable": spec["source_url_mutable"],
                "version_observed": spec["version_observed"],
                "http_status": status,
                "content_type": headers.get("Content-Type"),
                "content_length_header": content_length,
                "bytes_written": byte_count,
                "sha256": sha256,
                "etag": headers.get("ETag"),
                "last_modified": headers.get("Last-Modified"),
                "retrieved_at_utc": _utc_now(),
                "local_filename": destination.name,
                "evidence_status": "CAPTURED_UNREVIEWED",
                "authorization_status": "NOT_GRANTED",
            }
    except HTTPError as exc:
        raise AcquisitionError("HTTP_STATUS_NOT_SUCCESS") from exc
    except URLError as exc:
        raise AcquisitionError("NETWORK_RETRIEVAL_FAILED") from exc
    except FileExistsError as exc:
        raise AcquisitionError("SNAPSHOT_ALREADY_EXISTS") from exc
    finally:
        if temporary_path:
            try:
                os.unlink(temporary_path)
            except FileNotFoundError:
                pass


def acquire(document_ids, output_dir):
    if not document_ids:
        raise AcquisitionError("DOCUMENT_SELECTION_EMPTY")
    if len(document_ids) != len(set(document_ids)):
        raise AcquisitionError("DUPLICATE_DOCUMENT_ID")
    for document_id in document_ids:
        _validate_document_id(document_id)

    output_dir = Path(output_dir).expanduser().resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    manifest_path = output_dir / MANIFEST_NAME
    if manifest_path.exists():
        raise AcquisitionError("OUTPUT_MANIFEST_ALREADY_EXISTS")
    for document_id in document_ids:
        if (output_dir / DOCUMENTS[document_id]["filename"]).exists():
            raise AcquisitionError("SNAPSHOT_ALREADY_EXISTS")

    captured = []
    for document_id in document_ids:
        captured.append(_download_one(document_id, output_dir))
    manifest = {
        "manifest_version": "1.0.0",
        "created_at_utc": _utc_now(),
        "storage_scope": "LOCAL_ONLY",
        "network_methods": ["HTTPS_GET"],
        "external_upload_performed": False,
        "external_sync_performed": False,
        "legal_review_status": "NOT_PERFORMED",
        "authorization_status": "NOT_GRANTED",
        "documents": captured,
    }
    _write_json_exclusive(manifest_path, manifest)
    return manifest_path, manifest


def main(argv=None):
    parser = argparse.ArgumentParser(description="Capture official policy documents to a local evidence folder.")
    parser.add_argument("--output-dir", required=True, help="Private local directory; not a repository or sync folder.")
    parser.add_argument("--document-id", action="append", dest="document_ids",
                        choices=sorted(DOCUMENTS), help="Document ID; repeat to select multiple. Default: all.")
    args = parser.parse_args(argv)
    try:
        manifest_path, manifest = acquire(args.document_ids or list(DOCUMENTS), args.output_dir)
    except (AcquisitionError, OSError, ValueError) as exc:
        parser.exit(2, f"acquisition rejected: {exc}\n")
    print(json.dumps({
        "manifest_path": str(manifest_path),
        "documents_captured": len(manifest["documents"]),
        "authorization_status": manifest["authorization_status"],
        "legal_review_status": manifest["legal_review_status"],
    }, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
