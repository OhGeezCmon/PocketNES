#!/usr/bin/env python3
"""
Parse a debug run folder and regenerate summary.json/summary.md.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path


def require_path(p: Path, name: str) -> Path:
    if not p.exists():
        raise SystemExit(f"{name} not found: {p}")
    return p.resolve()


def parse_run_dir(run_dir: Path) -> tuple[Path, Path]:
    run_dir = require_path(run_dir, "RunDir")
    run_id = run_dir.name
    gdb_out = run_dir / "gdb_out.txt"
    if not gdb_out.exists():
        raise SystemExit(f"gdb_out.txt not found in run dir: {run_dir}")

    text = gdb_out.read_text(encoding="utf-8", errors="replace")

    def m1(pat: str) -> str | None:
        m = re.search(pat, text, flags=re.MULTILINE)
        return m.group(1).strip() if m else None

    port_ready_s = m1(r"^PORT_READY:\s*(true|false)\s*$")
    gdb_start_exit_s = m1(r"^GDB_START_EXIT:\s*([0-9]+)\s*$")
    gdb_dump_exit_s = m1(r"^GDB_DUMP_EXIT:\s*([0-9]+)\s*$")

    pc = m1(r"^\s*pc\s+0x[0-9a-fA-F]+\s+(0x[0-9a-fA-F]+)") or m1(r"^\s*pc\s+(0x[0-9a-fA-F]+)")
    sp = m1(r"^\s*sp\s+(0x[0-9a-fA-F]+)")
    lr = m1(r"^\s*lr\s+(0x[0-9a-fA-F]+)")
    cpsr = m1(r"^\s*cpsr\s+(0x[0-9a-fA-F]+)")

    bt = None
    m = re.search(
        r"^\s*#0[\s\S]*?(?=^\s*detach\b|^\s*disconnect\b|^\s*--- disasm @pc ---|\Z)",
        text,
        flags=re.MULTILINE | re.IGNORECASE,
    )
    if m:
        bt = m.group(0).strip()

    summary_json = run_dir / "summary.json"
    summary_md = run_dir / "summary.md"

    summary_obj = {
        "runId": run_id,
        "runDir": str(run_dir),
        "portReady": (port_ready_s.lower() == "true") if port_ready_s else None,
        "gdbStartExit": int(gdb_start_exit_s) if gdb_start_exit_s else None,
        "gdbDumpExit": int(gdb_dump_exit_s) if gdb_dump_exit_s else None,
        "registers": {"pc": pc, "sp": sp, "lr": lr, "cpsr": cpsr},
        "backtrace": bt,
        "artifacts": {
            "gdbOut": str(gdb_out),
            "summaryJson": str(summary_json),
            "summaryMd": str(summary_md),
        },
    }
    summary_json.write_text(json.dumps(summary_obj, indent=2), encoding="utf-8")

    md_lines = [
        "# mGBA debug harness summary",
        "",
        f"- **RunId**: {run_id}",
        f"- **RunDir**: `{run_dir}`",
        f"- **PortReady**: {summary_obj['portReady']}",
        f"- **GdbStartExit**: {summary_obj['gdbStartExit']}",
        f"- **GdbDumpExit**: {summary_obj['gdbDumpExit']}",
        "",
        "## Registers",
        "",
        f"- **pc**: {pc}",
        f"- **sp**: {sp}",
        f"- **lr**: {lr}",
        f"- **cpsr**: {cpsr}",
        "",
        "## Backtrace (raw)",
        "",
        "```",
        bt or "<none parsed>",
        "```",
        "",
    ]
    summary_md.write_text("\n".join(md_lines), encoding="utf-8")

    return summary_json, summary_md


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser(prog="pocketnes_parse_run.py")
    ap.add_argument("--run-dir", required=True)
    args = ap.parse_args(argv)
    sj, sm = parse_run_dir(Path(args.run_dir))
    print(f"Wrote: {sj}")
    print(f"Wrote: {sm}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))

