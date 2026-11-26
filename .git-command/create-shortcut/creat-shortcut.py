# -*- coding: utf-8 -*-
"""
Main entry point for Git Command Shortcut Manager.
Usage:
    # Open interactive glassmorphism panel (auto-restores remembered selections)
    python .git-command/create-shortcut/creat-shortcut.py [optional_project_root]

    # One-click regenerate all shortcuts directly from create-shortcut/shortcuts_preset.json
    python .git-command/create-shortcut/creat-shortcut.py --quick [optional_project_root]
"""

from __future__ import annotations

import argparse
import platform
import sys
from pathlib import Path

# Locate the directory containing the `modules` package
SCRIPT_DIR = Path(__file__).resolve().parent
CANDIDATE_ROOTS = [
    SCRIPT_DIR,
    SCRIPT_DIR.parent / "create-shortcut",
]
for root_dir in CANDIDATE_ROOTS:
    if (root_dir / "modules").is_dir():
        if str(root_dir) not in sys.path:
            sys.path.insert(0, str(root_dir))
        break

from modules.main_window import ShortcutManagerWindow, send_companion_toast
from modules.preset_store import quick_generate_from_preset
from modules.qt_compat import QApplication, exec_app
from modules.shortcut_engine import detect_project_root
from modules.theme import make_app_window_icon


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Git Command Shortcut Manager (.lnk)")
    parser.add_argument(
        "project_root",
        nargs="?",
        default=None,
        help="Optional project root directory path",
    )
    parser.add_argument(
        "-q",
        "--quick",
        "--apply",
        action="store_true",
        dest="quick",
        help="Directly regenerate shortcuts from saved shortcuts_preset.json without opening the GUI",
    )
    return parser.parse_args(argv)


def run_cli_quick(project_root: Path) -> int:
    res = quick_generate_from_preset(project_root)
    print(f"[Git-Command] 项目根目录: {project_root}")
    if res.save_dir is not None:
        print(f"[Git-Command] 保存位置: {res.save_dir}")
    print(f"[Git-Command] 结果: {res.summary}")

    if res.created_names:
        print("已生成:")
        for name in res.created_names:
            print(f"  + {name}")
    if res.skipped_names:
        print("已跳过 (已存在):")
        for name in res.skipped_names:
            print(f"  - {name}")
    if res.missing_targets:
        print("警告 - 记忆中以下源文件已缺失:")
        for m in res.missing_targets:
            print(f"  ! {m}")

    send_companion_toast(res.summary, 2200, "info" if res.ok else "error")
    return 0 if res.ok else 1


def main() -> None:
    if platform.system() != "Windows":
        print("此工具仅支持在 Windows 上生成 .lnk 快捷方式。", file=sys.stderr)
        sys.exit(1)

    args = parse_args(sys.argv[1:])
    project_root = detect_project_root(cli_path=args.project_root, anchor_file=Path(__file__))

    if args.quick:
        sys.exit(run_cli_quick(project_root))

    app = QApplication(sys.argv)
    default_png = project_root / ".git-command" / ".icons" / "github.png"
    app.setWindowIcon(make_app_window_icon(default_png if default_png.is_file() else None))

    window = ShortcutManagerWindow(project_root)
    window.show()

    # Default focus on save path input so pressing Enter immediately generates with remembered settings
    window.save_dir_input.setFocus()
    window.save_dir_input.end(False)

    sys.exit(exec_app(app))


if __name__ == "__main__":
    main()