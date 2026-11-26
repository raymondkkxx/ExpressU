# -*- coding: utf-8 -*-
"""
Selection Memory / Preset Store (.git-command/create-shortcut/shortcuts_preset.json)
- Stores targets, custom names, run modes, icons, and save dir using portable relative paths
- Automatically restores remembered selections on next launch
- Provides one-click generation from saved preset for both GUI and CLI (--quick)
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Iterable, Optional

from .config import INVALID_FILENAME_RE, MODE_AUTO, MODE_OPEN, MODE_TERMINAL, PRESET_FILENAME
from .models import TargetItem
from .shortcut_engine import (
    build_shortcut_task,
    create_target_item,
    create_windows_shortcuts,
    default_icon_path,
)

VALID_MODES = {MODE_AUTO, MODE_TERMINAL, MODE_OPEN}


@dataclass
class QuickGenerateResult:
    ok: bool
    summary: str
    save_dir: Optional[Path] = None
    created_names: list[str] = field(default_factory=list)
    skipped_names: list[str] = field(default_factory=list)
    missing_targets: list[str] = field(default_factory=list)


def resolve_preset_path(project_root: Path) -> Path:
    """
    Resolve preset path under .git-command/create-shortcut/shortcuts_preset.json.
    Falls back to .git-command/creat-shortcut/ if that folder exists instead.
    """
    git_cmd = project_root.resolve() / ".git-command"
    preferred_dir = git_cmd / "create-shortcut"
    alt_dir = git_cmd / "creat-shortcut"

    if preferred_dir.is_dir():
        return preferred_dir / PRESET_FILENAME
    if alt_dir.is_dir():
        return alt_dir / PRESET_FILENAME
    return preferred_dir / PRESET_FILENAME


def _to_portable_path(path: Path, project_root: Path) -> str:
    resolved = path.resolve()
    root_resolved = project_root.resolve()
    if resolved == root_resolved:
        return "."
    try:
        return resolved.relative_to(root_resolved).as_posix()
    except ValueError:
        return str(resolved)


def _from_portable_path(raw: str, project_root: Path) -> Path:
    val = raw.strip()
    if not val or val == ".":
        return project_root.resolve()
    p = Path(val)
    if p.is_absolute():
        return p.resolve()
    return (project_root.resolve() / p).resolve()


def _to_portable_icon(icon_value: str, project_root: Path) -> str:
    val = icon_value.strip()
    if not val:
        return ""
    # Preserve Windows system icon syntax like "%SystemRoot%\System32\cmd.exe,0"
    if "," in val and not Path(val).exists():
        return val
    try:
        return _to_portable_path(Path(val), project_root)
    except OSError:
        return val


def _from_portable_icon(raw_icon: str, project_root: Path) -> str:
    val = raw_icon.strip()
    if not val:
        return ""
    if "," in val and not (project_root / val).exists() and not Path(val).exists():
        return val
    p = Path(val)
    if p.is_absolute():
        return str(p.resolve())
    return str((project_root.resolve() / p).resolve())


def save_preset(
    project_root: Path,
    save_dir: Path,
    selected_items: Iterable[TargetItem],
    utf8_console: bool,
    overwrite: bool,
) -> Path:
    """Persist current selections and generation options into shortcuts_preset.json."""
    preset_file = resolve_preset_path(project_root)
    preset_file.parent.mkdir(parents=True, exist_ok=True)

    entries: list[dict[str, str]] = []
    for item in selected_items:
        entries.append(
            {
                "target": _to_portable_path(item.abs_path, project_root),
                "shortcut_name": item.shortcut_name.strip() or item.default_name,
                "run_mode": item.run_mode if item.run_mode in VALID_MODES else MODE_AUTO,
                "icon": _to_portable_icon(item.icon_value, project_root),
            }
        )

    payload = {
        "version": 1,
        "updated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "save_dir": _to_portable_path(save_dir, project_root),
        "utf8_console": bool(utf8_console),
        "overwrite": bool(overwrite),
        "items": entries,
    }
    preset_file.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
    return preset_file


def load_preset(project_root: Path) -> Optional[dict]:
    """Load saved preset dict if present and valid; otherwise return None."""
    preset_file = resolve_preset_path(project_root)
    if not preset_file.is_file():
        return None
    try:
        raw = json.loads(preset_file.read_text(encoding="utf-8"))
        if not isinstance(raw, dict) or not isinstance(raw.get("items"), list):
            return None
        return raw
    except Exception:
        return None


def delete_preset(project_root: Path) -> bool:
    preset_file = resolve_preset_path(project_root)
    if preset_file.is_file():
        try:
            preset_file.unlink()
            return True
        except OSError:
            return False
    return False


def apply_preset_to_items(
    project_root: Path,
    items: dict[str, TargetItem],
    extra_paths: list[Path],
    preset: dict,
) -> tuple[Path, bool, bool, int, list[str]]:
    """
    Apply a loaded preset onto scanned TargetItems in-place.
    Returns (save_dir, utf8_console, overwrite, matched_count, missing_targets).
    """
    # Uncheck default auto-selected scripts so only remembered items are selected
    for it in items.values():
        it.selected = False

    save_dir = _from_portable_path(str(preset.get("save_dir", ".")), project_root)
    utf8_console = bool(preset.get("utf8_console", True))
    overwrite = bool(preset.get("overwrite", True))

    def_icon = default_icon_path(project_root)
    matched = 0
    missing: list[str] = []

    for entry in preset.get("items", []):
        if not isinstance(entry, dict):
            continue
        raw_target = str(entry.get("target", "")).strip()
        if not raw_target:
            continue

        abs_target = _from_portable_path(raw_target, project_root)
        if not abs_target.exists():
            missing.append(raw_target)
            continue

        key = str(abs_target.resolve()).lower()
        if key not in items:
            # Target may be an external file/folder or inside a hidden directory
            if abs_target not in extra_paths:
                extra_paths.append(abs_target)
            items[key] = create_target_item(
                abs_target,
                project_root,
                def_icon,
                is_external=True,
                preselect=True,
            )

        item = items[key]
        item.selected = True

        saved_name = str(entry.get("shortcut_name", "")).strip()
        if saved_name:
            item.shortcut_name = saved_name

        saved_mode = str(entry.get("run_mode", MODE_AUTO)).strip()
        item.run_mode = saved_mode if saved_mode in VALID_MODES else MODE_AUTO

        saved_icon_raw = str(entry.get("icon", "")).strip()
        if saved_icon_raw:
            resolved_icon = _from_portable_icon(saved_icon_raw, project_root)
            # If saved custom icon file was moved/deleted, fall back cleanly to default icon
            if "," in resolved_icon or Path(resolved_icon).exists():
                item.icon_value = resolved_icon
            else:
                item.icon_value = def_icon
        else:
            item.icon_value = def_icon

        matched += 1

    return save_dir, utf8_console, overwrite, matched, missing


def quick_generate_from_preset(project_root: Path) -> QuickGenerateResult:
    """
    Directly regenerate all shortcuts stored in shortcuts_preset.json without user interaction.
    Used by both GUI "一键按记忆生成" and CLI `--quick`.
    """
    preset = load_preset(project_root)
    if preset is None:
        return QuickGenerateResult(
            ok=False,
            summary="尚未找到记忆配置（请先至少生成一次以保存所选项）。",
        )

    items: dict[str, TargetItem] = {}
    extra_paths: list[Path] = []
    save_dir, utf8_console, overwrite, matched, missing = apply_preset_to_items(
        project_root=project_root,
        items=items,
        extra_paths=extra_paths,
        preset=preset,
    )

    selected_items = [it for it in items.values() if it.selected]
    if not selected_items:
        miss_hint = f"（{len(missing)} 项已失效/缺失）" if missing else ""
        return QuickGenerateResult(
            ok=False,
            summary=f"记忆配置中没有可生成的有效目标{miss_hint}。",
            save_dir=save_dir,
            missing_targets=missing,
        )

    try:
        save_dir.mkdir(parents=True, exist_ok=True)
    except OSError as exc:
        return QuickGenerateResult(
            ok=False,
            summary=f"无法创建保存目录：{exc}",
            save_dir=save_dir,
            missing_targets=missing,
        )

    # Validate names & duplicates
    seen_names: set[str] = set()
    for item in selected_items:
        name = item.shortcut_name.strip()
        if name.lower().endswith(".lnk"):
            name = name[:-4].strip()
            item.shortcut_name = name
        if not name or INVALID_FILENAME_RE.search(name):
            return QuickGenerateResult(
                ok=False,
                summary=f"记忆配置中存在非法快捷方式名称：{name or item.display_path}",
                save_dir=save_dir,
                missing_targets=missing,
            )
        low = name.lower()
        if low in seen_names:
            return QuickGenerateResult(
                ok=False,
                summary=f"记忆配置中存在重名快捷方式：{name}",
                save_dir=save_dir,
                missing_targets=missing,
            )
        seen_names.add(low)

    tasks: list[dict[str, object]] = []
    created_names: list[str] = []
    skipped_names: list[str] = []

    try:
        for item in selected_items:
            lnk_file = save_dir / f"{item.shortcut_name}.lnk"
            if lnk_file.exists() and not overwrite:
                skipped_names.append(lnk_file.name)
                continue
            tasks.append(
                build_shortcut_task(
                    item=item,
                    project_root=project_root,
                    save_dir=save_dir,
                    utf8_console=utf8_console,
                )
            )
            created_names.append(lnk_file.name)

        if tasks:
            create_windows_shortcuts(tasks)
    except Exception as exc:
        return QuickGenerateResult(
            ok=False,
            summary=f"一键生成失败：{exc}",
            save_dir=save_dir,
            missing_targets=missing,
        )

    parts: list[str] = []
    if created_names:
        parts.append(f"已按记忆一键生成 {len(created_names)} 个快捷方式")
    else:
        parts.append(f"记忆中的 {len(skipped_names)} 个快捷方式均已存在且未开启覆盖")

    if created_names and skipped_names:
        parts.append(f"跳过已存在 {len(skipped_names)} 个")
    if missing:
        parts.append(f"忽略缺失源文件 {len(missing)} 个")

    return QuickGenerateResult(
        ok=True,
        summary="，".join(parts) + "。",
        save_dir=save_dir,
        created_names=created_names,
        skipped_names=skipped_names,
        missing_targets=missing,
    )