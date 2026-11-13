"""Schema and semantic tests for point-in-time feature and dataset snapshots."""
import copy
import json
import unittest
from pathlib import Path

from jsonschema import Draft202012Validator, FormatChecker

from iwfi.pit_dataset import validate_dataset_snapshot, validate_feature_snapshot


ROOT = Path(__file__).resolve().parent
SCHEMA_ROOT = ROOT.parent / "schemas" / "predictive" / "v1"


class PointInTimeDatasetTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.feature_schema = json.loads((SCHEMA_ROOT / "feature-snapshot.schema.json").read_text(encoding="utf-8"))
        cls.dataset_schema = json.loads((SCHEMA_ROOT / "dataset-snapshot.schema.json").read_text(encoding="utf-8"))
        cls.feature = json.loads((SCHEMA_ROOT / "examples" / "feature-snapshot.synthetic.json").read_text(encoding="utf-8"))
        cls.dataset = json.loads((SCHEMA_ROOT / "examples" / "dataset-snapshot.synthetic.json").read_text(encoding="utf-8"))
        Draft202012Validator.check_schema(cls.feature_schema)
        Draft202012Validator.check_schema(cls.dataset_schema)
        cls.feature_validator = Draft202012Validator(cls.feature_schema, format_checker=FormatChecker())
        cls.dataset_validator = Draft202012Validator(cls.dataset_schema, format_checker=FormatChecker())

    def test_schemas_are_draft_2020_12_and_versioned(self):
        self.assertEqual(self.feature_schema["$schema"], "https://json-schema.org/draft/2020-12/schema")
        self.assertEqual(self.dataset_schema["$schema"], "https://json-schema.org/draft/2020-12/schema")
        self.assertEqual(self.feature_schema["properties"]["schema_version"]["const"], "1.0.0")
        self.assertEqual(self.dataset_schema["properties"]["schema_version"]["const"], "1.0.0")

    def test_synthetic_fixtures_validate_against_schemas(self):
        self.assertEqual(list(self.feature_validator.iter_errors(self.feature)), [])
        self.assertEqual(list(self.dataset_validator.iter_errors(self.dataset)), [])

    def test_semantic_validators_accept_fixtures(self):
        self.assertEqual(validate_feature_snapshot(self.feature), [])
        self.assertEqual(validate_dataset_snapshot(self.dataset), [])

    def test_future_event_is_allowed_when_known_before_cutoff(self):
        item = copy.deepcopy(self.feature)
        future = item["source_observations"][1]
        self.assertGreater(future["event_time"], item["data_cutoff_time"])
        self.assertLessEqual(future["available_at"], item["data_cutoff_time"])
        self.assertEqual(validate_feature_snapshot(item), [])

    def test_late_arriving_source_is_rejected_even_with_old_event_time(self):
        item = copy.deepcopy(self.feature)
        source = item["source_observations"][0]
        source["ingested_at"] = "2026-01-01T00:00:03Z"
        source["available_at"] = "2026-01-01T00:00:03Z"
        self.assertTrue(any("not available by data_cutoff_time" in error for error in validate_feature_snapshot(item)))

    def test_source_event_time_must_be_utc_when_present(self):
        item = copy.deepcopy(self.feature)
        item["source_observations"][0]["event_time"] = "2026-01-01T00:00:00-05:00"
        self.assertTrue(any("timestamps must be UTC" in error for error in validate_feature_snapshot(item)))

    def test_source_available_at_cannot_precede_ingestion(self):
        item = copy.deepcopy(self.feature)
        item["source_observations"][0]["available_at"] = "2026-01-01T00:00:01Z"
        self.assertTrue(any("cannot precede" in error for error in validate_feature_snapshot(item)))

    def test_feature_must_reference_known_source_records(self):
        item = copy.deepcopy(self.feature)
        item["features"][0]["source_refs"] = ["unknown-source"]
        self.assertTrue(any("unknown source observations" in error for error in validate_feature_snapshot(item)))

    def test_missing_feature_requires_null_value_and_reason(self):
        item = copy.deepcopy(self.feature)
        feature = item["features"][0]
        feature["status"] = "MISSING"
        feature["value"] = None
        feature["missing_reason"] = "Source did not provide the observation"
        item["status"] = "DEGRADED"
        item["quality"]["status"] = "DEGRADED"
        self.assertEqual(validate_feature_snapshot(item), [])
        feature["value"] = 0
        self.assertTrue(any("non-AVAILABLE value must be null" in error for error in validate_feature_snapshot(item)))

    def test_ready_snapshot_cannot_contain_missing_feature(self):
        item = copy.deepcopy(self.feature)
        item["features"][0]["status"] = "MISSING"
        item["features"][0]["value"] = None
        item["features"][0]["missing_reason"] = "missing"
        self.assertTrue(any("READY snapshot may contain only AVAILABLE" in error for error in validate_feature_snapshot(item)))

    def test_dataset_rejects_overlapping_splits(self):
        item = copy.deepcopy(self.dataset)
        item["splits"][1]["start"] = "2025-09-30T12:00:00Z"
        self.assertTrue(any("overlaps" in error for error in validate_dataset_snapshot(item)))

    def test_dataset_requires_final_test_holdout(self):
        item = copy.deepcopy(self.dataset)
        item["holdout"]["used_for_selection"] = True
        self.assertTrue(validate_dataset_snapshot(item))

    def test_dataset_rejects_validation_fitted_transform(self):
        item = copy.deepcopy(self.dataset)
        item["transforms"][0]["fit_scope"] = "VALIDATION"
        self.assertTrue(validate_dataset_snapshot(item))

    def test_frozen_dataset_requires_locked_holdout(self):
        item = copy.deepcopy(self.dataset)
        item["holdout"]["frozen"] = False
        self.assertTrue(any("frozen and locked holdout" in error for error in validate_dataset_snapshot(item)))


if __name__ == "__main__":
    unittest.main()
