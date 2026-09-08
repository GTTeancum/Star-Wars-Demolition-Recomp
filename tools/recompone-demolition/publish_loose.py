#!/usr/bin/env python3
"""Publish the PC host directly beside the prepared loose game files."""

from __future__ import annotations

import argparse
import subprocess
from pathlib import Path


REPO = Path(__file__).resolve().parents[2]
PROJECT = REPO / "reference" / "generated" / "StarWarsDemolitionPC.csproj"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--loose-root",
        type=Path,
        default=REPO / "game",
        help="prepared loose-file directory (default: game)",
    )
    args = parser.parse_args()

    loose_root = args.loose_root.resolve()
    if not (loose_root / "SYSTEM.CNF").is_file():
        parser.error(f"SYSTEM.CNF was not found in {loose_root}")
    if not PROJECT.is_file():
        parser.error(
            "generated project is missing; run prepare_reference.py and RecompOne first"
        )

    subprocess.run(
        [
            "dotnet",
            "publish",
            str(PROJECT),
            "-c",
            "Release",
            "--no-restore",
            "-o",
            str(loose_root),
            "--consoleLoggerParameters:ErrorsOnly",
        ],
        cwd=REPO,
        check=True,
    )
    executable = loose_root / "StarWarsDemolitionPC.exe"
    if not executable.is_file():
        raise RuntimeError(f"publish completed without producing {executable}")
    print(f"Published loose-file build: {executable}")
    print("Run it with no arguments; it reads SYSTEM.CNF and all media beside itself.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
