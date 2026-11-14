"""Offline Binance Spot aggTrades aggressor-flow metrics.

The module performs no network access and writes no files. Numeric outputs are
serialized as decimal strings to avoid binary floating-point rounding.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import io
import json
import sys
import zipfile
from datetime import date, datetime, time, timedelta, timezone
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any

from iwfi.binance_vision_archive_validator import (
    ArchiveValidationError,
    validate_archive,
)


class SpotFlowMetricsError(ValueError):
    """Raised when an archive cannot safely produce flow metrics."""


def _sha256_file(path: str | Path) -> str:
    digest = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _decimal(value: str, field: str, row_number: int) -> Decimal:
    try:
        result = Decimal(value)
    except (InvalidOperation, TypeError) as exc:
        raise SpotFlowMetricsError(f"row {row_number}: invalid {field}") from exc
    if not result.is_finite() or result <= 0:
        raise SpotFlowMetricsError(f"row {row_number}: {field} must be positive and finite")
    return result


def _format_decimal(value: Decimal) -> str:
    return format(value, "f")


def _utc_text(day: date, seconds_from_midnight: int) -> str:
    value = datetime.combine(day, time.min, tzinfo=timezone.utc) + timedelta(seconds=seconds_from_midnight)
    return value.strftime("%Y-%m-%dT%H:%M:%SZ")


def _bucket_record() -> dict[str, Any]:
    return {
        "aggregate_trade_count": 0,
        "taker_buy_base_qty": Decimal("0"),
        "taker_sell_base_qty": Decimal("0"),
        "taker_buy_quote_qty": Decimal("0"),
        "taker_sell_quote_qty": Decimal("0"),
        "first_timestamp": None,
        "last_timestamp": None,
    }


def _finalize_bucket(record: dict[str, Any], cumulative_base: Decimal,
                     cumulative_quote: Decimal) -> dict[str, Any]:
    buy_base = record["taker_buy_base_qty"]
    sell_base = record["taker_sell_base_qty"]
    buy_quote = record["taker_buy_quote_qty"]
    sell_quote = record["taker_sell_quote_qty"]
    return {
        "aggregate_trade_count": record["aggregate_trade_count"],
        "taker_buy_base_qty": _format_decimal(buy_base),
        "taker_sell_base_qty": _format_decimal(sell_base),
        "taker_buy_quote_qty": _format_decimal(buy_quote),
        "taker_sell_quote_qty": _format_decimal(sell_quote),
        "signed_base_volume_delta": _format_decimal(buy_base - sell_base),
        "signed_quote_volume_delta": _format_decimal(buy_quote - sell_quote),
        "cumulative_signed_base_volume": _format_decimal(cumulative_base),
        "cumulative_signed_quote_volume": _format_decimal(cumulative_quote),
        "first_timestamp": record["first_timestamp"],
        "last_timestamp": record["last_timestamp"],
    }


def process_archive(zip_path: str | Path, checksum_path: str | Path,
                    symbol: str, archive_date: str,
                    interval_seconds: int | None = None) -> dict[str, Any]:
    """Validate and summarize one archive without persisting payloads/results.

    ``interval_seconds`` is caller-selected and must divide one UTC day. If it
    is omitted, one full-day aggregate is returned.
    """
    if interval_seconds is not None:
        if isinstance(interval_seconds, bool) or not isinstance(interval_seconds, int):
            raise SpotFlowMetricsError("interval_seconds must be an integer")
        if interval_seconds <= 0 or 86400 % interval_seconds:
            raise SpotFlowMetricsError("interval_seconds must be positive and divide 86400")

    try:
        validation = validate_archive(zip_path, checksum_path, symbol, archive_date)
    except ArchiveValidationError as exc:
        raise SpotFlowMetricsError(f"archive validation failed: {exc}") from exc

    day = date.fromisoformat(archive_date)
    unit = validation["timestamp_unit"]
    multiplier = 1_000_000 if unit == "microseconds" else 1_000
    day_start = int(datetime.combine(day, time.min, tzinfo=timezone.utc).timestamp()) * multiplier
    interval = interval_seconds or 86400
    buckets: dict[int, dict[str, Any]] = {}
    previous_agg_id: int | None = None
    previous_timestamp: int | None = None
    processed_rows = 0

    try:
        with zipfile.ZipFile(zip_path, "r") as archive:
            member = archive.namelist()[0]
            with archive.open(member, "r") as raw:
                stream = io.TextIOWrapper(raw, encoding="utf-8", newline="")
                try:
                    for row_number, row in enumerate(csv.reader(stream), start=1):
                        if len(row) != 8:
                            raise SpotFlowMetricsError(
                                f"row {row_number}: expected 8 columns, received {len(row)}"
                            )
                        agg_id = int(row[0])
                        price = _decimal(row[1], "price", row_number)
                        quantity = _decimal(row[2], "quantity", row_number)
                        timestamp = int(row[5])
                        if previous_agg_id is not None and agg_id <= previous_agg_id:
                            raise SpotFlowMetricsError("aggregate trade IDs must be strictly increasing")
                        if previous_timestamp is not None and timestamp < previous_timestamp:
                            raise SpotFlowMetricsError("timestamps must be nondecreasing")
                        previous_agg_id = agg_id
                        previous_timestamp = timestamp

                        offset_seconds = (timestamp - day_start) // multiplier
                        bucket_start = (offset_seconds // interval) * interval
                        record = buckets.setdefault(bucket_start, _bucket_record())
                        is_buyer_maker = row[6].strip().lower()
                        if is_buyer_maker == "false":
                            record["taker_buy_base_qty"] += quantity
                            record["taker_buy_quote_qty"] += price * quantity
                        elif is_buyer_maker == "true":
                            record["taker_sell_base_qty"] += quantity
                            record["taker_sell_quote_qty"] += price * quantity
                        else:
                            raise SpotFlowMetricsError(f"row {row_number}: invalid isBuyerMaker boolean")
                        record["aggregate_trade_count"] += 1
                        if record["first_timestamp"] is None:
                            record["first_timestamp"] = timestamp
                        record["last_timestamp"] = timestamp
                        processed_rows += 1
                finally:
                    stream.detach()
    except (OSError, zipfile.BadZipFile, UnicodeDecodeError, csv.Error) as exc:
        raise SpotFlowMetricsError(f"cannot process validated archive: {exc}") from exc

    if processed_rows != validation["rows_validated"]:
        raise SpotFlowMetricsError("row count changed between validation and processing")
    if _sha256_file(zip_path) != validation["archive_sha256"]:
        raise SpotFlowMetricsError("archive changed between validation and processing")

    output_buckets = []
    daily_record = _bucket_record()
    cumulative_base = Decimal("0")
    cumulative_quote = Decimal("0")
    for bucket_start in sorted(buckets):
        record = buckets[bucket_start]
        daily_record["aggregate_trade_count"] += record["aggregate_trade_count"]
        for key in ("taker_buy_base_qty", "taker_sell_base_qty", "taker_buy_quote_qty", "taker_sell_quote_qty"):
            daily_record[key] += record[key]
        if daily_record["first_timestamp"] is None:
            daily_record["first_timestamp"] = record["first_timestamp"]
        daily_record["last_timestamp"] = record["last_timestamp"]
        cumulative_base += record["taker_buy_base_qty"] - record["taker_sell_base_qty"]
        cumulative_quote += record["taker_buy_quote_qty"] - record["taker_sell_quote_qty"]
        output_buckets.append({
            "interval_start_utc": _utc_text(day, bucket_start),
            "interval_end_utc": _utc_text(day, bucket_start + interval),
            **_finalize_bucket(record, cumulative_base, cumulative_quote),
        })

    expected_bucket_count = 86400 // interval
    return {
        "status": "VALID",
        "venue": "BINANCE",
        "market": "SPOT",
        "symbol": symbol,
        "dataset": "aggTrades",
        "record_semantics": "AGGREGATED_TRADES",
        "participant_identity": "UNKNOWN",
        "institutional_attribution": "NOT_ESTABLISHED",
        "archive_date_utc": archive_date,
        "timestamp_unit": unit,
        "archive_sha256": validation["archive_sha256"],
        "checksum_verified": True,
        "rows_processed": processed_rows,
        "interval_seconds": interval,
        "expected_interval_count": expected_bucket_count,
        "observed_interval_count": len(output_buckets),
        "unobserved_interval_count": expected_bucket_count - len(output_buckets),
        "unobserved_interval_semantics": "NO_RECORDS_OBSERVED; ZERO_ACTIVITY_NOT_PROVEN",
        "daily_summary": _finalize_bucket(daily_record, cumulative_base, cumulative_quote),
        "buckets": output_buckets,
        "limitations": [
            "AggTrades are aggregated records, not guaranteed individual fills.",
            "Metrics describe aggressor-side activity on this Binance Spot market only.",
            "No participant, institution, beneficial owner, wallet, intent, or causality is inferred.",
            "Exchange Spot flow is not on-chain flow and does not establish institutional buying or selling.",
        ],
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--zip", required=True, dest="zip_path")
    parser.add_argument("--checksum", required=True)
    parser.add_argument("--symbol", required=True)
    parser.add_argument("--date", required=True, dest="archive_date")
    parser.add_argument("--interval-seconds", type=int)
    args = parser.parse_args(argv)
    try:
        result = process_archive(args.zip_path, args.checksum, args.symbol,
                                 args.archive_date, args.interval_seconds)
    except (SpotFlowMetricsError, OSError) as exc:
        print(json.dumps({"status": "INVALID", "error": str(exc)}, ensure_ascii=False))
        return 2
    print(json.dumps(result, ensure_ascii=False, sort_keys=True, separators=(",", ":")))
    return 0


if __name__ == "__main__":
    sys.exit(main())
