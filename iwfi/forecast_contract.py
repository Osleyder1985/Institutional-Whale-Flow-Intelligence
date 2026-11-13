"""Semantic validation for IWFI Forecast and ForecastOutcome v1 records.

JSON Schema validates record shape. This module enforces cross-field and temporal
invariants that JSON Schema cannot express, such as probability sums and record
relationships. It does not estimate or score market predictions.
"""
from datetime import datetime
from pathlib import Path
import json
import re

from jsonschema import Draft202012Validator, FormatChecker


ROOT = Path(__file__).resolve().parent.parent
FORECAST_SCHEMA_PATH = ROOT / "schemas" / "forecast" / "v1" / "forecast.schema.json"
OUTCOME_SCHEMA_PATH = ROOT / "schemas" / "forecast" / "v1" / "forecast-outcome.schema.json"
UTC_PATTERN = re.compile(r"^[0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{2}:[0-9]{2}:[0-9]{2}Z$")
PROBABILITY_TOLERANCE = 1e-6


def _load_schema(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def _utc(value):
    if not isinstance(value, str) or UTC_PATTERN.fullmatch(value) is None:
        return None
    try:
        return datetime.fromisoformat(value[:-1] + "+00:00")
    except ValueError:
        return None


def _schema_errors(record, schema_path):
    schema = _load_schema(schema_path)
    validator = Draft202012Validator(schema, format_checker=FormatChecker())
    return [f"schema: {error.message}" for error in validator.iter_errors(record)]


def validate_forecast(record):
    """Return deterministic validation errors for a Forecast v1 record."""
    if not isinstance(record, dict):
        return ["forecast must be an object"]
    errors = _schema_errors(record, FORECAST_SCHEMA_PATH)
    if errors:
        return errors

    times = record["time"]
    parsed = {key: _utc(times[key]) for key in (
        "issued_at", "as_of_time", "data_cutoff_time", "horizon_start", "horizon_end"
    )}
    for key, value in parsed.items():
        if value is None:
            errors.append(f"time.{key} must be a UTC timestamp ending in Z")
    if errors:
        return errors
    if parsed["issued_at"] < parsed["data_cutoff_time"]:
        errors.append("issued_at must not precede data_cutoff_time")
    if parsed["horizon_start"] < parsed["as_of_time"]:
        errors.append("horizon_start must be at or after as_of_time")
    if parsed["horizon_end"] <= parsed["horizon_start"]:
        errors.append("horizon_end must be after horizon_start")

    cutoff = parsed["data_cutoff_time"]
    reference_time = _utc(record["target_definition"]["reference_price"]["observed_at"])
    if reference_time is None or reference_time > cutoff:
        errors.append("reference price must be known no later than data_cutoff_time")

    for collection_name in ("supporting", "contrary"):
        for index, evidence in enumerate(record["evidence"][collection_name]):
            known_at = _utc(evidence["known_at"])
            if known_at is None or known_at > cutoff:
                errors.append(f"evidence.{collection_name}[{index}].known_at exceeds data cutoff or is not UTC")

    prediction = record["prediction"]
    magnitude = prediction["magnitude"]
    interval = magnitude["interval"]
    if interval is not None:
        if interval["lower"] > interval["upper"]:
            errors.append("magnitude interval lower must be <= upper")
        estimate = magnitude["estimate"]
        if estimate is not None and not interval["lower"] <= estimate <= interval["upper"]:
            errors.append("magnitude estimate must lie within its interval")

    for index, target in enumerate(prediction["price_targets"]):
        if target["lower_price"] > target["upper_price"]:
            errors.append(f"price_targets[{index}] lower_price must be <= upper_price")
        if _utc(target["valid_from"]) >= _utc(target["valid_until"]):
            errors.append(f"price_targets[{index}] valid_until must follow valid_from")

    for index, zone in enumerate(prediction["price_zones"]):
        if zone["lower_price"] > zone["upper_price"]:
            errors.append(f"price_zones[{index}] lower_price must be <= upper_price")
        if _utc(zone["valid_from"]) >= _utc(zone["valid_until"]):
            errors.append(f"price_zones[{index}] valid_until must follow valid_from")
        if zone["probability_status"] == "CALIBRATED" and zone["probability"] is None:
            errors.append(f"price_zones[{index}] calibrated probability must be present")
        if zone["probability_status"] != "CALIBRATED" and zone["probability"] is not None:
            errors.append(f"price_zones[{index}] probability must be null unless calibrated")

    for index, estimate in enumerate(prediction["time_to_target"]):
        lower, upper = estimate["lower_seconds"], estimate["upper_seconds"]
        if estimate["status"] == "ESTIMATED":
            if lower is None or upper is None:
                errors.append(f"time_to_target[{index}] estimated bounds must both be present")
            elif lower > upper:
                errors.append(f"time_to_target[{index}] lower_seconds must be <= upper_seconds")
        elif lower is not None or upper is not None:
            errors.append(f"time_to_target[{index}] NOT_ESTIMABLE bounds must be null")

    probabilities = prediction["scenario_probabilities"]
    values = (probabilities["bullish"], probabilities["bearish"], probabilities["sideways"])
    if probabilities["status"] == "CALIBRATED":
        if any(value is None for value in values):
            errors.append("calibrated scenario probabilities must all be present")
        elif abs(sum(values) - 1.0) > PROBABILITY_TOLERANCE:
            errors.append("calibrated scenario probabilities must sum to 1")
        if not probabilities["calibration_ref"]:
            errors.append("calibrated scenario probabilities require calibration_ref")
    elif any(value is not None for value in values):
        errors.append("scenario probabilities must be null unless calibrated")

    if record["status"] == "ISSUED":
        if prediction["direction"] == "UNDETERMINED":
            errors.append("issued forecast direction cannot be UNDETERMINED")
        if record["abstention"] is not None:
            errors.append("issued forecast must have abstention=null")
        if record["data_quality"]["status"] == "FAIL":
            errors.append("data quality FAIL requires abstention")
    else:
        if prediction["direction"] != "UNDETERMINED":
            errors.append("abstained forecast direction must be UNDETERMINED")
        if record["abstention"] is None:
            errors.append("abstained forecast requires an abstention reason")
    return errors


def validate_forecast_outcome(record, forecast=None):
    """Validate an Outcome and, when supplied, its relationship to its Forecast."""
    if not isinstance(record, dict):
        return ["outcome must be an object"]
    errors = _schema_errors(record, OUTCOME_SCHEMA_PATH)
    if errors:
        return errors

    window = record["observation_window"]
    start, end, expected_end = (_utc(window[key]) for key in ("start", "end", "expected_end"))
    if any(value is None for value in (start, end, expected_end)):
        errors.append("observation window timestamps must be UTC values ending in Z")
        return errors
    if end < start or expected_end <= start:
        errors.append("observation window must have ordered start, end and expected_end")
    if end > expected_end:
        errors.append("observation window end cannot exceed expected_end")

    status = record["status"]
    quality = record["data_quality"]
    if status == "COMPLETE":
        if end != expected_end:
            errors.append("COMPLETE outcome must cover the full expected horizon")
        if quality["status"] != "PASS" or quality["coverage_ratio"] != 1:
            errors.append("COMPLETE outcome requires PASS quality and coverage_ratio=1")
    if status == "CENSORED" and end >= expected_end:
        errors.append("CENSORED outcome must end before expected_end")

    for collection_name in ("target_events", "zone_events"):
        for index, event in enumerate(record[collection_name]):
            observed_at = event["first_observed_at"]
            observed_price = event["first_observed_price"]
            if event["result"] in ("REACHED", "TOUCHED"):
                if observed_at is None or observed_price is None:
                    errors.append(f"{collection_name}[{index}] confirmed event requires observed time and price")
            if event["result"] == "CROSSED_BY_GAP" and not event["gap_crossed"]:
                errors.append(f"{collection_name}[{index}] CROSSED_BY_GAP requires gap_crossed=true")

    if forecast is not None:
        if not isinstance(forecast, dict):
            errors.append("forecast reference must be an object")
        else:
            if record["forecast_id"] != forecast.get("forecast_id"):
                errors.append("outcome forecast_id does not match the supplied Forecast")
            forecast_time = forecast.get("time", {})
            if window["start"] != forecast_time.get("horizon_start"):
                errors.append("outcome observation start must match Forecast horizon_start")
            if window["expected_end"] != forecast_time.get("horizon_end"):
                errors.append("outcome expected_end must match Forecast horizon_end")
            forecast_market = forecast.get("market", {})
            outcome_market = record["reference_market"]
            for field in ("instrument", "venue"):
                if outcome_market[field] != forecast_market.get(field):
                    errors.append(f"outcome {field} must match Forecast market")
            if outcome_market["quote_currency"] != forecast_market.get("quote_currency"):
                errors.append("outcome quote_currency must match Forecast market")
    return errors
