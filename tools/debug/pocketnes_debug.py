#!/usr/bin/env python3
"""
Deterministic mGBA + GDB harness for PocketNES.

Creates a per-run folder under `tools/debug/runs/<runId>/` with logs and parsed summaries.
"""

from __future__ import annotations

import argparse
import datetime as _dt
import json
import os
import re
import socket
import subprocess
import sys
import time
import uuid
from pathlib import Path


def eprint(*args: object, **kwargs: object) -> None:
    print(*args, file=sys.stderr, **kwargs)


def now_utc() -> _dt.datetime:
    return _dt.datetime.now(tz=_dt.timezone.utc)


def new_run_id() -> str:
    ts = _dt.datetime.now().strftime("%Y%m%d_%H%M%S")
    return f"{ts}_{uuid.uuid4().hex[:8]}"


def require_path(p: Path, name: str) -> Path:
    if not p.exists():
        raise SystemExit(f"{name} not found: {p}")
    return p.resolve()


def to_msys_path(win_path: Path) -> str:
    p = str(win_path.resolve()).replace("\\", "/")
    m = re.match(r"^([A-Za-z]):/(.*)$", p)
    if m:
        return f"/{m.group(1).lower()}/{m.group(2)}"
    return p


def wait_for_port(port: int, timeout_s: int) -> bool:
    deadline = time.time() + max(1, timeout_s)
    while time.time() < deadline:
        try:
            with socket.create_connection(("127.0.0.1", port), timeout=0.2):
                return True
        except OSError:
            time.sleep(0.2)
    return False


def run_cmd(argv: list[str], *, check: bool = True) -> subprocess.CompletedProcess[str]:
    cp = subprocess.run(argv, text=True, capture_output=True)
    if check and cp.returncode != 0:
        if cp.stdout:
            eprint(cp.stdout)
        if cp.stderr:
            eprint(cp.stderr)
        raise SystemExit(f"Command failed ({cp.returncode}): {' '.join(argv)}")
    return cp


def resolve_gdb(gdb_exe: str | None) -> Path:
    if gdb_exe:
        return require_path(Path(gdb_exe), "GDB executable")

    devkitarm = os.environ.get("DEVKITARM")
    if devkitarm:
        cand = Path(devkitarm) / "bin" / "arm-none-eabi-gdb.exe"
        if cand.exists():
            return cand.resolve()

    candidates = [
        Path(r"C:\msys64\opt\devkitpro\devkitARM\bin\arm-none-eabi-gdb.exe"),
        Path(r"C:\msys64\mingw64\bin\gdb-multiarch.exe"),
        Path(r"C:\msys64\usr\bin\gdb-multiarch.exe"),
    ]
    for c in candidates:
        if c.exists():
            return c.resolve()

    raise SystemExit(
        "Could not find a GDB executable. Install devkitARM GDB or gdb-multiarch, or pass --gdb-exe."
    )


def find_processes_by_exe_name(exe_name: str) -> list[int]:
    try:
        cp = run_cmd(["tasklist", "/FI", f"IMAGENAME eq {exe_name}"], check=False)
    except Exception:
        return []

    pids: list[int] = []
    for line in (cp.stdout or "").splitlines():
        if not line.lower().startswith(exe_name.lower()):
            continue
        cols = [c for c in line.split(" ") if c]
        if len(cols) >= 2 and cols[1].isdigit():
            pids.append(int(cols[1]))
    return pids


def kill_pids(pids: list[int]) -> None:
    for pid in pids:
        run_cmd(["taskkill", "/PID", str(pid), "/T", "/F"], check=False)


def write_gdb_cmd_files(run_dir: Path, port: int) -> tuple[Path, Path]:
    gdb_cmd_start = run_dir / "gdb_cmd_start.gdb"
    gdb_cmd_dump = run_dir / "gdb_cmd_dump.gdb"

    start_txt = "\n".join(
        [
            "set pagination off",
            "set confirm off",
            "set remotetimeout 3",
            "set debug remote 0",
            "set remote noack-packet off",
            "handle SIGILL nostop noprint nopass",
            "set remote memory-map-packet off",
            "set remote library-info-packet off",
            "set remote trace-status-packet off",
            "set remote traceframe-info-packet off",
            "set remote static-tracepoints-packet off",
            "set remote fast-tracepoints-packet off",
            "set remote install-in-trace-packet off",
            "set remote conditional-tracepoints-packet off",
            f"target remote localhost:{port}",
            "info reg pc sp lr cpsr",
            "continue",
            "disconnect",
            "quit",
            "",
        ]
    )
    dump_txt = "\n".join(
        [
            "set pagination off",
            "set confirm off",
            "set remotetimeout 3",
            "set debug remote 0",
            "set remote noack-packet off",
            "handle SIGILL nostop noprint nopass",
            "set remote memory-map-packet off",
            "set remote library-info-packet off",
            "set remote trace-status-packet off",
            "set remote traceframe-info-packet off",
            "set remote static-tracepoints-packet off",
            "set remote fast-tracepoints-packet off",
            "set remote install-in-trace-packet off",
            "set remote conditional-tracepoints-packet off",
            f"target remote localhost:{port}",
            "interrupt",
            "info reg",
            "bt",
            r"echo \n--- disasm @pc ---\n",
            r"x/24i $pc",
            r"echo \n--- disasm @lr ---\n",
            r"x/24i $lr",
            "disconnect",
            "quit",
            "",
        ]
    )
    gdb_cmd_start.write_text(start_txt, encoding="ascii")
    gdb_cmd_dump.write_text(dump_txt, encoding="ascii")
    return gdb_cmd_start, gdb_cmd_dump


def run_msys2_gdb_batch(
    msys2_shell: Path,
    gdb_exe: Path,
    elf: Path,
    cmd_file: Path,
    out_file: Path,
    *,
    max_attempts: int,
    attempt_delay_ms: int,
) -> int:
    gdb_m = to_msys_path(gdb_exe)
    elf_m = to_msys_path(elf)
    cmd_m = to_msys_path(cmd_file)
    msys_cmd = f"exec '{gdb_m}' -q '{elf_m}' -batch -x '{cmd_m}'"

    last = 1
    with out_file.open("a", encoding="utf-8") as f:
        for attempt in range(1, max_attempts + 1):
            f.write(f"\n=== gdb attempt {attempt}/{max_attempts} ({cmd_file.name}) ===\n")
            cp = run_cmd(
                [
                    str(msys2_shell),
                    "-mingw64",
                    "-defterm",
                    "-no-start",
                    "-here",
                    "-c",
                    msys_cmd,
                ],
                check=False,
            )
            f.write(cp.stdout or "")
            f.write(cp.stderr or "")
            last = cp.returncode
            if last == 0:
                return 0
            time.sleep(max(0.0, attempt_delay_ms / 1000.0))
    return last


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser(prog="pocketnes_debug.py")
    ap.add_argument("--repo-root", default=str(Path(__file__).resolve().parents[2]))
    ap.add_argument("--runs-dir", default="")
    ap.add_argument("--run-id", default="")
    ap.add_argument("--mgba-exe", default=r"X:\games\emu\gba\mGBA-0.10.5-win32\mGBA.exe")
    ap.add_argument("--rom", default=r"C:\Users\benedict\Documents\GitHub\PocketNES\PocketNESMenu.gba")
    ap.add_argument("--elf", default=r"C:\Users\benedict\Documents\GitHub\PocketNES\pocketnes.elf")
    ap.add_argument("--gdb-exe", default="")
    ap.add_argument("--msys2-shell", default=r"C:\msys64\msys2_shell.cmd")
    ap.add_argument("--port", type=int, default=2345)
    ap.add_argument("--initial-delay-seconds", type=int, default=2)
    ap.add_argument("--capture-delay-seconds", type=int, default=5)
    ap.add_argument("--port-timeout-seconds", type=int, default=30)
    ap.add_argument("--max-attempts", type=int, default=4)
    ap.add_argument("--attempt-delay-ms", type=int, default=750)
    ap.add_argument("--kill-existing-mgba", action="store_true")
    ap.add_argument("--no-window", action="store_true")
    args = ap.parse_args(argv)

    repo_root = Path(args.repo_root).resolve()
    runs_dir = Path(args.runs_dir).resolve() if args.runs_dir else (repo_root / "tools" / "debug" / "runs")
    run_id = args.run_id or new_run_id()
    run_dir = runs_dir / run_id
    run_dir.mkdir(parents=True, exist_ok=True)

    mgba_exe = require_path(Path(args.mgba_exe), "mGBA executable")
    rom = require_path(Path(args.rom), "ROM")
    elf = require_path(Path(args.elf), "ELF")
    msys2_shell = require_path(Path(args.msys2_shell), "msys2_shell.cmd")
    gdb_exe = resolve_gdb(args.gdb_exe)

    if args.kill_existing_mgba:
        kill_pids(find_processes_by_exe_name("mGBA.exe"))
        time.sleep(0.3)
    else:
        existing = find_processes_by_exe_name("mGBA.exe")
        if existing:
            raise SystemExit(f"mGBA.exe already running ({len(existing)} processes). Re-run with --kill-existing-mgba.")

    started_utc = now_utc().isoformat()
    meta = {
        "runId": run_id,
        "startedUtc": started_utc,
        "mgbaExe": str(mgba_exe),
        "rom": str(rom),
        "elf": str(elf),
        "gdbExe": str(gdb_exe),
        "msys2Shell": str(msys2_shell),
        "port": args.port,
        "initialDelaySeconds": args.initial_delay_seconds,
        "captureDelaySeconds": args.capture_delay_seconds,
        "portTimeoutSeconds": args.port_timeout_seconds,
        "maxAttempts": args.max_attempts,
        "attemptDelayMs": args.attempt_delay_ms,
    }
    (run_dir / "meta.json").write_text(json.dumps(meta, indent=2), encoding="utf-8")

    mgba_stdout = run_dir / "mgba_stdout.txt"
    mgba_stderr = run_dir / "mgba_stderr.txt"
    gdb_out = run_dir / "gdb_out.txt"

    gdb_cmd_start, gdb_cmd_dump = write_gdb_cmd_files(run_dir, args.port)
    gdb_out.write_text(
        f"=== pocketnes_debug.py ===\nRUN_DIR: {run_dir}\nSTARTED_UTC: {started_utc}\n",
        encoding="utf-8",
    )

    mgba_proc = subprocess.Popen(
        [str(mgba_exe), "-g", str(rom)],
        cwd=str(rom.parent),
        stdout=mgba_stdout.open("w", encoding="utf-8", errors="replace"),
        stderr=mgba_stderr.open("w", encoding="utf-8", errors="replace"),
        creationflags=(0x08000000 if args.no_window else 0),  # CREATE_NO_WINDOW
    )
    with gdb_out.open("a", encoding="utf-8") as f:
        f.write(f"MGBA_PID: {mgba_proc.pid}\n")

    gdb_start_exit: int | None = None
    gdb_dump_exit: int | None = None
    port_ready = False

    try:
        time.sleep(max(0, args.initial_delay_seconds))
        port_ready = wait_for_port(args.port, args.port_timeout_seconds)
        with gdb_out.open("a", encoding="utf-8") as f:
            f.write(f"PORT_READY: {str(port_ready).lower()}\n")

        gdb_start_exit = run_msys2_gdb_batch(
            msys2_shell,
            gdb_exe,
            elf,
            gdb_cmd_start,
            gdb_out,
            max_attempts=args.max_attempts,
            attempt_delay_ms=args.attempt_delay_ms,
        )
        with gdb_out.open("a", encoding="utf-8") as f:
            f.write(f"\nGDB_START_EXIT: {gdb_start_exit}\n")

        time.sleep(max(0, args.capture_delay_seconds))
        gdb_dump_exit = run_msys2_gdb_batch(
            msys2_shell,
            gdb_exe,
            elf,
            gdb_cmd_dump,
            gdb_out,
            max_attempts=args.max_attempts,
            attempt_delay_ms=args.attempt_delay_ms,
        )
        with gdb_out.open("a", encoding="utf-8") as f:
            f.write(f"\nGDB_DUMP_EXIT: {gdb_dump_exit}\n")
    finally:
        try:
            mgba_proc.terminate()
        except Exception:
            pass
        try:
            mgba_proc.wait(timeout=3)
        except Exception:
            try:
                mgba_proc.kill()
            except Exception:
                pass

    # Parse after capture (delegates to parse script)
    parse_script = repo_root / "tools" / "debug" / "pocketnes_parse_run.py"
    cp = subprocess.run([sys.executable, str(parse_script), "--run-dir", str(run_dir)], text=True)
    if cp.returncode != 0:
        eprint("WARN: parse step failed")

    print(f"Run folder: {run_dir}")
    if gdb_start_exit != 0 or gdb_dump_exit != 0:
        return 10
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))

