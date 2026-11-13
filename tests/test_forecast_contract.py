"""Schema and semantic contract tests for IWFI Forecast v1 records."""
import copy
import json
import unittest
from pathlib import Path

from jsonschema import Draft202012Validator, FormatChecker

from iwfi.forecast_contract import validate_forecast, validate_forecast_outcome


ROOT = Path(__file__).resolve().parent
SCHEMA_ROOT = ROOT.parent / "schemas" / "forecast" / "v1"


class ForecastContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.forecast_schema = json.loads((SCHEMA_ROOT / "forecast.schema.json").read_text(encoding="utf-8"))
        cls.outcome_schema = json.loads((SCHEMA_ROOT / "forecast-outcome.schema.json").read_text(encoding="utf-8"))
        cls.forecast = json.loads((SCHEMA_ROOT / "examples" / "forecast.synthetic.json").read_text(encoding="utf-8"))
        cls.outcome = json.loads((SCHEMA_ROOT / "examples" / "forecast-outcome.synthetic.json").read_text(encoding="utf-8"))
        Draft202012Validator.check_schema(cls.forecast_schema)
        Draft202012Validator.check_schema(cls.outcome_schema)
        cls.forecast_validator = Draft202012Validator(cls.forecast_schema, format_checker=FormatChecker())
        cls.outcome_validator = Draft202012Validator(cls.outcome_schema, format_checker=FormatChecker())

    def test_schemas_are_draft_2020_12_and_versioned(self):
        self.assertEqual(self.forecast_schema["$schema"], "https://json-schema.org/draft/2020-12/schema")
        self.assertEqual(self.outcome_schema["$schema"], "https://json-schema.org/draft/2020-12/schema")
        self.assertEqual(self.forecast_schema["properties"]["schema_version"]["const"], "1.0.0")
        self.assertEqual(self.outcome_schema["properties"]["schema_version"]["const"], "1.0.0")

    def test_synthetic_fixtures_validate_against_json_schemas(self):
        self.assertEqual(list(self.forecast_validator.iter_errors(self.forecast)), [])
        self.assertEqual(list(self.outcome_validator.iter_errors(self.outcome)), [])

    def test_semantic_validators_accept_synthetic_fixtures(self):
        self.assertEqual(validate_forecast(self.forecast), [])
        self.assertEqual(validate_forecast_outcome(self.outcome, self.forecast), [])

    def test_forecast_rejects_non_utc_timestamp(self):
        item = copy.deepcopy(self.forecast)
        item["time"]["data_cutoff_time"] = "2026-01-01T00:00:00-05:00"
        self.assertTrue(validate_forecast(item))

    def test_forecast_rejects_evidence_known_after_data_cutoff(self):
        item = copy.deepcopy(self.forecast)
        item["evidence"]["supporting"][0]["known_at"] = "2026-01-01T00:00:01Z"
        self.assertTrue(any("data cutoff" in error for error in validate_forecast(item)))

    def test_forecast_rejects_calibrated_probabilities_that_do_not_sum_to_one(self):
        item = copy.deepcopy(self.forecast)
        probabilities = item["prediction"]["scenario_probabilities"]
        probabilities.update({"status": "CALIBRATED", "bullish": 0.7, "bearish": 0.2, "sideways": 0.2, "calibration_ref": "calibration-v1"})
        self.assertTrue(any("sum to 1" in error for error in validate_forecast(item)))

    def test_forecast_rejects_probability_values_when_not_calibrated(self):
        item = copy.deepcopy(self.forecast)
        item["prediction"]["scenario_probabilities"]["bullish"] = 0.8
        self.assertTrue(any("must be null unless calibrated" in error for error in validate_forecast(item)))

    def test_forecast_allows_explicit_unestimated_target(self):
        item = copy.deepcopy(self.forecast)
        target = item["prediction"]["price_targets"][0]
        target["status"] = "NOT_ESTIMABLE"
        target["lower_price"] = None
        target["upper_price"] = None
        self.assertEqual(validate_forecast(item), [])
        target["lower_price"] = 100500
        self.assertTrue(any("NOT_ESTIMABLE bounds must be null" in error for error in validate_forecast(item)))

    def test_calibrated_zone_probability_requires_calibration_reference(self):
        item = copy.deepcopy(self.forecast)
        zone = item["prediction"]["price_zones"][0]
        zone["probability_status"] = "CALIBRATED"
        zone["probability"] = 0.6
        zone["calibration_ref"] = None
        self.assertTrue(any("requires calibration_ref" in error for error in validate_forecast(item)))

    def test_forecast_rejects_inverted_price_zone(self):
        item = copy.deepcopy(self.forecast)
        item["prediction"]["price_zones"][0]["lower_price"] = 103000
        self.assertTrue(any("lower_price" in error for error in validate_forecast(item)))

    def test_forecast_rejects_estimated_time_without_bounds(self):
        item = copy.deepcopy(self.forecast)
        item["prediction"]["time_to_target"][0]["status"] = "ESTIMATED"
        self.assertTrue(any("bounds must both be present" in error for error in validate_forecast(item)))

    def test_abstained_forecast_requires_undetermined_direction_and_reason(self):
        item = copy.deepcopy(self.forecast)
        item["status"] = "ABSTAINED"
        item["prediction"]["direction"] = "UNDETERMINED"
        item["abstention"] = {"reason_code": "INSUFFICIENT_DATA", "explanation": "Synthetic test abstention"}
        self.assertEqual(validate_forecast(item), [])
        item["abstention"] = None
        self.assertTrue(validate_forecast(item))

    def test_outcome_rejects_wrong_forecast_reference(self):
        item = copy.deepcopy(self.outcome)
        item["forecast_id"] = "different-forecast"
        self.assertTrue(any("does not match" in error for error in validate_forecast_outcome(item, self.forecast)))

    def test_censored_outcome_must_end_before_expected_horizon_end(self):
        item = copy.deepcopy(self.outcome)
        item["observation_window"]["end"] = item["observation_window"]["expected_end"]
        self.assertTrue(any("must end before" in error for error in validate_forecast_outcome(item, self.forecast)))

    def test_complete_outcome_requires_full_coverage(self):
        item = copy.deepcopy(self.outcome)
        item["status"] = "COMPLETE"
        item["observation_window"]["end"] = item["observation_window"]["expected_end"]
        item["data_quality"] = {"status": "PASS", "coverage_ratio": 1, "missing_intervals": []}
        self.assertEqual(validate_forecast_outcome(item, self.forecast), [])

    def test_gap_crossing_requires_interval_and_cannot_claim_exact_touch(self):
        item = copy.deepcopy(self.outcome)
        event = item["target_events"][0]
        event["result"] = "CROSSED_BY_GAP"
        event["gap_crossed"] = True
        event["first_observed_at"] = None
        event["first_observed_price"] = None
        event["crossing_interval"] = {
            "last_observed_before": {"observed_at": "2026-01-01T11:55:00Z", "price": 100100},
            "first_observed_after": {"observed_at": "2026-01-01T12:05:00Z", "price": 100600}
        }
        item["observation_window"]["end"] = "2026-01-01T12:05:00Z"
        item["data_quality"]["missing_intervals"] = [
            {"start": "2026-01-01T11:55:00Z", "end": "2026-01-01T12:05:00Z"}
        ]
        self.assertEqual(validate_forecast_outcome(item, self.forecast), [])
        event["crossing_interval"] = None
        self.assertTrue(any("requires a gap flag and crossing interval" in error for error in validate_forecast_outcome(item, self.forecast)))

    def test_not_reached_requires_fully_observed_horizon(self):
        item = copy.deepcopy(self.outcome)
        item["target_events"][0]["result"] = "NOT_REACHED"
        self.assertTrue(any("fully observed horizon" in error for error in validate_forecast_outcome(item, self.forecast)))


if __name__ == "__main__":
    unittest.main()
