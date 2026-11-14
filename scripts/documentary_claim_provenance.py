"""Validate documentary claims against an explicitly supplied immutable snapshot catalog.

No network, filesystem access, legal opinion, authorization, or automatic conflict resolution.
"""
from __future__ import annotations

import re
from datetime import datetime

_SHA256 = re.compile(r"^[a-f0-9]{64}$")
_UTC = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z$")
_TYPES = {"VERBATIM", "PARAPHRASE", "INFERENCE"}
_EPISTEMIC = {"VERIFIED", "PROVIDER_LABELLED", "INFERRED", "UNKNOWN", "DISPUTED"}
_LOCATORS = {"CLAUSE", "SECTION", "PAGE", "CHARACTER_RANGE"}
_TARGETS = {"ANALYSIS", "MOVEMENT_EPISODE", "HYPOTHESIS", "ATTRIBUTION_CLAIM", "ACTOR", "SOURCE_OBSERVATION"}
_RELATIONS = {"SUPPORTS", "CONTRADICTS", "CONTEXT_FOR", "DERIVED_FROM"}


class DocumentaryClaimError(ValueError):
    """Raised when a claim or snapshot catalog is malformed."""


def _valid_utc(value):
    if not isinstance(value, str) or not _UTC.fullmatch(value):
        return False
    try:
        datetime.strptime(value, "%Y-%m-%dT%H:%M:%SZ")
        return True
    except ValueError:
        return False


def _nonempty(value):
    return isinstance(value, str) and bool(value.strip())


def validate_snapshot_catalog(catalog):
    """Return an index of unique snapshot records; reject ambiguous identities."""
    if not isinstance(catalog, list) or not catalog:
        raise DocumentaryClaimError("SNAPSHOT_CATALOG_INVALID")
    index = {}
    for item in catalog:
        if not isinstance(item, dict):
            raise DocumentaryClaimError("SNAPSHOT_RECORD_INVALID")
        required = ("document_id", "snapshot_sha256", "source_url", "retrieved_at_utc", "document_version")
        if any(not _nonempty(item.get(key)) for key in required):
            raise DocumentaryClaimError("SNAPSHOT_RECORD_INCOMPLETE")
        if not _SHA256.fullmatch(item["snapshot_sha256"]):
            raise DocumentaryClaimError("SNAPSHOT_HASH_INVALID")
        if not item["source_url"].startswith("https://") or not _valid_utc(item["retrieved_at_utc"]):
            raise DocumentaryClaimError("SNAPSHOT_METADATA_INVALID")
        key = (item["document_id"], item["snapshot_sha256"])
        if key in index:
            raise DocumentaryClaimError("DUPLICATE_SNAPSHOT_IDENTITY")
        index[key] = dict(item)
    return index


def validate_claim(claim, snapshot_catalog):
    """Validate one claim against the supplied catalog; return deterministic diagnostics."""
    errors = []
    if not isinstance(claim, dict):
        return {"valid": False, "errors": ["CLAIM_NOT_OBJECT"]}
    if claim.get("contract_version") != "1.0.0":
        errors.append("UNSUPPORTED_CONTRACT_VERSION")
    if not _nonempty(claim.get("claim_id")) or not _nonempty(claim.get("claim_text")):
        errors.append("CLAIM_ID_OR_TEXT_MISSING")
    if claim.get("expression_type") not in _TYPES:
        errors.append("EXPRESSION_TYPE_INVALID")
    if claim.get("epistemic_status") not in _EPISTEMIC:
        errors.append("EPISTEMIC_STATUS_INVALID")
    if claim.get("authorization_status") != "NOT_GRANTED":
        errors.append("AUTHORIZATION_STATE_MUST_REMAIN_NOT_GRANTED")
    if claim.get("legal_review_status") != "NOT_PERFORMED":
        errors.append("LEGAL_REVIEW_STATE_MUST_REMAIN_NOT_PERFORMED")
    if claim.get("review_status") not in {"PENDING", "REVIEWED", "REJECTED", "SUPERSEDED"}:
        errors.append("REVIEW_STATUS_INVALID")
    if not _valid_utc(claim.get("recorded_at_utc")):
        errors.append("RECORDED_AT_INVALID")
    if claim.get("reviewed_at_utc") is not None and not _valid_utc(claim.get("reviewed_at_utc")):
        errors.append("REVIEWED_AT_INVALID")
    if claim.get("review_status") == "REVIEWED" and (not _nonempty(claim.get("reviewer")) or not _valid_utc(claim.get("reviewed_at_utc"))):
        errors.append("REVIEW_METADATA_REQUIRED")

    try:
        snapshots = validate_snapshot_catalog(snapshot_catalog)
    except DocumentaryClaimError as exc:
        return {"valid": False, "errors": errors + [str(exc)]}

    evidence = claim.get("evidence")
    if not isinstance(evidence, list) or not evidence:
        errors.append("EVIDENCE_REQUIRED")
        evidence = []
    seen_evidence = set()
    for item in evidence:
        if not isinstance(item, dict):
            errors.append("EVIDENCE_RECORD_INVALID")
            continue
        doc_id, digest = item.get("document_id"), item.get("snapshot_sha256")
        key = (doc_id, digest)
        if key in seen_evidence:
            errors.append("DUPLICATE_EVIDENCE_REFERENCE")
        seen_evidence.add(key)
        if not _nonempty(doc_id) or not isinstance(digest, str) or not _SHA256.fullmatch(digest):
            errors.append("SNAPSHOT_REFERENCE_INVALID")
            continue
        snapshot = snapshots.get(key)
        if snapshot is None:
            errors.append("SNAPSHOT_NOT_REGISTERED_OR_HASH_MISMATCH")
            continue
        for field in ("source_url", "retrieved_at_utc", "document_version"):
            if item.get(field) != snapshot.get(field):
                errors.append("SNAPSHOT_METADATA_MISMATCH")
                break
        locator = item.get("locator")
        if not isinstance(locator, dict) or locator.get("locator_type") not in _LOCATORS or not _nonempty(locator.get("value")):
            errors.append("LOCATOR_INVALID")
        elif locator["locator_type"] == "CHARACTER_RANGE":
            start, end = locator.get("start_offset"), locator.get("end_offset")
            if (not isinstance(start, int) or isinstance(start, bool) or not isinstance(end, int)
                    or isinstance(end, bool) or start < 0 or end <= start):
                errors.append("LOCATOR_RANGE_INVALID")
        elif "start_offset" in locator or "end_offset" in locator:
            errors.append("LOCATOR_OFFSETS_NOT_APPLICABLE")
        span_hash = item.get("extracted_span_sha256")
        if claim.get("expression_type") in {"VERBATIM", "PARAPHRASE"}:
            if not isinstance(span_hash, str) or not _SHA256.fullmatch(span_hash):
                errors.append("EXTRACTED_SPAN_HASH_REQUIRED")
        elif span_hash is not None:
            errors.append("INFERENCE_MUST_NOT_CLAIM_LITERAL_SPAN")

    targets = claim.get("targets")
    if not isinstance(targets, list) or not targets:
        errors.append("IWFI_TARGET_REQUIRED")
    else:
        for target in targets:
            if (not isinstance(target, dict) or target.get("target_type") not in _TARGETS
                    or not _nonempty(target.get("target_id")) or target.get("relation") not in _RELATIONS):
                errors.append("IWFI_TARGET_INVALID")

    if claim.get("expression_type") == "INFERENCE" and not evidence:
        errors.append("INFERENCE_WITHOUT_TRACEABLE_SUPPORT")
    if claim.get("expression_type") == "VERBATIM" and claim.get("epistemic_status") == "INFERRED":
        errors.append("VERBATIM_CANNOT_BE_LABELLED_INFERRED")
    return {"valid": not errors, "errors": sorted(set(errors))}


def validate_claim_collection(claims, snapshot_catalog):
    """Validate a set while preserving contradiction groups without adjudicating them."""
    if not isinstance(claims, list):
        return {"valid": False, "claims": [], "contradiction_groups": {}, "errors": ["CLAIM_COLLECTION_INVALID"]}
    ids = [item.get("claim_id") for item in claims if isinstance(item, dict)]
    duplicate_ids = sorted({item for item in ids if ids.count(item) > 1})
    results = []
    groups = {}
    for claim in claims:
        result = validate_claim(claim, snapshot_catalog)
        results.append({"claim_id": claim.get("claim_id") if isinstance(claim, dict) else None, **result})
        group = claim.get("contradiction_group_id") if isinstance(claim, dict) else None
        if _nonempty(group):
            groups.setdefault(group, []).append(claim.get("claim_id"))
    errors = ["DUPLICATE_CLAIM_ID"] if duplicate_ids else []
    if any(not item["valid"] for item in results):
        errors.append("CLAIM_VALIDATION_FAILED")
    return {
        "valid": not errors,
        "claims": results,
        "contradiction_groups": {key: sorted(value) for key, value in sorted(groups.items())},
        "errors": errors,
    }
