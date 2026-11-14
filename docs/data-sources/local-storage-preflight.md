# Local storage preflight

Run `inspect_storage_root(path)` on an already existing candidate directory before considering local acquisition. The utility is read-only and reports total, used, and free bytes from the operating system, plus obvious sync-provider path markers, known sync-related environment variables, and Windows reparse-point ancestors.

It deliberately returns `sync_verification=NOT_VERIFIED` even when no heuristic risk is detected. Directory names and environment variables cannot prove the absence of OneDrive, Dropbox, Google Drive, iCloud, Box, backup clients, junctions, or other sync software. The operator must inspect Windows account/app settings and verify the selected folder manually.

The report always sets `capture_authorized=false`. It does not create directories, apply arbitrary free-space thresholds, write files, disable sync, or activate data capture. No external services or costs are used.


## Windows command

From the repository root in PowerShell, after Python 3.12 is installed:

```powershell
python -m iwfi.local_storage_preflight --path "$HOME\\Documents\\IWFI-Local"
```

Replace the example directory with an existing folder you have manually checked. The command only inspects; it does not create the folder, write a report file, disable sync, or authorize downloads. It prints JSON to the terminal. A clean heuristic result is still NOT_VERIFIED and must be followed by manual review of Windows sync/backup settings.
