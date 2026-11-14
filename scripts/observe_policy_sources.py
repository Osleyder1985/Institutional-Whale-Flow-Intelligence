"""Explicitly observe allowlisted policy sources without overwriting prior evidence."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import urlparse
from urllib.request import HTTPRedirectHandler, Request, build_opener


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_REGISTRY = ROOT / "data" / "policy-document-sources-v1.0.json"
CHUNK_SIZE = 1024 * 1024
ALLOWED_SOURCE_HOSTS = {"raw.githubusercontent.com", "creativecommons.org", "bin.bnbstatic.com"}
SHA256_RE = re.compile(r"^[a-f0-9]{64}$")


class ObservationError(RuntimeError):
    pass


class AllowlistedRedirectHandler(HTTPRedirectHandler):
    def __init__(self, allowed_hosts):
        super().__init__()
        self.allowed_hosts = set(allowed_hosts)

    def redirect_request(self, req, fp, code, msg, headers, newurl):
        parsed = urlparse(newurl)
        if parsed.scheme != "https" or parsed.hostname not in self.allowed_hosts:
            raise ObservationError("REDIRECT_TARGET_NOT_ALLOWLISTED")
        if parsed.username or parsed.password:
            raise ObservationError("REDIRECT_CREDENTIALS_FORBIDDEN")
        return super().redirect_request(req, fp, code, msg, headers, newurl)


def utc_now():
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def load_registry(path=DEFAULT_REGISTRY):
    try:
        payload = json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ObservationError("SOURCE_REGISTRY_INVALID") from exc
    if not isinstance(payload, dict) or payload.get("manifest_version") != "1.0.0":
        raise ObservationError("SOURCE_REGISTRY_INVALID")
    documents = payload.get("documents")
    if not isinstance(documents, list) or not documents:
        raise ObservationError("SOURCE_REGISTRY_EMPTY")
    result = {}
    for item in documents:
        if not isinstance(item, dict):
            raise ObservationError("SOURCE_RECORD_INVALID")
        source_id = item.get("document_id")
        url = item.get("url")
        parsed = urlparse(url) if isinstance(url, str) else None
        if (not isinstance(source_id, str) or not re.fullmatch(r"[a-z0-9_.-]+", source_id) or source_id in {".", ".."} or source_id in result
                or parsed is None or parsed.scheme != "https" or parsed.hostname not in ALLOWED_SOURCE_HOSTS
                or parsed.username or parsed.password or parsed.fragment
                or not isinstance(item.get("filename"), str) or not re.fullmatch(r"[a-zA-Z0-9_.-]+", item.get("filename", ""))
                or not isinstance(item.get("provider"), str)):
            raise ObservationError("SOURCE_RECORD_INVALID")
        baseline = item.get("baseline_sha256")
        if baseline is not None and (not isinstance(baseline, str) or not SHA256_RE.fullmatch(baseline)):
            raise ObservationError("BASELINE_SHA256_INVALID")
        result[source_id] = dict(item)
    return result


def read_body(response):
    digest = hashlib.sha256()
    size = 0
    while True:
        block = response.read(CHUNK_SIZE)
        if not block:
            break
        digest.update(block)
        size += len(block)
    expected_length = response.headers.get("Content-Length")
    if expected_length is not None and int(expected_length) != size:
        raise ObservationError("CONTENT_LENGTH_MISMATCH")
    return digest.hexdigest(), size


def observe_source(source, opener=None, observed_at=None):
    url = source["url"]
    parsed = urlparse(url)
    allowed_hosts = {parsed.hostname}
    opener = opener or build_opener(AllowlistedRedirectHandler(allowed_hosts))
    request = Request(url, headers={"User-Agent": "IWFI-policy-source-observer/1.0"})
    common = {
        "observation_version": "1.0.0",
        "document_id": source["document_id"],
        "provider": source["provider"],
        "requested_url": url,
        "observed_at_utc": observed_at or utc_now(),
        "declared_version": source.get("observed_version"),
        "url_is_mutable": source.get("url_is_mutable", True),
        "authorization_status": "NOT_GRANTED",
        "legal_review_status": "NOT_PERFORMED",
    }
    try:
        with opener.open(request, timeout=60) as response:
            status = getattr(response, "status", None) or response.getcode()
            if status != 200:
                raise ObservationError("HTTP_STATUS_NOT_SUCCESS")
            final_url = response.geturl()
            final = urlparse(final_url)
            if final.scheme != "https" or final.hostname not in allowed_hosts:
                raise ObservationError("FINAL_URL_NOT_ALLOWLISTED")
            sha256, byte_count = read_body(response)
            headers = response.headers
            baseline = source.get("baseline_sha256")
            if baseline is None:
                change_status = "BASELINE_NOT_ESTABLISHED"
            elif sha256 != baseline:
                change_status = "CONTENT_CHANGED"
            elif (
                (source.get("baseline_etag") is not None and headers.get("ETag") != source.get("baseline_etag"))
                or (source.get("baseline_last_modified") is not None
                    and headers.get("Last-Modified") != source.get("baseline_last_modified"))
            ):
                change_status = "METADATA_CHANGED"
            else:
                change_status = "UNCHANGED"
            return {
                **common,
                "observation_status": "RETRIEVED",
                "change_status": change_status,
                "http_status": status,
                "final_url": final_url,
                "content_type": headers.get("Content-Type"),
                "content_length_header": headers.get("Content-Length"),
                "bytes_received": byte_count,
                "sha256": sha256,
                "baseline_sha256": baseline,
                "etag": headers.get("ETag"),
                "last_modified": headers.get("Last-Modified"),
                "source_version_hint": headers.get("Last-Modified") or headers.get("ETag"),
                "redistribution_status": source.get("redistribution_status", "NOT_ASSESSED"),
                "retention_status": source.get("retention_status", "NOT_ASSESSED"),
            }
    except HTTPError as exc:
        return {
            **common, "observation_status": "SOURCE_UNAVAILABLE",
            "change_status": "REVIEW_REQUIRED", "http_status": exc.code,
            "error_class": "HTTP_ERROR",
            "baseline_sha256": source.get("baseline_sha256"),
        }
    except URLError as exc:
        return {
            **common, "observation_status": "SOURCE_UNAVAILABLE",
            "change_status": "REVIEW_REQUIRED", "http_status": None,
            "error_class": "NETWORK_ERROR",
            "baseline_sha256": source.get("baseline_sha256"),
        }


def write_observation(record, output_dir):
    output_dir = Path(output_dir).expanduser().resolve()
    repository_root = ROOT.resolve()
    if output_dir == repository_root or repository_root in output_dir.parents:
        raise ObservationError("OBSERVATION_OUTPUT_INSIDE_REPOSITORY")
    output_dir.mkdir(parents=True, exist_ok=True)
    timestamp = re.sub(r"[^0-9TZ]", "-", record["observed_at_utc"])
    path = output_dir / f'{record["document_id"]}__{timestamp}.json'
    data = (json.dumps(record, ensure_ascii=False, indent=2, sort_keys=True) + "\n").encode("utf-8")
    fd, temporary = tempfile.mkstemp(prefix=".iwfi-observation-", suffix=".tmp", dir=str(output_dir))
    try:
        with os.fdopen(fd, "wb") as stream:
            stream.write(data)
            stream.flush()
            os.fsync(stream.fileno())
        os.link(temporary, path)
    except FileExistsError as exc:
        raise ObservationError("OBSERVATION_ALREADY_EXISTS") from exc
    finally:
        try:
            os.unlink(temporary)
        except FileNotFoundError:
            pass
    return path

def run_observations(registry_path, output_dir, source_ids=None, opener_factory=None, observed_at=None):
    registry = load_registry(registry_path)
    selected = source_ids or list(registry)
    if len(selected) != len(set(selected)):
        raise ObservationError("DUPLICATE_SOURCE_ID")
    if any(source_id not in registry for source_id in selected):
        raise ObservationError("SOURCE_ID_NOT_REGISTERED")
    results = []
    for source_id in selected:
        source = registry[source_id]
        opener = opener_factory(source) if opener_factory else None
        record = observe_source(source, opener=opener, observed_at=observed_at)
        path = write_observation(record, output_dir)
        results.append({"path": str(path), "record": record})
    return results


def main(argv=None):
    parser = argparse.ArgumentParser(description="Explicitly observe registered policy sources.")
    parser.add_argument("--registry", default=str(DEFAULT_REGISTRY))
    parser.add_argument("--output-dir", required=True)
    parser.add_argument("--source-id", action="append", dest="source_ids")
    args = parser.parse_args(argv)
    try:
        results = run_observations(args.registry, args.output_dir, args.source_ids)
    except (ObservationError, OSError, ValueError) as exc:
        parser.exit(2, f"observation rejected: {exc}\n")
    print(json.dumps([{
        "document_id": item["record"]["document_id"],
        "observation_status": item["record"]["observation_status"],
        "change_status": item["record"]["change_status"],
        "sha256": item["record"].get("sha256"),
        "path": item["path"],
    } for item in results], ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
