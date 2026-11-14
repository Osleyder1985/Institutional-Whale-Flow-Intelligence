"""Offline validator for a single Binance Vision Spot aggTrades archive.

No network access, extraction to disk, payload persistence, or float conversion.
"""
import argparse
import csv
import hashlib
import json
import re
import sys
import zipfile
from datetime import date, datetime, time, timedelta, timezone
from decimal import Decimal, InvalidOperation
from pathlib import Path


class ArchiveValidationError(ValueError):
    """Raised when an archive or its evidence fails validation."""


_DECIMAL = re.compile(r"^\d+(?:\.\d+)?$")
_INTEGER = re.compile(r"^\d+$")
_SHA256 = re.compile(r"^([0-9a-fA-F]{64})(?:\s+[* ]?(.+))?$")
_BOOLEAN = {"true", "false"}
_MICROSECOND_BOUNDARY = date(2025, 1, 1)


def _sha256_file(path):
    digest = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _expected_checksum(checksum_path, archive_name):
    try:
        content = Path(checksum_path).read_text(encoding="utf-8").strip()
    except OSError as exc:
        raise ArchiveValidationError(f"cannot read checksum file: {exc}") from exc
    match = _SHA256.fullmatch(content)
    if not match:
        raise ArchiveValidationError("checksum file must contain a SHA-256 digest and optional filename")
    named_file = match.group(2)
    if named_file and Path(named_file).name != archive_name:
        raise ArchiveValidationError("checksum filename does not match archive filename")
    return match.group(1).lower()


def _integer(value, field, row_number):
    if not _INTEGER.fullmatch(value):
        raise ArchiveValidationError(f"row {row_number}: {field} must be a non-negative integer")
    return int(value)


def _positive_decimal(value, field, row_number):
    if not _DECIMAL.fullmatch(value):
        raise ArchiveValidationError(f"row {row_number}: {field} must be a plain decimal string")
    try:
        number = Decimal(value)
    except InvalidOperation as exc:
        raise ArchiveValidationError(f"row {row_number}: invalid {field}") from exc
    if not number.is_finite() or number <= 0:
        raise ArchiveValidationError(f"row {row_number}: {field} must be positive and finite")


def _utc_day_bounds(day, unit):
    start = datetime.combine(day, time.min, tzinfo=timezone.utc)
    end = start + timedelta(days=1)
    multiplier = 1_000_000 if unit == "microseconds" else 1_000
    epoch = datetime(1970, 1, 1, tzinfo=timezone.utc)
    start_value = int((start - epoch).total_seconds()) * multiplier
    end_value = int((end - epoch).total_seconds()) * multiplier
    return start_value, end_value


def _validate_csv(stream, symbol, archive_day):
    unit = "microseconds" if archive_day >= _MICROSECOND_BOUNDARY else "milliseconds"
    lower, upper = _utc_day_bounds(archive_day, unit)
    reader = csv.reader(stream)
    count = 0
    first_timestamp = None
    last_timestamp = None

    for row_number, row in enumerate(reader, start=1):
        if len(row) != 8:
            raise ArchiveValidationError(
                f"row {row_number}: expected 8 columns, received {len(row)}"
            )
        agg_id = _integer(row[0], "aggregate_trade_id", row_number)
        _positive_decimal(row[1], "price", row_number)
        _positive_decimal(row[2], "quantity", row_number)
        first_trade_id = _integer(row[3], "first_trade_id", row_number)
        last_trade_id = _integer(row[4], "last_trade_id", row_number)
        timestamp = _integer(row[5], "timestamp", row_number)
        if first_trade_id > last_trade_id:
            raise ArchiveValidationError(
                f"row {row_number}: first_trade_id exceeds last_trade_id"
            )
        if row[6].strip().lower() not in _BOOLEAN:
            raise ArchiveValidationError(f"row {row_number}: invalid isBuyerMaker boolean")
        if row[7].strip().lower() not in _BOOLEAN:
            raise ArchiveValidationError(f"row {row_number}: invalid isBestMatch boolean")
        if not lower <= timestamp < upper:
            raise ArchiveValidationError(
                f"row {row_number}: timestamp is outside expected UTC day for {unit}"
            )

        if count == 0:
            first_timestamp = timestamp
        last_timestamp = timestamp
        count += 1

    if count == 0:
        raise ArchiveValidationError("CSV contains no data rows")

    return {
        "symbol": symbol,
        "archive_date_utc": archive_day.isoformat(),
        "market": "SPOT",
        "dataset": "aggTrades",
        "rows_validated": count,
        "timestamp_unit": unit,
        "first_timestamp": first_timestamp,
        "last_timestamp": last_timestamp,
        "actor_attribution": "UNKNOWN",
        "participant_identity_inferred": False,
    }


def validate_archive(zip_path, checksum_path, symbol, archive_date):
    """Validate one archive in place and return metadata; never extracts its payload."""
    archive = Path(zip_path)
    if not archive.is_file():
        raise ArchiveValidationError("archive ZIP does not exist")
    if not re.fullmatch(r"[A-Z0-9]+", symbol):
        raise ArchiveValidationError("symbol must contain uppercase alphanumeric characters")
    try:
        day = date.fromisoformat(archive_date)
    except (TypeError, ValueError) as exc:
        raise ArchiveValidationError("archive_date must be YYYY-MM-DD") from exc
    if day.isoformat() != archive_date:
        raise ArchiveValidationError("archive_date must use canonical YYYY-MM-DD format")

    expected_zip = f"{symbol}-aggTrades-{archive_date}.zip"
    expected_csv = f"{symbol}-aggTrades-{archive_date}.csv"
    if archive.name != expected_zip:
        raise ArchiveValidationError(f"archive filename must be {expected_zip}")

    expected_hash = _expected_checksum(checksum_path, archive.name)
    actual_hash = _sha256_file(archive)
    if actual_hash != expected_hash:
        raise ArchiveValidationError("SHA-256 checksum mismatch")

    try:
        with zipfile.ZipFile(archive, "r") as zipped:
            entries = zipped.infolist()
            if len(entries) != 1:
                raise ArchiveValidationError("ZIP must contain exactly one CSV entry")
            entry = entries[0]
            if entry.is_dir() or entry.filename != expected_csv:
                raise ArchiveValidationError(f"ZIP must contain only {expected_csv}")
            with zipped.open(entry, "r") as raw:
                import io
                import textwrap
                text_stream = io.TextIOWrapper(raw, encoding="utf-8", newline="")
                try:
                    result = _validate_csv(text_stream, symbol, day)
                except (UnicodeDecodeError, csv.Error) as exc:
                    raise ArchiveValidationError(f"invalid CSV encoding or structure: {exc}") from exc
                finally:
                    text_stream.detach()
    except zipfile.BadZipFile as exc:
        raise ArchiveValidationError("invalid or corrupt ZIP archive") from exc
    except OSError as exc:
        raise ArchiveValidationError(f"cannot read ZIP archive: {exc}") from exc

    result["archive_sha256"] = actual_hash
    result["checksum_verified"] = True
    return result


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--zip", required=True, dest="zip_path")
    parser.add_argument("--checksum", required=True)
    parser.add_argument("--symbol", required=True)
    parser.add_argument("--date", required=True, dest="archive_date")
    args = parser.parse_args(argv)
    try:
        result = validate_archive(args.zip_path, args.checksum, args.symbol, args.archive_date)
    except ArchiveValidationError as exc:
        print(json.dumps({"status": "INVALID", "error": str(exc)}, ensure_ascii=False))
        return 2
    print(json.dumps({"status": "VALID", **result}, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    sys.exit(main())
