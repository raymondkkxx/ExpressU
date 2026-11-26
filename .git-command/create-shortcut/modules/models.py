# -*- coding: utf-8 -*-
"""
TargetItem Data Model for Files & Folders in .git-command
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from .config import MODE_AUTO, MODE_OPEN, MODE_TERMINAL, SCRIPT_EXTENSIONS


@dataclass
class TargetItem:
    item_id: str                    # Normalized lowercase absolute path string
    abs_path: Path                  # Resolved absolute path
    rel_path: Optional[Path]        # Relative to project_root; None if outside project
    rel_to_git_cmd: Optional[Path]  # Relative to .git-command; None if external
    is_dir: bool
    selected: bool
    shortcut_name: str
    default_name: str
    run_mode: str                   # MODE_AUTO / MODE_TERMINAL / MODE_OPEN
    icon_value: str                 # Local path or "dll,index"
    is_external: bool = False
    mtime: float = 0.0

    @property
    def ext(self) -> str:
        return "" if self.is_dir else self.abs_path.suffix.lower()

    @property
    def is_script(self) -> bool:
        return (not self.is_dir) and (self.ext in SCRIPT_EXTENSIONS)

    def resolved_mode(self) -> str:
        if self.run_mode != MODE_AUTO:
            return self.run_mode
        return MODE_TERMINAL if self.is_script else MODE_OPEN

    @property
    def mode_short_label(self) -> str:
        resolved = "终端常驻" if self.resolved_mode() == MODE_TERMINAL else "直接打开"
        return resolved if self.run_mode != MODE_AUTO else f"自动·{resolved}"

    @property
    def runner_tag(self) -> str:
        if self.is_dir:
            return "DIR"
        mapping = {
            ".sh": "Git Bash",
            ".py": "Python",
            ".bat": "Batch",
            ".cmd": "Batch",
            ".ps1": "PowerShell",
            ".js": "Node.js",
            ".mjs": "Node.js",
        }
        if self.ext in mapping:
            return f"{self.ext} · {mapping[self.ext]}"
        return self.ext.upper().lstrip(".") if self.ext else "FILE"

    @property
    def display_path(self) -> str:
        if self.rel_path is not None:
            return self.rel_path.as_posix()
        return str(self.abs_path)

    @property
    def node_label(self) -> str:
        return self.abs_path.name or str(self.abs_path)

    @property
    def is_renamed(self) -> bool:
        return self.shortcut_name.strip() != self.default_name