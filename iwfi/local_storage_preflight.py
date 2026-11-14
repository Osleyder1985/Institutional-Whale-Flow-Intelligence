"""Read-only local storage preflight; never claims OS cloud-sync state is verified."""
import os
from pathlib import Path
import shutil

_SYNC_MARKERS = {
    "onedrive", "dropbox", "google drive", "googledrive", "googledrivefs",
    "icloud drive", "iclouddrive", "box",
}
_REPARSE_POINT = getattr(__import__("stat"), "FILE_ATTRIBUTE_REPARSE_POINT", 0x400)


def inspect_storage_root(path):
    """Measure capacity and report obvious sync/reparse risks without writing data."""
    root = Path(path).expanduser()
    if not root.exists() or not root.is_dir():
        raise ValueError("storage root must already exist and be a directory")
    if root.is_symlink():
        raise ValueError("storage root cannot be a symbolic link")

    resolved = root.resolve(strict=True)
    usage = shutil.disk_usage(resolved)
    components = {part.casefold() for part in resolved.parts}
    marker_hits = sorted(components & _SYNC_MARKERS)

    env_hits = []
    for key in ("OneDrive", "OneDriveCommercial", "OneDriveConsumer", "DROPBOX", "GOOGLE_DRIVE", "ICLOUD"):
        value = os.environ.get(key)
        if value:
            try:
                if resolved == Path(value).expanduser().resolve(strict=False) or Path(value).expanduser().resolve(strict=False) in resolved.parents:
                    env_hits.append(key)
            except OSError:
                continue

    reparse_paths = []
    for parent in (resolved, *resolved.parents):
        try:
            attributes = getattr(parent.stat(), "st_file_attributes", 0)
            if attributes & _REPARSE_POINT:
                reparse_paths.append(str(parent))
        except OSError:
            reparse_paths.append(str(parent))

    risks = []
    if marker_hits:
        risks.append("sync-provider directory marker(s): " + ", ".join(marker_hits))
    if env_hits:
        risks.append("sync-related environment variable(s): " + ", ".join(sorted(env_hits)))
    if reparse_paths:
        risks.append("reparse-point ancestor(s) require manual review: " + ", ".join(reparse_paths))

    return {
        "path": str(resolved),
        "total_bytes": usage.total,
        "used_bytes": usage.used,
        "free_bytes": usage.free,
        "sync_risk": "RISK_DETECTED" if risks else "NOT_DETECTED_BY_HEURISTICS",
        "sync_verification": "NOT_VERIFIED",
        "reparse_point_ancestors": reparse_paths,
        "risk_details": risks,
        "capture_authorized": False,
        "note": "This read-only preflight cannot prove that the OS, backup software, or another process will not sync this path.",
    }
