#!/usr/bin/env python3
"""
Repack PocketNES menu .gba using tools/pocketnes_packer/pocketnes-pack.exe (MSYS2 MinGW64).
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
    ap = argparse.ArgumentParser(prog="pocketnes_repack.py")
    ap.add_argument("--repo-root", default=str(Path(__file__).resolve().parents[2]))
    ap.add_argument("--msys2-shell", default=r"C:\msys64\msys2_shell.cmd")
    ap.add_argument("--build-packer", action=argparse.BooleanOptionalAction, default=True)
    ap.add_argument("--rom", default=r"C:\Users\benedict\Documents\GitHub\PocketNES\tools\pocketnes_packer\mtpo.nes")
    ap.add_argument("--emu-gba", default=r"C:\Users\benedict\Documents\GitHub\PocketNES\pocketnes.gba")
    ap.add_argument("--out-gba", default=r"C:\Users\benedict\Documents\GitHub\PocketNES\PocketNESMenu.gba")
    args = ap.parse_args(argv)

    repo_root = require_path(Path(args.repo_root), "RepoRoot")
    msys2_shell = require_path(Path(args.msys2_shell), "msys2_shell.cmd")

    rom = require_path(Path(args.rom), "ROM")
    emu_gba = Path(args.emu_gba).resolve()
    out_gba = Path(args.out_gba).resolve()

    packer_dir = repo_root / "tools" / "pocketnes_packer"
    packer_dir_m = to_msys_path(packer_dir)
    rom_m = to_msys_path(rom)
    emu_m = to_msys_path(emu_gba)
    out_m = to_msys_path(out_gba)

    if args.build_packer:
        print("Building packer in MSYS2 MinGW64...")
        rc = run_msys2(msys2_shell, f"cd '{packer_dir_m}' && make")
        if rc != 0:
            raise SystemExit(rc)

    print("Running PocketNES packer...")
    cmd = f"cd '{packer_dir_m}' && ./pocketnes-pack.exe --emu '{emu_m}' --out '{out_m}' --rom '{rom_m}'"
    rc = run_msys2(msys2_shell, cmd)
    if rc != 0:
        raise SystemExit(rc)

    print("OK")
    print(f"Packed: {out_gba}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))

