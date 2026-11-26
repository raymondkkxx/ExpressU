# -*- coding: utf-8 -*-
"""
Core Engine:
- Auto-detect project root containing .git-command
- Recursively scan all subdirectories & scripts for the file tree
- Zero-dependency PNG/JPG -> 256x256 ICO conversion via Qt QImage
- Portable relative-path .lnk generation via Windows PowerShell COM
"""

from __future__ import annotations

import json
import os
import re
import struct
import subprocess
import tempfile
from pathlib import Path
from typing import Optional

from .config import (
    CREATE_NO_WINDOW,
    EXCLUDED_DIRS,
    EXCLUDED_FILES,
    MODE_AUTO,
    MODE_OPEN,
    SCRIPT_EXTENSIONS,
    SYSTEM_ICON_PRESETS,
    TOOL_DIR_NAMES,
)
from .models import TargetItem
from .qt_compat import (
    ANTIALIASING,
    GLOBAL_TRANSPARENT,
    IMG_ARGB32,
    IO_WRITE_ONLY,
    KEEP_ASPECT,
    QBuffer,
    QByteArray,
    QImage,
    QPainter,
    SMOOTH_TRANSFORM,
)


def detect_project_root(cli_path: Optional[str] = None, anchor_file: Optional[Path] = None) -> Path:
    """Walk upward from CLI arg, anchor script, or CWD to locate the project root."""
    candidates: list[Path] = []
    if cli_path:
        p = Path(cli_path).expanduser().resolve()
        candidates.append(p if p.is_dir() else p.parent)

    if anchor_file is not None:
        candidates.append(anchor_file.resolve().parent)

    candidates.append(Path.cwd().resolve())
    candidates.append(Path(__file__).resolve().parent)

    for base in candidates:
        for parent in [base, *base.parents]:
            if parent.name == ".git-command":
                return parent.parent
            if (parent / ".git-command").is_dir():
                return parent

    for base in candidates:
        for parent in [base, *base.parents]:
            if (parent / ".git").exists():
                return parent

    return Path.cwd().resolve()


def default_icon_path(project_root: Path) -> str:
    """Default to .git-command/.icons/github.png (or github.ico), fallback to cmd icon."""
    icons_dir = project_root / ".git-command" / ".icons"
    png = icons_dir / "github.png"
    if png.is_file():
        return str(png.resolve())
    ico = icons_dir / "github.ico"
    if ico.is_file():
        return str(ico.resolve())
    return SYSTEM_ICON_PRESETS[1][1]


def scan_git_command_paths(
    project_root: Path,
    show_hidden: bool = False,
    show_tool_dir: bool = False,
) -> list[Path]:
    """
    Recursively discover all subdirectories and files under .git-command.
    Returns directories before their children so tree construction is deterministic.
    """
    git_cmd_dir = (project_root / ".git-command").resolve()
    if not git_cmd_dir.is_dir():
        return []

    discovered: list[Path] = []
    tool_dirs = {(git_cmd_dir / name).resolve() for name in TOOL_DIR_NAMES}

    for root_str, dirs, files in os.walk(git_cmd_dir):
        cur = Path(root_str).resolve()

        kept_dirs: list[str] = []
        for d in sorted(dirs, key=str.lower):
            if d in EXCLUDED_DIRS:
                continue
            if not show_hidden and d.startswith("."):
                continue
            candidate_dir = (cur / d).resolve()
            if not show_tool_dir and candidate_dir in tool_dirs:
                continue
            kept_dirs.append(d)

        dirs[:] = kept_dirs
        for d in kept_dirs:
            discovered.append((cur / d).resolve())

        for f in sorted(files, key=str.lower):
            if f in EXCLUDED_FILES:
                continue
            if not show_hidden and f.startswith("."):
                continue
            discovered.append((cur / f).resolve())

    return discovered


def create_target_item(
    path: Path,
    project_root: Path,
    icon_value: str,
    is_external: bool = False,
    preselect: Optional[bool] = None,
) -> TargetItem:
    resolved = path.resolve()
    proj_resolved = project_root.resolve()
    git_cmd_resolved = (proj_resolved / ".git-command").resolve()

    try:
        rel_proj: Optional[Path] = resolved.relative_to(proj_resolved)
    except ValueError:
        rel_proj = None
        is_external = True

    try:
        rel_git_cmd: Optional[Path] = resolved.relative_to(git_cmd_resolved)
    except ValueError:
        rel_git_cmd = None
        is_external = True

    is_dir = resolved.is_dir()
    default_name = resolved.name if is_dir else resolved.stem
    is_script = (not is_dir) and (resolved.suffix.lower() in SCRIPT_EXTENSIONS)
    selected = preselect if preselect is not None else is_script

    try:
        mtime = resolved.stat().st_mtime
    except OSError:
        mtime = 0.0

    return TargetItem(
        item_id=str(resolved).lower(),
        abs_path=resolved,
        rel_path=rel_proj,
        rel_to_git_cmd=rel_git_cmd,
        is_dir=is_dir,
        selected=selected,
        shortcut_name=default_name,
        default_name=default_name,
        run_mode=MODE_AUTO,
        icon_value=icon_value,
        is_external=is_external,
        mtime=mtime,
    )


def _write_png_as_ico(png_bytes: bytes, width: int, height: int, ico_path: Path) -> None:
    w_byte = 0 if width >= 256 else width
    h_byte = 0 if height >= 256 else height
    header = struct.pack("<HHH", 0, 1, 1)
    entry = struct.pack("<BBBBHHII", w_byte, h_byte, 0, 0, 1, 32, len(png_bytes), 22)
    ico_path.write_bytes(header + entry + png_bytes)


def _image_to_256_png_bytes(img_path: Path) -> bytes:
    src = QImage(str(img_path))
    if src.isNull():
        raise RuntimeError(f"无法读取图标图片: {img_path}")

    canvas = QImage(256, 256, IMG_ARGB32)
    canvas.fill(GLOBAL_TRANSPARENT)

    scaled = src.scaled(256, 256, KEEP_ASPECT, SMOOTH_TRANSFORM)
    painter = QPainter(canvas)
    painter.setRenderHint(ANTIALIASING)
    x = (256 - scaled.width()) // 2
    y = (256 - scaled.height()) // 2
    painter.drawImage(x, y, scaled)
    painter.end()

    ba = QByteArray()
    buf = QBuffer(ba)
    buf.open(IO_WRITE_ONLY)
    ok = canvas.save(buf, "PNG")
    buf.close()
    if not ok or ba.size() == 0:
        raise RuntimeError(f"图标 PNG 编码失败: {img_path.name}")
    return bytes(ba.data())


def prepare_icon_location(icon_value: str) -> str:
    """
    Resolve icon path for Windows .lnk.
    PNG/JPG/BMP files are automatically cached as a sibling .ico file.
    """
    val = icon_value.strip()
    if not val:
        return ""

    if "," in val and not Path(val).exists():
        return val

    icon_path = Path(val)
    if not icon_path.exists():
        return ""

    ext = icon_path.suffix.lower()
    if ext in {".ico", ".exe", ".dll", ".icl"}:
        return f"{icon_path.resolve()},0"

    if ext in {".png", ".jpg", ".jpeg", ".bmp", ".webp"}:
        ico_path = icon_path.with_suffix(".ico")
        need_build = (
            not ico_path.exists()
            or ico_path.stat().st_mtime < icon_path.stat().st_mtime
        )
        if need_build:
            data = icon_path.read_bytes()
            is_png = (
                len(data) >= 24
                and data[:8] == b"\x89PNG\r\n\x1a\n"
                and data[12:16] == b"IHDR"
            )
            if is_png:
                w, h = struct.unpack(">II", data[16:24])
                if 1 <= w <= 256 and 1 <= h <= 256 and w == h:
                    _write_png_as_ico(data, w, h, ico_path)
                else:
                    png_bytes = _image_to_256_png_bytes(icon_path)
                    _write_png_as_ico(png_bytes, 256, 256, ico_path)
            else:
                png_bytes = _image_to_256_png_bytes(icon_path)
                _write_png_as_ico(png_bytes, 256, 256, ico_path)
        return f"{ico_path.resolve()},0"

    return ""


def build_command_preview(item: TargetItem, utf8_console: bool) -> tuple[str, str, int]:
    """
    Build (target_path, arguments, window_style) for .lnk.
    Uses relative paths whenever the item resides inside project_root.
    """
    target_path = r"%SystemRoot%\System32\cmd.exe"

    if item.rel_path is not None:
        win_path = ".\\" + str(item.rel_path).replace("/", "\\")
        posix_path = "./" + str(item.rel_path).replace("\\", "/")
    else:
        win_path = str(item.abs_path)
        posix_path = str(item.abs_path).replace("\\", "/")

    if item.resolved_mode() == MODE_OPEN:
        return target_path, f'/c start "" "{win_path}"', 7

    ext = item.ext
    if ext in {".bat", ".cmd"}:
        cmd_body = f'call "{win_path}"'
    elif ext == ".ps1":
        cmd_body = f'powershell -NoProfile -ExecutionPolicy Bypass -File "{win_path}"'
    elif ext == ".py":
        cmd_body = f'python "{win_path}"'
    elif ext == ".sh":
        # Prefer Git for Windows bash.exe to avoid triggering WSL bash
        cmd_body = (
            f'(if exist "%ProgramFiles%\\Git\\bin\\bash.exe" '
            f'("%ProgramFiles%\\Git\\bin\\bash.exe" "{posix_path}") '
            f'else if exist "%ProgramFiles(x86)%\\Git\\bin\\bash.exe" '
            f'("%ProgramFiles(x86)%\\Git\\bin\\bash.exe" "{posix_path}") '
            f'else (bash "{posix_path}"))'
        )
    elif ext in {".js", ".mjs"}:
        cmd_body = f'node "{win_path}"'
    else:
        cmd_body = f'"{win_path}"'

    safe_label = re.sub(r'[&|<>^"%!]', "_", item.display_path)
    parts: list[str] = []
    if utf8_console:
        parts.append("chcp 65001 >nul")
    parts.append(f"echo [Git-Command] {safe_label}")
    parts.append(cmd_body)
    parts.append("echo.")
    parts.append("echo [Done] Terminal stays open in project root.")

    arguments = "/k " + " & ".join(parts)
    return target_path, arguments, 1


def build_shortcut_task(
    item: TargetItem,
    project_root: Path,
    save_dir: Path,
    utf8_console: bool,
) -> dict[str, object]:
    is_portable = (save_dir.resolve() == project_root.resolve()) and (item.rel_path is not None)
    # Empty WorkingDirectory allows Windows to use the .lnk folder as CWD (Git portable)
    working_dir = "" if is_portable else str(project_root.resolve())

    target_path, arguments, window_style = build_command_preview(item, utf8_console)
    icon_location = prepare_icon_location(item.icon_value)
    lnk_path = save_dir.resolve() / f"{item.shortcut_name}.lnk"

    return {
        "lnk_path": str(lnk_path),
        "target_path": target_path,
        "arguments": arguments,
        "working_directory": working_dir,
        "window_style": window_style,
        "description": f"Git Command: {item.display_path}",
        "icon_location": icon_location,
    }


def create_windows_shortcuts(tasks: list[dict[str, object]]) -> None:
    """Batch-generate Windows .lnk files using built-in PowerShell + WScript.Shell."""
    ps_code = r"""
$ErrorActionPreference = "Stop"
$jsonPath = $args[0]
$raw = Get-Content -LiteralPath $jsonPath -Raw -Encoding UTF8
$items = $raw | ConvertFrom-Json
if ($items -isnot [System.Array]) {
    $items = @($items)
}
$shell = New-Object -ComObject WScript.Shell
foreach ($item in $items) {
    $lnk = $shell.CreateShortcut($item.lnk_path)
    $lnk.TargetPath = $item.target_path
    $lnk.Arguments = $item.arguments
    $lnk.WorkingDirectory = $item.working_directory
    $lnk.WindowStyle = [int]$item.window_style
    if ($item.description) {
        $lnk.Description = $item.description
    }
    if ($item.icon_location) {
        $lnk.IconLocation = $item.icon_location
    }
    $lnk.Save()
}
"""
    with tempfile.TemporaryDirectory() as tmpdir:
        ps_file = Path(tmpdir) / "make_lnk.ps1"
        json_file = Path(tmpdir) / "tasks.json"
        ps_file.write_text(ps_code, encoding="utf-8-sig")
        json_file.write_text(json.dumps(tasks, ensure_ascii=False, indent=2), encoding="utf-8")

        res = subprocess.run(
            [
                "powershell",
                "-NoProfile",
                "-ExecutionPolicy",
                "Bypass",
                "-File",
                str(ps_file),
                str(json_file),
            ],
            capture_output=True,
            text=True,
            creationflags=CREATE_NO_WINDOW,
        )
        if res.returncode != 0:
            raise RuntimeError(res.stderr.strip() or res.stdout.strip() or "PowerShell 执行失败")


def reveal_in_explorer(path: Path) -> None:
    if path.exists():
        subprocess.Popen(["explorer", "/select,", str(path)], creationflags=CREATE_NO_WINDOW)