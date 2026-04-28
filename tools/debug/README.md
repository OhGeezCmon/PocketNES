# PocketNES automated GDB capture (mGBA)

This folder contains a **one-command** debug harness that:

- launches mGBA with its **GDB server enabled**
- connects `arm-none-eabi-gdb` to it
- dumps a small set of **PocketNES/MMC2-relevant state** to a timestamped log

Important behavior note:

- When mGBA is launched with `-g`, it will typically **wait for GDB** before emulation (audio/video) begins.
- This harness works around that by doing a fast first attach that issues **`continue` + `detach`** so emulation starts immediately, then it waits a bit and re-attaches to **interrupt + dump** state.

## Requirements

- mGBA 0.10.5 (or compatible) executable path
- `arm-none-eabi-gdb.exe` (from devkitARM) available via `DEVKITARM` or on `PATH`
- `arm-none-eabi-nm.exe` available (used to resolve symbol addresses from `pocketnes.elf`)

## Usage

From PowerShell:

```powershell
.\tools\debug\run_mgba_gdb.ps1
```

Common overrides:

```powershell
.\tools\debug\run_mgba_gdb.ps1 `
  -InitialDelaySeconds 1 `
  -CaptureDelaySeconds 5 `
  -MaxAttempts 10
```

Override mGBA path / ROM / ELF if needed:

```powershell
.\tools\debug\run_mgba_gdb.ps1 `
  -MgbaExe "X:\games\emu\gba\mGBA-0.10.5-win32\mgba-sdl.exe" `
  -Rom "C:\Users\benedict\Documents\GitHub\PocketNES\PocketNESMenu.gba" `
  -Elf "C:\Users\benedict\Documents\GitHub\PocketNES\pocketnes.elf"
```

Logs are written to:

- `tools/debug/logs/gdb_out_YYYYMMDD_HHMMSS.txt`

