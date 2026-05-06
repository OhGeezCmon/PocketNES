# PocketNES automated GDB capture (mGBA)

See `tools/README.md` for canonical commands.

Important behavior note:

- When mGBA is launched with `-g`, it will typically **wait for GDB** before emulation (audio/video) begins.
- This harness works around that by doing a fast first attach that issues **`continue` + `detach`** so emulation starts immediately, then it waits a bit and re-attaches to **interrupt + dump** state.

## Notes

Runs are written to:

- `tools/debug/runs/<runId>/gdb_out.txt`
- `tools/debug/runs/<runId>/mgba_stdout.txt`
- `tools/debug/runs/<runId>/mgba_stderr.txt`
- `tools/debug/runs/<runId>/summary.json`
- `tools/debug/runs/<runId>/summary.md`

## Parsing an existing run folder

Use `python tools/debug/pocketnes_parse_run.py --run-dir tools/debug/runs/<runId>`.

