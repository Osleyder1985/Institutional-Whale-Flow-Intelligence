"""Verify and extract locally captured policy documents into a private evidence bundle.

This module performs technical integrity checks and text extraction only. It does
not determine legal applicability, grant retention rights, or authorize a source.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
from pathlib import Path
from typing import Any


MANIFEST_NAME = "policy-document-evidence-manifest-v1.0.json"
BUNDLE_NAME = "policy-document-extraction-bundle-v1.0.json"
SHA256_RE = re.compile(r"^[a-f0-9]{64}$")
HEADING_RE = re.compile(
    r"^\s*(?:(?:#{1,6}\s*)|(?:§\s*)|(?:Section\s+))"
    r"(?P<section>\d+(?:\.\d+)*(?:[A-Za-z])?)\s*[\.:–—-]?\s*(?P<title>.*)$",
    re.IGNORECASE,
)
LOCATOR_TERMS = (
    "license", "licence", "commercial", "non-commercial", "redistribution",
    "retain", "retention", "snapshot", "download", "caching", "derived",
    "third-party", "third party", "arbitration", "governing law",
    "intellectual property", "created ip", "termination", "assignment",
)


class EvidenceExtractionError(RuntimeError):
    """Raised when a local evidence bundle fails validation or extraction."""


def _ensure_outside_repository(path: Path) -> Path:
    resolved = path.expanduser().resolve()
    repository_root = Path(__file__).resolve().parents[1]
    if resolved == repository_root or repository_root in resolved.parents:
        raise EvidenceExtractionError("PRIVATE_EVIDENCE_PATH_INSIDE_REPOSITORY")
    return resolved


def _sha256_file(path: Path) -> tuple[str, int]:
    digest = hashlib.sha256()
    size = 0
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
            size += len(chunk)
    return digest.hexdigest(), size


def _safe_snapshot_path(evidence_dir: Path, filename: Any) -> Path:
    if (not isinstance(filename, str) or not filename or filename in {".", ".."}
            or "/" in filename or "\\" in filename or Path(filename).name != filename):
        raise EvidenceExtractionError("SNAPSHOT_FILENAME_INVALID")
    path = evidence_dir / filename
    if path.is_symlink() or not path.is_file():
        raise EvidenceExtractionError("SNAPSHOT_FILE_MISSING_OR_UNSAFE")
    return path


def _extract_text_document(path: Path) -> dict[str, Any]:
    try:
        text = path.read_text(encoding="utf-8-sig")
    except UnicodeDecodeError as exc:
        raise EvidenceExtractionError("TEXT_DOCUMENT_NOT_UTF8") from exc
    return {"format": "text", "text": text, "page_count": None, "pages": []}


def _extract_pdf_document(path: Path) -> dict[str, Any]:
    try:
        from pypdf import PdfReader
    except ImportError as exc:
        raise EvidenceExtractionError(
            "PDF_EXTRACTION_REQUIRES_PYPDF_INSTALLATION"
        ) from exc
    try:
        reader = PdfReader(str(path), strict=True)
        pages = []
        for index, page in enumerate(reader.pages, start=1):
            pages.append({"page": index, "text": page.extract_text() or ""})
    except Exception as exc:
        raise EvidenceExtractionError("PDF_EXTRACTION_FAILED") from exc
    return {
        "format": "pdf",
        "text": "\n".join(page["text"] for page in pages),
        "page_count": len(pages),
        "pages": pages,
    }


def _extract_document(path: Path) -> dict[str, Any]:
    suffix = path.suffix.lower()
    if suffix in {".txt", ".md"}:
        return _extract_text_document(path)
    if suffix == ".pdf":
        return _extract_pdf_document(path)
    raise EvidenceExtractionError("DOCUMENT_FORMAT_UNSUPPORTED")


def _find_structural_locators(text: str) -> list[dict[str, Any]]:
    locators = []
    for line_number, line in enumerate(text.splitlines(), start=1):
        match = HEADING_RE.match(line)
        if match:
            locators.append({
                "kind": "section_heading",
                "section": match.group("section"),
                "title": match.group("title").strip(),
                "line": line_number,
            })
        lowered = line.lower()
        matched_terms = [term for term in LOCATOR_TERMS if term in lowered]
        if matched_terms:
            locators.append({
                "kind": "topic_locator",
                "line": line_number,
                "matched_terms": matched_terms,
            })
    return locators


def build_extraction_bundle(evidence_dir: str | Path) -> dict[str, Any]:
    evidence_dir = _ensure_outside_repository(Path(evidence_dir))
    manifest_path = evidence_dir / MANIFEST_NAME
    if not manifest_path.is_file() or manifest_path.is_symlink():
        raise EvidenceExtractionError("EVIDENCE_MANIFEST_MISSING_OR_UNSAFE")
    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise EvidenceExtractionError("EVIDENCE_MANIFEST_INVALID") from exc

    if (not isinstance(manifest, dict)
            or manifest.get("manifest_version") != "1.0.0"
            or not isinstance(manifest.get("documents"), list)):
        raise EvidenceExtractionError("EVIDENCE_MANIFEST_INVALID")
    if manifest.get("storage_scope") != "LOCAL_ONLY":
        raise EvidenceExtractionError("EVIDENCE_STORAGE_SCOPE_NOT_LOCAL_ONLY")
    if manifest.get("external_upload_performed") is not False:
        raise EvidenceExtractionError("EXTERNAL_UPLOAD_FLAG_NOT_FALSE")
    if manifest.get("external_sync_performed") is not False:
        raise EvidenceExtractionError("EXTERNAL_SYNC_FLAG_NOT_FALSE")

    documents = []
    seen_ids = set()
    for record in manifest["documents"]:
        if not isinstance(record, dict):
            raise EvidenceExtractionError("DOCUMENT_RECORD_INVALID")
        document_id = record.get("document_id")
        if not isinstance(document_id, str) or not document_id or document_id in seen_ids:
            raise EvidenceExtractionError("DOCUMENT_ID_INVALID_OR_DUPLICATE")
        seen_ids.add(document_id)
        expected_hash = record.get("sha256")
        expected_size = record.get("bytes_written")
        if not isinstance(expected_hash, str) or not SHA256_RE.fullmatch(expected_hash):
            raise EvidenceExtractionError("MANIFEST_SHA256_INVALID")
        if not isinstance(expected_size, int) or isinstance(expected_size, bool) or expected_size < 0:
            raise EvidenceExtractionError("MANIFEST_BYTE_COUNT_INVALID")

        snapshot_path = _safe_snapshot_path(evidence_dir, record.get("local_filename"))
        actual_hash, actual_size = _sha256_file(snapshot_path)
        if actual_hash != expected_hash:
            raise EvidenceExtractionError(f"SNAPSHOT_SHA256_MISMATCH:{document_id}")
        if actual_size != expected_size:
            raise EvidenceExtractionError(f"SNAPSHOT_BYTE_COUNT_MISMATCH:{document_id}")

        extracted = _extract_document(snapshot_path)
        documents.append({
            "document_id": document_id,
            "provider": record.get("provider"),
            "requested_url": record.get("requested_url"),
            "final_url": record.get("final_url"),
            "retrieved_at_utc": record.get("retrieved_at_utc"),
            "sha256": actual_hash,
            "bytes": actual_size,
            "evidence_status": record.get("evidence_status"),
            "authorization_status": record.get("authorization_status"),
            "format": extracted["format"],
            "page_count": extracted["page_count"],
            "structural_locators": _find_structural_locators(extracted["text"]),
            "text": extracted["text"],
            "pages": extracted["pages"],
        })

    if not documents:
        raise EvidenceExtractionError("EVIDENCE_DOCUMENT_SET_EMPTY")
    return {
        "bundle_version": "1.0.0",
        "bundle_scope": "LOCAL_ONLY",
        "source_manifest": MANIFEST_NAME,
        "source_manifest_sha256": _sha256_file(manifest_path)[0],
        "authorization_status": manifest.get("authorization_status", "NOT_GRANTED"),
        "legal_review_status": manifest.get("legal_review_status", "NOT_PERFORMED"),
        "external_upload_performed": False,
        "external_sync_performed": False,
        "technical_integrity_verified": True,
        "legal_conclusion": "NOT_PROVIDED",
        "documents": documents,
    }


def write_bundle(bundle: dict[str, Any], output_path: str | Path) -> Path:
    output_path = _ensure_outside_repository(Path(output_path))
    output_path.parent.mkdir(parents=True, exist_ok=True)
    if output_path.exists() or output_path.is_symlink():
        raise EvidenceExtractionError("OUTPUT_BUNDLE_ALREADY_EXISTS")
    data = (json.dumps(bundle, ensure_ascii=False, indent=2) + "\n").encode("utf-8")
    temporary = output_path.with_name(f".{output_path.name}.tmp")
    try:
        with temporary.open("xb") as stream:
            stream.write(data)
            stream.flush()
            os.fsync(stream.fileno())
        os.link(temporary, output_path)
    except FileExistsError as exc:
        raise EvidenceExtractionError("OUTPUT_BUNDLE_ALREADY_EXISTS") from exc
    finally:
        try:
            temporary.unlink()
        except FileNotFoundError:
            pass
    return output_path


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Verify and extract local policy evidence; output remains local."
    )
    parser.add_argument("--evidence-dir", required=True)
    parser.add_argument("--output", help="Private JSON bundle path; defaults inside evidence-dir.")
    args = parser.parse_args(argv)
    evidence_dir = Path(args.evidence_dir).expanduser().resolve()
    output = Path(args.output) if args.output else evidence_dir / BUNDLE_NAME
    try:
        bundle = build_extraction_bundle(evidence_dir)
        path = write_bundle(bundle, output)
    except (EvidenceExtractionError, OSError) as exc:
        parser.exit(2, f"extraction rejected: {exc}\n")
    print(json.dumps({
        "bundle_path": str(path),
        "documents_processed": len(bundle["documents"]),
        "technical_integrity_verified": bundle["technical_integrity_verified"],
        "authorization_status": bundle["authorization_status"],
        "legal_review_status": bundle["legal_review_status"],
        "storage_scope": bundle["bundle_scope"],
    }, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
