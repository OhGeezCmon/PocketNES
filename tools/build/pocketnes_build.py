#!/usr/bin/env python3
"""
Build PocketNES (MSYS2 MinGW64).
"""

from __future__ import annotations

import argparse
import re
import subprocess
import sys
from pathlib import Path


def eprint(*args: object, **kwargs: object) -> None:
    print(*args, file=sys.stderr, **kwargs)


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


def run_cmd(argv: list[str]) -> int:
    cp = subprocess.run(argv, text=True, capture_output=True)
    if cp.stdout:
        print(cp.stdout, end="")
    if cp.stderr:
        eprint(cp.stderr, end="")
    return cp.returncode


def run_msys2(msys2_shell: Path, bash_cmd: str) -> int:
    return run_cmd([str(msys2_shell), "-mingw64", "-defterm", "-no-start", "-here", "-c", bash_cmd])


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser(prog="pocketnes_build.py")
    ap.add_argument("--repo-root", default=str(Path(__file__).resolve().parents[2]))
    ap.add_argument("--msys2-shell", default=r"C:\msys64\msys2_shell.cmd")
    ap.add_argument("--clean", action="store_true")
    args = ap.parse_args(argv)

    repo_root = require_path(Path(args.repo_root), "RepoRoot")
    msys2_shell = require_path(Path(args.msys2_shell), "msys2_shell.cmd")

    repo_m = to_msys_path(repo_root)
    parts: list[str] = []
    if args.clean:
        parts.append(f"cd '{repo_m}' && make clean")
    parts.append(f"cd '{repo_m}' && make")
    cmd = " && ".join(parts)

    print("Running build in MSYS2 MinGW64...")
    rc = run_msys2(msys2_shell, cmd)
    if rc != 0:
        raise SystemExit(rc)
    print("OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))

