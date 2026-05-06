# PocketNES tools

Canonical entrypoints:

- `tools/build/pocketnes_build.py` (build)
- `tools/pack/pocketnes_repack.py` (repack)
- `tools/debug/pocketnes_debug.py` (debug harness)
- `tools/debug/pocketnes_parse_run.py` (parse-only)

## Debug harness (mGBA + GDB)

Run a deterministic capture (creates a new `tools/debug/runs/<runId>/` folder and writes `summary.json` / `summary.md`):

```bash
python tools/debug/pocketnes_debug.py --kill-existing-mgba --no-window
```

Parse an existing run folder:

```bash
python tools/debug/pocketnes_parse_run.py --run-dir tools/debug/runs/<runId>
```

## Build / repack

Rebuild PocketNES (`make` via MSYS2 MinGW64):

```bash
python tools/build/pocketnes_build.py --clean
```

Repack a menu `.gba` (optionally rebuilds the packer first):

```bash
python tools/pack/pocketnes_repack.py --rom tools/pocketnes_packer/mtpo.nes
```

Build + repack in one step:

```bash
python tools/build/pocketnes_build.py --clean
python tools/pack/pocketnes_repack.py --rom tools/pocketnes_packer/mtpo.nes
```

## Local-only wrappers

If you use `tools/local/*.bat`, those are meant to be machine-local and are ignored via `.git/info/exclude`.

