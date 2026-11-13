"""Point-in-time validation for IWFI FeatureSnapshot and DatasetSnapshot v1."""
from datetime import datetime
from pathlib import Path
import json
import re

from jsonschema import Draft202012Validator, FormatChecker


ROOT = Path(__file__).resolve().parent.parent
FEATURE_SCHEMA_PATH = ROOT / "schemas" / "predictive" / "v1" / "feature-snapshot.schema.json"
DATASET_SCHEMA_PATH = ROOT / "schemas" / "predictive" / "v1" / "dataset-snapshot.schema.json"
UTC_PATTERN = re.compile(r"^[0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{2}:[0-9]{2}:[0-9]{2}Z$")


def _utc(value):
    if not isinstance(value, str) or UTC_PATTERN.fullmatch(value) is None:
        return None
    try:
        return datetime.fromisoformat(value[:-1] + "+00:00")
    except ValueError:
        return None


def _schema_errors(record, schema_path):
    schema = json.loads(Path(schema_path).read_text(encoding="utf-8"))
    validator = Draft202012Validator(schema, format_checker=FormatChecker())
    return [f"schema: {error.message}" for error in validator.iter_errors(record)]


def validate_feature_snapshot(snapshot):
    """Validate schema and point-in-time eligibility for a FeatureSnapshot."""
    if not isinstance(snapshot, dict):
        return ["feature snapshot must be an object"]
    errors = _schema_errors(snapshot, FEATURE_SCHEMA_PATH)
    if errors:
        return errors

    origin = _utc(snapshot["origin_time"])
    cutoff = _utc(snapshot["data_cutoff_time"])
    created = _utc(snapshot["created_at"])
    if any(value is None for value in (origin, cutoff, created)):
        return ["origin_time, data_cutoff_time and created_at must be UTC timestamps ending in Z"]
    if cutoff > origin:
        errors.append("data_cutoff_time cannot be later than origin_time")
    if created < cutoff:
        errors.append("created_at cannot precede data_cutoff_time")

    sources = {}
    for index, source in enumerate(snapshot["source_observations"]):
        ref = source["source_ref"]
        if ref in sources:
            errors.append(f"source_observations[{index}] duplicates source_ref")
        sources[ref] = source
        known = _utc(source["known_at"])
        ingested = _utc(source["ingested_at"])
        available = _utc(source["available_at"])
        if any(value is None for value in (known, ingested, available)):
            errors.append(f"source_observations[{index}] timestamps must be UTC values ending in Z")
            continue
        if available < known or available < ingested:
            errors.append(f"source_observations[{index}] available_at cannot precede known_at or ingested_at")
        if available > cutoff:
            errors.append(f"source_observations[{index}] was not available by data_cutoff_time")

    for index, feature in enumerate(snapshot["features"]):
        start = _utc(feature["window_start"])
        end = _utc(feature["window_end"])
        computed = _utc(feature["computed_at"])
        if start is None or end is None or computed is None or start > end:
            errors.append(f"features[{index}] has invalid UTC window/computed_at")
        refs = feature["source_refs"]
        if len(refs) != len(set(refs)):
            errors.append(f"features[{index}] source_refs must be unique")
        missing_refs = [ref for ref in refs if ref not in sources]
        if missing_refs:
            errors.append(f"features[{index}] references unknown source observations")
        known_times = [
            _utc(sources[ref]["available_at"])
            for ref in refs
            if ref in sources and _utc(sources[ref]["available_at"]) is not None
        ]
        if computed is not None and known_times and computed < max(known_times):
            errors.append(f"features[{index}] computed_at precedes an input's available_at")
        if computed is not None and computed > created:
            errors.append(f"features[{index}] computed_at cannot follow snapshot created_at")

        if feature["status"] == "AVAILABLE":
            if feature["value"] is None:
                errors.append(f"features[{index}] AVAILABLE status requires a value")
            if not refs:
                errors.append(f"features[{index}] AVAILABLE status requires source_refs")
            if feature["missing_reason"] is not None:
                errors.append(f"features[{index}] AVAILABLE status must not have missing_reason")
        else:
            if feature["value"] is not None:
                errors.append(f"features[{index}] non-AVAILABLE value must be null")
            if not feature["missing_reason"]:
                errors.append(f"features[{index}] non-AVAILABLE status requires missing_reason")

    if snapshot["status"] == "READY":
        if snapshot["quality"]["status"] != "PASS":
            errors.append("READY snapshot requires PASS quality")
        if any(feature["status"] != "AVAILABLE" for feature in snapshot["features"]):
            errors.append("READY snapshot may contain only AVAILABLE features")
    if snapshot["quality"]["status"] == "FAIL" and snapshot["status"] != "ABSTAINED":
        errors.append("FAIL quality requires ABSTAINED snapshot status")
    return errors


def validate_dataset_snapshot(dataset):
    """Validate DatasetSnapshot schema and chronological holdout invariants."""
    if not isinstance(dataset, dict):
        return ["dataset snapshot must be an object"]
    errors = _schema_errors(dataset, DATASET_SCHEMA_PATH)
    if errors:
        return errors

    created = _utc(dataset["created_at"])
    frozen_at = _utc(dataset["frozen_at"]) if dataset["frozen_at"] is not None else None
    if created is None:
        errors.append("created_at must be a UTC timestamp ending in Z")
    if dataset["status"] == "FROZEN":
        if frozen_at is None or frozen_at < created:
            errors.append("FROZEN dataset requires frozen_at at or after created_at")
        if not dataset["holdout"]["frozen"] or dataset["holdout"]["locked_at"] is None:
            errors.append("FROZEN dataset requires a frozen and locked holdout")
    elif dataset["holdout"]["frozen"]:
        errors.append("non-FROZEN dataset cannot declare a frozen holdout")

    splits = sorted(dataset["splits"], key=lambda item: item["order"])
    orders = [item["order"] for item in splits]
    if len(orders) != len(set(orders)):
        errors.append("split order values must be unique")
    required_roles = {"TRAIN", "VALIDATION", "TEST"}
    roles = {item["role"] for item in splits}
    if not required_roles.issubset(roles):
        errors.append("dataset requires TRAIN, VALIDATION and TEST splits")
    if sum(item["role"] == "TEST" for item in splits) != 1:
        errors.append("dataset requires exactly one final TEST split")

    previous_end = None
    previous_role_order = -1
    role_order = {"TRAIN": 0, "VALIDATION": 1, "CALIBRATION": 2, "TEST": 3}
    for index, split in enumerate(splits):
        start = _utc(split["start"])
        end = _utc(split["end"])
        if start is None or end is None or start > end:
            errors.append(f"splits[{index}] has invalid UTC bounds")
            continue
        if previous_end is not None and start <= previous_end:
            errors.append(f"splits[{index}] overlaps or is not after the preceding split")
        current_role_order = role_order[split["role"]]
        if current_role_order < previous_role_order:
            errors.append("split roles must progress TRAIN, VALIDATION, CALIBRATION, TEST")
        previous_end = end
        previous_role_order = current_role_order

    test_splits = [item for item in splits if item["role"] == "TEST"]
    if test_splits and dataset["holdout"]["test_split_id"] != test_splits[0]["split_id"]:
        errors.append("holdout.test_split_id must identify the TEST split")
    if dataset["holdout"]["used_for_selection"] is not False:
        errors.append("final holdout must never be used for selection")
    locked_at = _utc(dataset["holdout"]["locked_at"]) if dataset["holdout"]["locked_at"] else None
    if dataset["status"] == "FROZEN" and locked_at is not None and frozen_at is not None and locked_at > frozen_at:
        errors.append("holdout locked_at cannot follow dataset frozen_at")
    return errors
