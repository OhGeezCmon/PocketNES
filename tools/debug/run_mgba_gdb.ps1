param(
  [string]$MgbaExe = "X:\games\emu\gba\mGBA-0.10.5-win32\mGBA.exe",
  [string]$Rom = "C:\Users\benedict\Documents\GitHub\PocketNES\PocketNESMenu.gba",
  [string]$Elf = "C:\Users\benedict\Documents\GitHub\PocketNES\pocketnes.elf",
  [string]$GdbExe = "",
  [string]$Msys2Shell = "C:\msys64\msys2_shell.cmd",
  [int]$Port = 2345,
  [int]$MaxAttempts = 2,
  [int]$AttemptDelayMs = 1000,
  [int]$InitialDelaySeconds = 1,
  [int]$CaptureDelaySeconds = 5,
  [switch]$KillExistingMgba,
  [switch]$NoWindow
)

$ErrorActionPreference = "Stop"

function Require-File([string]$Path, [string]$Name) {
  if (-not (Test-Path -LiteralPath $Path)) { throw "$Name not found: $Path" }
  return (Resolve-Path -LiteralPath $Path).Path
}

function Resolve-Gdb([string]$ExplicitPath) {
  if ($ExplicitPath) {
    return Require-File $ExplicitPath "GDB executable"
  }

  # Prefer devkitARM's arm-none-eabi-gdb first. In practice this has been the
  # most reliable with mGBA's GDB stub for this project.
  if ($env:DEVKITARM) {
    $p = Join-Path $env:DEVKITARM "bin\arm-none-eabi-gdb.exe"
    if (Test-Path -LiteralPath $p) { return (Resolve-Path -LiteralPath $p).Path }
  }
  $devkitGdb = "C:\msys64\opt\devkitpro\devkitARM\bin\arm-none-eabi-gdb.exe"
  if (Test-Path -LiteralPath $devkitGdb) { return (Resolve-Path -LiteralPath $devkitGdb).Path }

  $candidates = @(
    "C:\msys64\mingw64\bin\gdb-multiarch.exe",
    "C:\msys64\usr\bin\gdb-multiarch.exe",
    "C:\msys64\opt\devkitpro\devkitARM\bin\arm-none-eabi-gdb.exe"
  )

  foreach ($p in $candidates) {
    if (Test-Path -LiteralPath $p) { return (Resolve-Path -LiteralPath $p).Path }
  }

  throw "Could not find a GDB executable. Install gdb-multiarch (preferred) or devkitARM GDB, or pass -GdbExe."
}

function To-MsysPath([string]$WindowsPath) {
  # Convert e.g. C:\Foo\Bar -> /c/Foo/Bar (sufficient for standard absolute paths)
  $p = $WindowsPath.Replace('\','/')
  if ($p -match '^(?<drive>[A-Za-z]):/(?<rest>.*)$') {
    $d = $Matches['drive'].ToLower()
    $r = $Matches['rest']
    return "/$d/$r"
  }
  return $p
}

$mgba = Require-File $MgbaExe "mGBA executable"
$rom = Require-File $Rom "ROM"
$elf = Require-File $Elf "ELF"
$gdb = Resolve-Gdb $GdbExe
$msys2Shell = Require-File $Msys2Shell "msys2_shell.cmd"

$logsDir = Join-Path $PSScriptRoot "logs"
New-Item -ItemType Directory -Force -Path $logsDir | Out-Null

$ts = Get-Date -Format "yyyyMMdd_HHmmss"
$gdbCmdStart = Join-Path $logsDir "gdb_cmd_start_$ts.gdb"
$gdbCmdDump = Join-Path $logsDir "gdb_cmd_dump_$ts.gdb"
$gdbLog = Join-Path $logsDir "gdb_out_$ts.txt"

# 2-phase approach:
# 1) Attach immediately, "continue", detach => emulation starts right away (audio/video).
# 2) Wait a bit, then re-attach, interrupt, dump state, detach.
@"
set pagination off
set confirm off
set remote noack-packet off
handle SIGILL nostop noprint pass
set remote memory-map-packet off
set remote library-info-packet off
set remote trace-status-packet off
set remote traceframe-info-packet off
set remote static-tracepoints-packet off
set remote fast-tracepoints-packet off
set remote install-in-trace-packet off
set remote conditional-tracepoints-packet off
target remote localhost:$Port
continue
disconnect
quit
"@ | Set-Content -LiteralPath $gdbCmdStart -Encoding ASCII

@"
set pagination off
set confirm off
set remote noack-packet off
handle SIGILL nostop noprint pass
set remote memory-map-packet off
set remote library-info-packet off
set remote trace-status-packet off
set remote traceframe-info-packet off
set remote static-tracepoints-packet off
set remote fast-tracepoints-packet off
set remote install-in-trace-packet off
set remote conditional-tracepoints-packet off
target remote localhost:$Port
interrupt
info reg pc sp lr cpsr
x/24i `$pc
disconnect
quit
"@ | Set-Content -LiteralPath $gdbCmdDump -Encoding ASCII

if ($KillExistingMgba) {
  Get-Process -ErrorAction SilentlyContinue | Where-Object {
    $_.Path -and ((Split-Path -Leaf $_.Path) -ieq "mGBA.exe")
  } | ForEach-Object { try { $_.Kill() } catch {} }
  Start-Sleep -Milliseconds 300
}

$proc = $null
try {
  $wd = Split-Path -Parent $rom
  if ($NoWindow) {
    $proc = Start-Process -PassThru -WorkingDirectory $wd -FilePath $mgba -ArgumentList @("-g", $rom) -WindowStyle Hidden
  } else {
    $proc = Start-Process -PassThru -WorkingDirectory $wd -FilePath $mgba -ArgumentList @("-g", $rom)
  }

  "=== run_mgba_gdb.ps1 prelude ===`nMGBA: $mgba`nPORT: $Port`nELF: $elf`nROM: $rom`nPID: $($proc.Id)`n" |
    Set-Content -LiteralPath $gdbLog -Encoding utf8
  Add-Content -LiteralPath $gdbLog -Encoding utf8 -Value ("GDB: " + $gdb + "`n")
  Add-Content -LiteralPath $gdbLog -Encoding utf8 -Value ("MSYS2: " + $msys2Shell + "`n")
  Add-Content -LiteralPath $gdbLog -Encoding utf8 -Value ("InitialDelaySeconds: " + $InitialDelaySeconds + "`n")
  Add-Content -LiteralPath $gdbLog -Encoding utf8 -Value ("CaptureDelaySeconds: " + $CaptureDelaySeconds + "`n")

  Start-Sleep -Seconds $InitialDelaySeconds

  $prevEap = $ErrorActionPreference
  $ErrorActionPreference = "Continue"
  $gdbExit = 1

  for ($attempt = 1; $attempt -le $MaxAttempts; $attempt++) {
    Add-Content -LiteralPath $gdbLog -Encoding utf8 -Value "`n=== gdb START attempt $attempt/$MaxAttempts ===`n"

    # Run GDB inside MSYS2 MinGW64 to match the user's known-good environment.
    # Convert paths to MSYS form (avoid requiring cygpath in the host PowerShell session).
    $gdbM = To-MsysPath $gdb
    $elfM = To-MsysPath $elf
    $cmdStartM = To-MsysPath $gdbCmdStart
    $msysCmd = "exec '$gdbM' -q '$elfM' -batch -x '$cmdStartM'"

    & $msys2Shell -mingw64 -defterm -no-start -here -c $msysCmd 2>&1 | Out-File -FilePath $gdbLog -Append -Encoding utf8
    $gdbExit = $LASTEXITCODE
    if ($gdbExit -eq 0) { break }
    Start-Sleep -Milliseconds $AttemptDelayMs
  }

  if ($gdbExit -ne 0) {
    $ErrorActionPreference = $prevEap
    Add-Content -LiteralPath $gdbLog -Encoding utf8 -Value "`n=== run_mgba_gdb.ps1 ===`nSTART_PHASE_GDB_EXIT: $gdbExit`nRESULT: FAIL`n"
    Write-Host "Wrote GDB log: $gdbLog"
    Write-Host "Wrote GDB cmd start: $gdbCmdStart"
    Write-Host "Wrote GDB cmd dump: $gdbCmdDump"
    exit $gdbExit
  }

  Start-Sleep -Seconds $CaptureDelaySeconds

  $gdbExitDump = 1
  for ($attempt = 1; $attempt -le $MaxAttempts; $attempt++) {
    Add-Content -LiteralPath $gdbLog -Encoding utf8 -Value "`n=== gdb DUMP attempt $attempt/$MaxAttempts ===`n"

    $gdbM = To-MsysPath $gdb
    $elfM = To-MsysPath $elf
    $cmdDumpM = To-MsysPath $gdbCmdDump
    $msysCmd = "exec '$gdbM' -q '$elfM' -batch -x '$cmdDumpM'"

    & $msys2Shell -mingw64 -defterm -no-start -here -c $msysCmd 2>&1 | Out-File -FilePath $gdbLog -Append -Encoding utf8
    $gdbExitDump = $LASTEXITCODE
    if ($gdbExitDump -eq 0) { break }
    Start-Sleep -Milliseconds $AttemptDelayMs
  }

  $ErrorActionPreference = $prevEap
  $result = if ($gdbExitDump -eq 0) { "OK" } else { "FAIL" }
  Add-Content -LiteralPath $gdbLog -Encoding utf8 -Value "`n=== run_mgba_gdb.ps1 ===`nSTART_PHASE_GDB_EXIT: 0`nDUMP_PHASE_GDB_EXIT: $gdbExitDump`nRESULT: $result`n"

  Write-Host "Wrote GDB log: $gdbLog"
  Write-Host "Wrote GDB cmd start: $gdbCmdStart"
  Write-Host "Wrote GDB cmd dump: $gdbCmdDump"
  if ($gdbExitDump -ne 0) { exit $gdbExitDump }
} finally {
  if ($proc -and -not $proc.HasExited) {
    try { $proc.Kill() | Out-Null } catch {}
    try { $proc.WaitForExit(3000) | Out-Null } catch {}
  }
}

