#!/usr/bin/env python3
"""
Recursively detect truly empty leaf directories in a project (skipping .git
and hidden directories) and create 0-byte README.md placeholders for Git.
Provides full execution logs and pauses before exit so the terminal stays open.
"""

from __future__ import annotations

import os
import sys
import traceback
from dataclasses import dataclass
from pathlib import Path

PLACEHOLDER_FILENAME = "README.md"
FALLBACK_LEVELS_UP = 2  # Used when no .git marker is found upward


@dataclass
class ScanResult:
    scanned_dirs: int
    skipped_hidden_dirs: list[Path]
    empty_dirs: list[Path]


def detect_default_root() -> tuple[Path, str]:
    """
    Locate project root by searching upward for a .git folder/file.
    Falls back to FALLBACK_LEVELS_UP above the script's directory.
    """
    script_dir = Path(__file__).resolve().parent

    # Strategy 1: Search upward for .git (supports standard repos & worktrees)
    for candidate in (script_dir, *script_dir.parents):
        if (candidate / ".git").exists():
            return candidate, "detected via .git"

    # Strategy 2: Fallback to N levels above script directory
    parents = script_dir.parents
    if FALLBACK_LEVELS_UP <= 0:
        fallback_root = script_dir
    elif len(parents) >= FALLBACK_LEVELS_UP:
        fallback_root = parents[FALLBACK_LEVELS_UP - 1]
    else:
        fallback_root = parents[-1]

    return fallback_root, f"fallback ({FALLBACK_LEVELS_UP} levels above script)"


def prompt_project_root(default_root: Path, reason: str) -> Path:
    """Allow the user to specify a custom root path or press Enter for default."""
    script_path = Path(__file__).resolve()

    print("=" * 68)
    print(f"  Empty Folder Placeholder Tool ({PLACEHOLDER_FILENAME})")
    print("=" * 68)
    print(f"Script location : {script_path}")
    print(f"Default root    : {default_root}")
    print(f"Detection rule  : {reason}\n")

    while True:
        user_input = input(
            "Enter custom project root path (or press Enter to use default): "
        ).strip()

        if not user_input:
            print(f"\n[INFO] Using default project root: {default_root}")
            return default_root

        # Strip quotes in case a folder was dragged into the terminal
        cleaned_path = user_input.strip('"').strip("'")
        custom_root = Path(cleaned_path).expanduser().resolve()

        if custom_root.is_dir():
            print(f"\n[INFO] Using custom project root: {custom_root}")
            return custom_root

        print(f"[ERROR] Directory does not exist: {custom_root}")
        print("Please enter a valid directory path.\n")


def scan_project(root_dir: Path) -> ScanResult:
    """
    Scan the project for directories with zero files and zero subdirectories.
    Hidden directories (starting with '.') including .git are skipped.
    """
    scanned_dirs = 0
    skipped_hidden: list[Path] = []
    empty_dirs: list[Path] = []

    for current_root, dirnames, filenames in os.walk(root_dir, topdown=True):
        current_path = Path(current_root)
        scanned_dirs += 1

        # Evaluate emptiness BEFORE pruning hidden subdirectories
        if not dirnames and not filenames:
            empty_dirs.append(current_path)
            continue

        # Record and prune .git and all hidden directories
        visible_dirs: list[str] = []
        for d in dirnames:
            if d.startswith("."):
                skipped_hidden.append(current_path / d)
            else:
                visible_dirs.append(d)
        dirnames[:] = visible_dirs

    skipped_hidden.sort()
    empty_dirs.sort()

    return ScanResult(
        scanned_dirs=scanned_dirs,
        skipped_hidden_dirs=skipped_hidden,
        empty_dirs=empty_dirs,
    )


def create_placeholders(
    empty_dirs: list[Path], root_dir: Path
) -> tuple[list[Path], list[Path], list[tuple[Path, str]]]:
    """Create 0-byte README.md files in each target directory."""
    created: list[Path] = []
    skipped: list[Path] = []
    failed: list[tuple[Path, str]] = []

    print("[STEP 3/3] Creating placeholder files...")
    for folder in empty_dirs:
        target_file = folder / PLACEHOLDER_FILENAME
        rel_path = target_file.relative_to(root_dir)
        try:
            target_file.touch(exist_ok=False)
            print(f"  [CREATED] {rel_path}")
            created.append(rel_path)
        except FileExistsError:
            print(f"  [SKIPPED] {rel_path} (already exists)")
            skipped.append(rel_path)
        except OSError as exc:
            print(f"  [ERROR]   {rel_path} ({exc})")
            failed.append((rel_path, str(exc)))

    return created, skipped, failed


def print_summary(
    root_dir: Path,
    scan: ScanResult,
    status: str,
    created: int = 0,
    skipped: int = 0,
    failed: int = 0,
) -> None:
    """Print a complete execution summary report."""
    print("\n" + "=" * 68)
    print("  EXECUTION SUMMARY")
    print("=" * 68)
    print(f"  Status                 : {status}")
    print(f"  Target root            : {root_dir}")
    print(f"  Directories scanned    : {scan.scanned_dirs}")
    print(f"  Hidden dirs skipped    : {len(scan.skipped_hidden_dirs)}")
    print(f"  Empty folders detected : {len(scan.empty_dirs)}")
    print(f"  Files created          : {created}")
    print(f"  Files skipped          : {skipped}")
    print(f"  Files failed           : {failed}")
    print("=" * 68)


def wait_for_manual_close() -> None:
    """Keep the terminal open until the user presses Enter or closes the window."""
    print()
    try:
        input("Press Enter to exit (or close this terminal window manually)...")
    except (EOFError, KeyboardInterrupt):
        pass


def run() -> int:
    default_root, reason = detect_default_root()
    root_dir = prompt_project_root(default_root, reason)

    print(f"\n[STEP 1/3] Scanning directory tree: {root_dir}")
    scan = scan_project(root_dir)
    print(f"  - Directories scanned    : {scan.scanned_dirs}")
    print(f"  - Hidden dirs skipped    : {len(scan.skipped_hidden_dirs)}")
    if scan.skipped_hidden_dirs:
        for hidden in scan.skipped_hidden_dirs:
            print(f"      * skipped: {hidden.relative_to(root_dir)}")
    print(f"  - Empty folders detected : {len(scan.empty_dirs)}")

    if not scan.empty_dirs:
        print("\n[INFO] No truly empty folders were found. No files were created.")
        print_summary(root_dir, scan, status="No changes needed")
        return 0

    print(
        f"\n[STEP 2/3] Preview: {len(scan.empty_dirs)} empty '{PLACEHOLDER_FILENAME}' "
        "file(s) will be created:"
    )
    print("-" * 68)
    for idx, folder in enumerate(scan.empty_dirs, start=1):
        rel_target = (folder / PLACEHOLDER_FILENAME).relative_to(root_dir)
        print(f"  {idx:>3}. {rel_target}")
    print("-" * 68)

    confirm = input(
        f"\nProceed to create these {len(scan.empty_dirs)} file(s)? [y/N]: "
    ).strip().lower()

    if confirm not in ("y", "yes"):
        print("\n[INFO] Operation cancelled by user. No files were modified.")
        print_summary(root_dir, scan, status="Cancelled by user")
        return 0

    print()
    created, skipped, failed = create_placeholders(scan.empty_dirs, root_dir)

    status = "Completed successfully" if not failed else "Completed with errors"
    print_summary(
        root_dir,
        scan,
        status=status,
        created=len(created),
        skipped=len(skipped),
        failed=len(failed),
    )
    return 0 if not failed else 1


def main() -> int:
    exit_code = 0
    try:
        exit_code = run()
    except KeyboardInterrupt:
        print("\n\n[ABORTED] Interrupted by user (Ctrl+C). No further actions taken.")
        exit_code = 130
    except Exception:
        print("\n[FATAL ERROR] An unexpected error occurred:")
        traceback.print_exc()
        exit_code = 1
    finally:
        wait_for_manual_close()

    return exit_code


if __name__ == "__main__":
    sys.exit(main())