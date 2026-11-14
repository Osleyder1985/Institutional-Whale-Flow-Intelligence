"""Validate policy findings against exact extracted document snapshots and text locators.

This validator verifies references only. It does not assess legal correctness,
applicability, licensing, retention rights, or source authorization.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import tempfile
from datetime import datetime
from pathlib import Path
from typing import Any

from scripts.extract_policy_evidence import EvidenceExtractionError, build_extraction_bundle


ROOT = Path(__file__).resolve().parents[1]
SHA256_RE = re.compile(r"^[a-f0-9]{64}$")
FINDING_ID_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:-]{0,127}$")
ALLOWED_CONCLUSION_TYPES = {"OBSERVED_TEXT", "INTERPRETATION"}
ALLOWED_APPLICABILITY = {
    "NOT_ASSESSED", "ASSESSED_APPLICABLE", "ASSESSED_NOT_APPLICABLE", "UNCERTAIN"
}
ALLOWED_REVIEW_STATES = {"DRAFT", "REVIEWED", "REVIEW_REQUIRED"}


class FindingValidationError(RuntimeError):
    pass


def _load_json(path: Path, error_code: str) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise FindingValidationError(error_code) from exc
    if not isinstance(value, dict):
        raise FindingValidationError(error_code)
    return value


def _valid_utc_timestamp(value: Any) -> bool:
    if not isinstance(value, str) or not value.endswith("Z"):
        return False
    try:
        parsed = datetime.fromisoformat(value[:-1] + "+00:00")
    except ValueError:
        return False
    return parsed.utcoffset() is not None


def load_extraction_bundle(path: str | Path) -> dict[str, dict[str, Any]]:
    bundle = _load_json(Path(path), "EXTRACTION_BUNDLE_INVALID")
    if bundle.get("bundle_version") != "1.0.0":
        raise FindingValidationError("EXTRACTION_BUNDLE_VERSION_UNSUPPORTED")
    if bundle.get("bundle_scope") != "LOCAL_ONLY":
        raise FindingValidationError("EXTRACTION_BUNDLE_SCOPE_INVALID")
    if bundle.get("technical_integrity_verified") is not True:
        raise FindingValidationError("EXTRACTION_BUNDLE_INTEGRITY_NOT_VERIFIED")
    if bundle.get("legal_conclusion") != "NOT_PROVIDED":
        raise FindingValidationError("EXTRACTION_BUNDLE_LEGAL_SCOPE_INVALID")
    documents = bundle.get("documents")
    if not isinstance(documents, list) or not documents:
        raise FindingValidationError("EXTRACTION_BUNDLE_DOCUMENTS_INVALID")
    indexed = {}
    for document in documents:
        if not isinstance(document, dict):
            raise FindingValidationError("EXTRACTION_DOCUMENT_INVALID")
        document_id = document.get("document_id")
        digest = document.get("sha256")
        if (not isinstance(document_id, str) or not document_id or document_id in indexed
                or not isinstance(digest, str) or not SHA256_RE.fullmatch(digest)
                or not isinstance(document.get("text"), str)):
            raise FindingValidationError("EXTRACTION_DOCUMENT_ID_OR_HASH_INVALID")
        pages = document.get("pages")
        if not isinstance(pages, list):
            raise FindingValidationError("EXTRACTION_DOCUMENT_PAGES_INVALID")
        indexed[document_id] = document
    return indexed


def _validate_finding(finding: Any, documents: dict[str, dict[str, Any]]) -> dict[str, Any]:
    if not isinstance(finding, dict):
        raise FindingValidationError("FINDING_RECORD_INVALID")
    finding_id = finding.get("finding_id")
    if not isinstance(finding_id, str) or not FINDING_ID_RE.fullmatch(finding_id):
        raise FindingValidationError("FINDING_ID_INVALID")
    proposition = finding.get("proposition")
    if not isinstance(proposition, str) or not proposition.strip():
        raise FindingValidationError(f"FINDING_PROPOSITION_MISSING:{finding_id}")
    conclusion_type = finding.get("conclusion_type")
    if conclusion_type not in ALLOWED_CONCLUSION_TYPES:
        raise FindingValidationError(f"CONCLUSION_TYPE_INVALID:{finding_id}")
    applicability = finding.get("applicability_status")
    if applicability not in ALLOWED_APPLICABILITY:
        raise FindingValidationError(f"APPLICABILITY_STATUS_INVALID:{finding_id}")
    review_state = finding.get("review_state")
    if review_state not in ALLOWED_REVIEW_STATES:
        raise FindingValidationError(f"REVIEW_STATE_INVALID:{finding_id}")

    source = finding.get("source")
    if not isinstance(source, dict):
        raise FindingValidationError(f"SOURCE_REFERENCE_MISSING:{finding_id}")
    document_id = source.get("document_id")
    document = documents.get(document_id) if isinstance(document_id, str) else None
    if document is None:
        raise FindingValidationError(f"SOURCE_DOCUMENT_NOT_IN_BUNDLE:{finding_id}")
    snapshot_hash = source.get("snapshot_sha256")
    if not isinstance(snapshot_hash, str) or not SHA256_RE.fullmatch(snapshot_hash):
        raise FindingValidationError(f"SNAPSHOT_HASH_INVALID:{finding_id}")
    if snapshot_hash != document["sha256"]:
        raise FindingValidationError(f"SNAPSHOT_HASH_MISMATCH:{finding_id}")
    declared_version = source.get("declared_version")
    if declared_version is not None and not isinstance(declared_version, str):
        raise FindingValidationError(f"DECLARED_VERSION_INVALID:{finding_id}")

    locator = finding.get("locator")
    if not isinstance(locator, dict):
        raise FindingValidationError(f"TEXT_LOCATOR_MISSING:{finding_id}")
    exact_text = locator.get("exact_text")
    if not isinstance(exact_text, str) or not exact_text.strip():
        raise FindingValidationError(f"TEXT_LOCATOR_EMPTY:{finding_id}")
    locator_kind = locator.get("kind")
    if locator_kind == "document_text":
        if exact_text not in document["text"]:
            raise FindingValidationError(f"TEXT_LOCATOR_NOT_FOUND:{finding_id}")
        page_number = None
    elif locator_kind == "pdf_page":
        page_number = locator.get("page")
        if not isinstance(page_number, int) or isinstance(page_number, bool) or page_number < 1:
            raise FindingValidationError(f"PDF_PAGE_INVALID:{finding_id}")
        page = next((item for item in document["pages"]
                     if isinstance(item, dict) and item.get("page") == page_number), None)
        if page is None or not isinstance(page.get("text"), str) or exact_text not in page["text"]:
            raise FindingValidationError(f"TEXT_LOCATOR_NOT_FOUND_ON_PAGE:{finding_id}")
    else:
        raise FindingValidationError(f"TEXT_LOCATOR_KIND_INVALID:{finding_id}")

    return {
        "finding_id": finding_id,
        "reference_status": "REFERENCE_VERIFIED",
        "document_id": document_id,
        "snapshot_sha256": snapshot_hash,
        "locator_kind": locator_kind,
        "page": page_number,
        "conclusion_type": conclusion_type,
        "applicability_status": applicability,
        "review_state": review_state,
    }


def validate_policy_findings(
    bundle_path: str | Path, review_path: str | Path, evidence_dir: str | Path
) -> dict[str, Any]:
    documents = load_extraction_bundle(bundle_path)
    try:
        rebuilt_bundle = build_extraction_bundle(evidence_dir)
    except (EvidenceExtractionError, OSError) as exc:
        raise FindingValidationError("ORIGINAL_SNAPSHOT_RECONSTRUCTION_FAILED") from exc
    supplied_bundle = _load_json(Path(bundle_path), "EXTRACTION_BUNDLE_INVALID")
    if (
        supplied_bundle.get("source_manifest_sha256") != rebuilt_bundle.get("source_manifest_sha256")
        or supplied_bundle.get("documents") != rebuilt_bundle.get("documents")
        or supplied_bundle.get("authorization_status") != rebuilt_bundle.get("authorization_status")
        or supplied_bundle.get("legal_review_status") != rebuilt_bundle.get("legal_review_status")
    ):
        raise FindingValidationError("EXTRACTION_BUNDLE_DOES_NOT_MATCH_ORIGINAL_SNAPSHOTS")
    review = _load_json(Path(review_path), "POLICY_REVIEW_REGISTER_INVALID")
    if review.get("review_register_version") != "1.0.0":
        raise FindingValidationError("POLICY_REVIEW_VERSION_UNSUPPORTED")
    if review.get("register_scope") != "METADATA_AND_REFERENCES_ONLY":
        raise FindingValidationError("POLICY_REVIEW_REGISTER_SCOPE_INVALID")
    reviewer = review.get("reviewer")
    reviewed_at = review.get("reviewed_at_utc")
    if not isinstance(reviewer, str) or not reviewer.strip():
        raise FindingValidationError("REVIEWER_MISSING")
    if not _valid_utc_timestamp(reviewed_at):
        raise FindingValidationError("REVIEW_TIMESTAMP_INVALID")
    findings = review.get("findings")
    if not isinstance(findings, list) or not findings:
        raise FindingValidationError("FINDINGS_EMPTY_OR_INVALID")
    ids = [item.get("finding_id") for item in findings if isinstance(item, dict)]
    if len(ids) != len(findings) or len(ids) != len(set(ids)):
        raise FindingValidationError("FINDING_ID_DUPLICATE_OR_INVALID")
    results = [_validate_finding(item, documents) for item in findings]
    return {
        "validation_version": "1.0.0",
        "validation_status": "ALL_REFERENCES_VERIFIED",
        "reference_verification_only": True,
        "legal_conclusion": "NOT_PROVIDED",
        "authorization_status": "NOT_CHANGED",
        "retention_status": "NOT_CHANGED",
        "redistribution_status": "NOT_CHANGED",
        "review_register_sha256": hashlib.sha256(
            Path(review_path).read_bytes()
        ).hexdigest(),
        "extraction_bundle_sha256": hashlib.sha256(
            Path(bundle_path).read_bytes()
        ).hexdigest(),
        "findings_checked": len(results),
        "findings": results,
    }


def write_validation_report(report: dict[str, Any], output_path: str | Path) -> Path:
    output = Path(output_path).expanduser().resolve()
    if output == ROOT or ROOT in output.parents:
        raise FindingValidationError("VALIDATION_OUTPUT_INSIDE_REPOSITORY")
    output.parent.mkdir(parents=True, exist_ok=True)
    if output.exists() or output.is_symlink():
        raise FindingValidationError("VALIDATION_OUTPUT_ALREADY_EXISTS")
    data = (json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n").encode("utf-8")
    fd, temporary = tempfile.mkstemp(prefix=".iwfi-validation-", suffix=".tmp", dir=str(output.parent))
    try:
        with os.fdopen(fd, "wb") as stream:
            stream.write(data)
            stream.flush()
            os.fsync(stream.fileno())
        os.link(temporary, output)
    except FileExistsError as exc:
        raise FindingValidationError("VALIDATION_OUTPUT_ALREADY_EXISTS") from exc
    finally:
        try:
            os.unlink(temporary)
        except FileNotFoundError:
            pass
    return output


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Verify policy finding references against a private extraction bundle."
    )
    parser.add_argument("--bundle", required=True)
    parser.add_argument("--review-register", required=True)
    parser.add_argument("--evidence-dir", required=True, help="Directory containing original snapshots and capture manifest.")
    parser.add_argument("--output", required=True)
    args = parser.parse_args(argv)
    try:
        report = validate_policy_findings(args.bundle, args.review_register, args.evidence_dir)
        path = write_validation_report(report, args.output)
    except (FindingValidationError, OSError) as exc:
        parser.exit(2, f"validation rejected: {exc}\n")
    print(json.dumps({
        "validation_status": report["validation_status"],
        "findings_checked": report["findings_checked"],
        "report_path": str(path),
        "reference_verification_only": True,
    }, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
