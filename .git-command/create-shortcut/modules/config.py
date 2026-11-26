# -*- coding: utf-8 -*-
"""
Global Constants, Palette Tokens & UI Preference Persistence
"""

from __future__ import annotations

import json
import re
import subprocess
import tempfile
from pathlib import Path

# Dual-font CSS declaration
FONT_STYLE_BASE = 'font-family: "Consolas", "Microsoft YaHei UI", monospace;'

# Unified Accent Palette: Black, Rose Red, Dark Orange
PALETTE_BLACK = "#18181B"
PALETTE_BLACK_SUB = "#52525B"
PALETTE_ROSE = "#E11D48"
PALETTE_ROSE_LIGHT = "#FB7185"
PALETTE_ROSE_DEEP = "#BE123C"
PALETTE_ORANGE = "#C2410C"
PALETTE_ORANGE_LIGHT = "#FB923C"
PALETTE_ORANGE_DEEP = "#9A3412"

# Window Defaults
DEFAULT_PANEL_WIDTH = 1040
DEFAULT_PANEL_HEIGHT = 700
DEFAULT_TRANSPARENCY = 18  # 0% = pure white opaque, 1%~95% = dark black-gray translucent

# Scanning & Preset Rules
TOOL_DIR_NAMES = {"create-shortcut", "creat-shortcut"}
PRESET_FILENAME = "shortcuts_preset.json"
EXCLUDED_DIRS = {".icons", "__pycache__", ".git", ".venv", "venv", "node_modules"}
EXCLUDED_FILES = {".DS_Store", "Thumbs.db", "desktop.ini"}
SCRIPT_EXTENSIONS = {".bat", ".cmd", ".ps1", ".py", ".sh", ".js", ".mjs"}

# Run Modes
MODE_AUTO = "auto"
MODE_TERMINAL = "terminal"
MODE_OPEN = "open"

# Tree Filters
FILTER_ALL = "all"
FILTER_SCRIPTS = "scripts"
FILTER_DIRS = "dirs"
FILTER_SELECTED = "selected"
FILTER_EXISTING = "existing"

# Built-in Windows System Icon Presets (100% portable across machines)
SYSTEM_ICON_PRESETS: list[tuple[str, str]] = [
    ("自定义 / .icons 图标", ""),
    ("系统 · 终端 (cmd)", r"%SystemRoot%\System32\cmd.exe,0"),
    ("系统 · 文件夹", r"%SystemRoot%\System32\shell32.dll,3"),
    ("系统 · 工具齿轮", r"%SystemRoot%\System32\shell32.dll,316"),
    ("系统 · 同步刷新", r"%SystemRoot%\System32\shell32.dll,238"),
    ("系统 · 网络地球", r"%SystemRoot%\System32\shell32.dll,13"),
    ("系统 · 文档", r"%SystemRoot%\System32\shell32.dll,70"),
    ("系统 · 闪电运行", r"%SystemRoot%\System32\imageres.dll,102"),
]

INVALID_FILENAME_RE = re.compile(r'[<>:"/\\|?*]')
CREATE_NO_WINDOW = getattr(subprocess, "CREATE_NO_WINDOW", 0x08000000)

# Store local UI-only preferences (transparency, etc.) in OS temp dir
UI_CONFIG_FILE = Path(tempfile.gettempdir()) / "git_command_create_shortcut_ui.json"


def clamp_transparency(val: int) -> int:
    try:
        v = int(val)
    except Exception:
        v = DEFAULT_TRANSPARENCY
    return max(0, min(95, v))


def load_ui_config() -> dict:
    defaults = {
        "transparency": DEFAULT_TRANSPARENCY,
        "utf8_console": True,
        "overwrite": True,
        "show_hidden": False,
        "show_tool_dir": False,
    }
    if UI_CONFIG_FILE.exists():
        try:
            raw = json.loads(UI_CONFIG_FILE.read_text(encoding="utf-8"))
            if isinstance(raw, dict):
                defaults.update(raw)
        except Exception:
            pass
    defaults["transparency"] = clamp_transparency(defaults["transparency"])
    return defaults


def save_ui_config(cfg: dict) -> None:
    try:
        UI_CONFIG_FILE.write_text(
            json.dumps(cfg, indent=2, ensure_ascii=False),
            encoding="utf-8",
        )
    except Exception:
        pass