#!/usr/bin/env python3
"""Publish the PC host directly beside the prepared loose game files."""

from __future__ import annotations

import argparse
import shutil
import subprocess
import tempfile
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

    with tempfile.TemporaryDirectory(prefix="demolition-single-file-") as temp:
        staging = Path(temp)
        subprocess.run(
            [
                "dotnet",
                "publish",
                str(PROJECT),
                "-c",
                "Release",
                "-r",
                "win-x64",
                "--self-contained",
                "true",
                "-p:PublishSingleFile=true",
                "-p:IncludeNativeLibrariesForSelfExtract=true",
                "-p:IncludeAllContentForSelfExtract=true",
                "-p:EnableCompressionInSingleFile=true",
                "-p:DebugSymbols=false",
                "-p:DebugType=None",
                "-o",
                str(staging),
                "--consoleLoggerParameters:ErrorsOnly",
            ],
            cwd=REPO,
            check=True,
        )

        staged_executable = staging / "StarWarsDemolitionPC.exe"
        unexpected = [path.name for path in staging.iterdir()
                      if path.is_file() and path != staged_executable]
        if not staged_executable.is_file() or unexpected:
            raise RuntimeError(
                "single-file publish contract failed; "
                f"exe={staged_executable.is_file()} unexpected={unexpected}"
            )

        # A successful staged publish is the commit point. Remove only legacy
        # host products from earlier framework-dependent publishes; prepared
        # retail media and user configuration are never part of this cleanup.
        for legacy in loose_root.glob("*.dll"):
            legacy.unlink()
        for suffix in (".deps.json", ".runtimeconfig.json", ".pdb"):
            for legacy in loose_root.glob(f"StarWarsDemolitionPC*{suffix}"):
                legacy.unlink()
        (loose_root / "RecompOne.Runtime.pdb").unlink(missing_ok=True)
        shutil.copy2(staged_executable, loose_root / staged_executable.name)

    executable = loose_root / "StarWarsDemolitionPC.exe"
    if not executable.is_file():
        raise RuntimeError(f"publish completed without producing {executable}")
    print(f"Published self-contained loose-file build: {executable}")
    print("Run it with no arguments; it reads SYSTEM.CNF and all media beside itself.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
