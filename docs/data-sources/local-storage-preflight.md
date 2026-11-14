# Local storage preflight

Run `inspect_storage_root(path)` on an already existing candidate directory before considering local acquisition. The utility is read-only and reports total, used, and free bytes from the operating system, plus obvious sync-provider path markers, known sync-related environment variables, and Windows reparse-point ancestors.

It deliberately returns `sync_verification=NOT_VERIFIED` even when no heuristic risk is detected. Directory names and environment variables cannot prove the absence of OneDrive, Dropbox, Google Drive, iCloud, Box, backup clients, junctions, or other sync software. The operator must inspect Windows account/app settings and verify the selected folder manually.

The report always sets `capture_authorized=false`. It does not create directories, apply arbitrary free-space thresholds, write files, disable sync, or activate data capture. No external services or costs are used.
