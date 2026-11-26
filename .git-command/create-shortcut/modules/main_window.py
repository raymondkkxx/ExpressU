# -*- coding: utf-8 -*-
"""
Main Frameless Glass Window:
- Draggable header bar & all-edge borderless resizing
- Collapsible setting panel (0% pure white / 1%~95% translucent black-gray glass)
- Auto-saves & restores selected items via create-shortcut/shortcuts_preset.json
- Provides one-click "按记忆一键生成" button & themed completion dialog
"""

from __future__ import annotations

import json
import subprocess
import threading
import urllib.request
from pathlib import Path
from typing import Optional

from .config import (
    CREATE_NO_WINDOW,
    DEFAULT_PANEL_HEIGHT,
    DEFAULT_PANEL_WIDTH,
    DEFAULT_TRANSPARENCY,
    FONT_STYLE_BASE,
    INVALID_FILENAME_RE,
    MODE_AUTO,
    PALETTE_ROSE,
    PRESET_FILENAME,
    clamp_transparency,
    load_ui_config,
    save_ui_config,
)
from .inspector_panel import InspectorPanel
from .models import TargetItem
from .preset_store import (
    apply_preset_to_items,
    delete_preset,
    load_preset,
    quick_generate_from_preset,
    resolve_preset_path,
    save_preset,
)
from .qt_compat import (
    ALIGN_LEFT_VCENTER,
    CURSOR_BDIAG,
    CURSOR_FDIAG,
    CURSOR_HOR,
    CURSOR_POINTER,
    CURSOR_SIZEALL,
    CURSOR_VER,
    EV_MOVE,
    EV_PRESS,
    EV_RELEASE,
    FLAG_FRAMELESS,
    FLAG_FRAMELESS_DIALOG,
    KEY_A,
    KEY_ENTER,
    KEY_ESC,
    KEY_F,
    KEY_F2,
    KEY_RETURN,
    MOD_CTRL,
    MOUSE_LEFT,
    NO_FRAME,
    ORIENT_HORIZONTAL,
    QApplication,
    QCheckBox,
    QColor,
    QComboBox,
    QDialog,
    QFileDialog,
    QFrame,
    QGraphicsDropShadowEffect,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QRect,
    QScrollArea,
    QSlider,
    QSplitter,
    QTimer,
    QVBoxLayout,
    QWidget,
    WA_TRANSLUCENT,
    event_global_pos,
    exec_dialog,
    make_ui_font,
)
from .shortcut_engine import (
    build_shortcut_task,
    create_target_item,
    create_windows_shortcuts,
    default_icon_path,
    scan_git_command_paths,
)
from .theme import (
    ThemePalette,
    build_button_stylesheet,
    build_checkbox_stylesheet,
    build_input_stylesheet,
    build_pill_stylesheet,
    build_slider_stylesheet,
    compute_theme_palette,
)
from .tree_selector import FileTreeSelector

NOTIFICATION_PORT = 15057


def send_companion_toast(text: str, duration: int = 2200, tip_type: str = "info") -> None:
    """Fire-and-forget notification to local toast service (127.0.0.1:15057) if running."""
    def _worker() -> None:
        payload = json.dumps(
            {"text": text, "duration": duration, "type": tip_type},
            ensure_ascii=False,
        ).encode("utf-8")
        req = urllib.request.Request(
            f"http://127.0.0.1:{NOTIFICATION_PORT}/toast",
            data=payload,
            headers={"Content-Type": "application/json; charset=utf-8"},
            method="POST",
        )
        try:
            with urllib.request.urlopen(req, timeout=0.3):
                pass
        except Exception:
            pass

    threading.Thread(target=_worker, daemon=True).start()


class GenerationResultDialog(QDialog):
    """Frameless themed result popup displayed after shortcut creation finishes."""

    def __init__(
        self,
        parent: QWidget,
        palette: ThemePalette,
        title: str,
        summary: str,
        save_dir: Optional[Path],
        created_names: list[str],
        skipped_names: list[str],
        missing_targets: Optional[list[str]] = None,
        preset_note: str = "",
        is_error: bool = False,
    ):
        super().__init__(parent)
        self.setWindowFlags(FLAG_FRAMELESS_DIALOG)
        self.setAttribute(WA_TRANSLUCENT)
        self.setModal(True)
        self.save_dir = save_dir
        self._drag_offset = None

        outer = QVBoxLayout(self)
        outer.setContentsMargins(10, 10, 10, 10)

        card = QFrame(self)
        card.setObjectName("resultCard")

        bg_css = "#FFFFFF" if not palette.is_dark else "rgba(22, 24, 30, 244)"
        bd_css = "1px solid #D4D4D8" if not palette.is_dark else "1px solid rgba(255, 255, 255, 42)"
        card.setStyleSheet(f"""
            QFrame#resultCard {{
                {FONT_STYLE_BASE}
                background-color: {bg_css};
                border: {bd_css};
                border-radius: 12px;
            }}
        """)

        shadow = QGraphicsDropShadowEffect(self)
        shadow.setBlurRadius(28)
        shadow.setOffset(0, 8)
        shadow.setColor(QColor(0, 0, 0, 85 if palette.is_dark else 52))
        card.setGraphicsEffect(shadow)

        layout = QVBoxLayout(card)
        layout.setContentsMargins(16, 14, 16, 14)
        layout.setSpacing(10)

        # Header
        hdr = QHBoxLayout()
        hdr.setContentsMargins(0, 0, 0, 0)
        hdr.setSpacing(8)

        badge_text = "ERROR" if is_error else ("DONE" if created_names else "NOTICE")
        badge_bg = palette.rose_pill_bg if is_error else palette.org_pill_bg
        badge_fg = palette.rose_accent if is_error else palette.org_accent

        badge = QLabel(badge_text, card)
        badge.setFont(make_ui_font(7.8, bold=True))
        badge.setStyleSheet(
            f"{FONT_STYLE_BASE} color: {badge_fg}; background: {badge_bg}; "
            f"border-radius: 5px; padding: 2px 8px;"
        )

        title_lbl = QLabel(title, card)
        title_lbl.setFont(make_ui_font(10.0, bold=True))
        title_lbl.setStyleSheet(f"{FONT_STYLE_BASE} color: {palette.text_fg}; background: transparent;")

        close_x = QPushButton("×", card)
        close_x.setFixedSize(24, 24)
        close_x.setCursor(CURSOR_POINTER)
        close_x.setFont(make_ui_font(12.0, bold=True))
        close_x.setStyleSheet(f"""
            QPushButton {{
                {FONT_STYLE_BASE} background: transparent; color: {palette.muted_fg};
                border: none; border-radius: 6px;
            }}
            QPushButton:hover {{ background: {palette.rose_pill_bg}; color: {palette.rose_accent}; }}
        """)
        close_x.clicked.connect(self.accept)

        hdr.addWidget(badge)
        hdr.addWidget(title_lbl, 1)
        hdr.addWidget(close_x)
        layout.addLayout(hdr)

        # Summary & Save Path
        summary_lbl = QLabel(summary, card)
        summary_lbl.setFont(make_ui_font(8.6))
        summary_lbl.setWordWrap(True)
        summary_lbl.setStyleSheet(f"{FONT_STYLE_BASE} color: {palette.text_fg}; background: transparent;")
        layout.addWidget(summary_lbl)

        if save_dir is not None:
            path_lbl = QLabel(f"保存位置: {save_dir}", card)
            path_lbl.setFont(make_ui_font(7.8))
            path_lbl.setWordWrap(True)
            path_lbl.setStyleSheet(
                f"{FONT_STYLE_BASE} color: {palette.muted_fg}; background: {palette.ctrl_bg}; "
                f"border-radius: 6px; padding: 6px 9px;"
            )
            layout.addWidget(path_lbl)

        if preset_note:
            note_lbl = QLabel(preset_note, card)
            note_lbl.setFont(make_ui_font(7.6))
            note_lbl.setWordWrap(True)
            note_lbl.setStyleSheet(f"{FONT_STYLE_BASE} color: {palette.org_accent}; background: transparent;")
            layout.addWidget(note_lbl)

        # Scrollable List of Generated / Skipped / Missing Items
        lines: list[str] = []
        if created_names:
            lines.append(f"已生成 ({len(created_names)} 个):")
            lines.extend(f"  ✓ {name}" for name in created_names)
        if skipped_names:
            if lines:
                lines.append("")
            lines.append(f"已跳过已存在 ({len(skipped_names)} 个):")
            lines.extend(f"  · {name}" for name in skipped_names)
        if missing_targets:
            if lines:
                lines.append("")
            lines.append(f"记忆中已失效/缺失的源文件 ({len(missing_targets)} 个):")
            lines.extend(f"  ! {m}" for m in missing_targets)

        if lines:
            scroll = QScrollArea(card)
            scroll.setWidgetResizable(True)
            scroll.setFrameShape(NO_FRAME)
            scroll.setMaximumHeight(210)
            scroll.setStyleSheet(f"""
                QScrollArea {{
                    background-color: {palette.ctrl_bg};
                    border-radius: 7px;
                }}
                QScrollBar:vertical {{ width: 5px; background: transparent; }}
                QScrollBar::handle:vertical {{ background: {palette.scroll_col}; border-radius: 2px; }}
                QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{ height: 0px; }}
            """)

            content = QLabel("\n".join(lines), scroll)
            content.setFont(make_ui_font(8.2))
            content.setAlignment(ALIGN_LEFT_VCENTER)
            content.setWordWrap(True)
            content.setStyleSheet(
                f"{FONT_STYLE_BASE} color: {palette.text_fg}; background: transparent; padding: 8px 10px;"
            )
            scroll.setWidget(content)
            layout.addWidget(scroll)

        # Footer Buttons
        btn_row = QHBoxLayout()
        btn_row.setContentsMargins(0, 4, 0, 0)
        btn_row.setSpacing(8)
        btn_row.addStretch(1)

        if save_dir is not None and save_dir.exists():
            open_btn = QPushButton("打开保存目录", card)
            open_btn.setCursor(CURSOR_POINTER)
            open_btn.setFont(make_ui_font(8.4, bold=True))
            open_btn.setStyleSheet(build_button_stylesheet(palette, "neutral", "6px 14px"))
            open_btn.clicked.connect(self._open_save_dir)
            btn_row.addWidget(open_btn)

        ok_btn = QPushButton("确定", card)
        ok_btn.setCursor(CURSOR_POINTER)
        ok_btn.setFont(make_ui_font(8.4, bold=True))
        ok_btn.setStyleSheet(build_button_stylesheet(palette, "rose", "6px 20px"))
        ok_btn.setDefault(True)
        ok_btn.clicked.connect(self.accept)
        btn_row.addWidget(ok_btn)

        layout.addLayout(btn_row)
        outer.addWidget(card)

        self.setMinimumWidth(470)
        self.setMaximumWidth(580)
        self.adjustSize()

        if parent is not None:
            pg = parent.frameGeometry()
            self.move(
                pg.center().x() - self.width() // 2,
                pg.center().y() - self.height() // 2,
            )

    def _open_save_dir(self) -> None:
        if self.save_dir and self.save_dir.exists():
            subprocess.Popen(["explorer", str(self.save_dir)], creationflags=CREATE_NO_WINDOW)

    def mousePressEvent(self, event) -> None:
        if event.button() == MOUSE_LEFT:
            self._drag_offset = event_global_pos(event) - self.frameGeometry().topLeft()
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event) -> None:
        if self._drag_offset is not None:
            self.move(event_global_pos(event) - self._drag_offset)
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event) -> None:
        self._drag_offset = None
        super().mouseReleaseEvent(event)


class ShortcutManagerWindow(QWidget):
    RESIZE_MARGIN = 12

    def __init__(self, initial_project_root: Path):
        super().__init__()
        self.setWindowFlags(FLAG_FRAMELESS)
        self.setAttribute(WA_TRANSLUCENT)
        self.setMouseTracking(True)

        self.cfg = load_ui_config()
        self.transparency: int = clamp_transparency(self.cfg.get("transparency", DEFAULT_TRANSPARENCY))
        self.palette: ThemePalette = compute_theme_palette(self.transparency)
        self.is_setting_open: bool = False

        self.project_root: Path = initial_project_root.resolve()
        self.items: dict[str, TargetItem] = {}
        self.extra_paths: list[Path] = []

        # Drag & Edge-Resize state
        self._is_dragging = False
        self._drag_offset = None
        self._resize_edges = ""
        self._resize_start_global = None
        self._resize_start_geom = None

        self.save_cfg_timer = QTimer(self)
        self.save_cfg_timer.setSingleShot(True)
        self.save_cfg_timer.timeout.connect(self._persist_config)

        self.status_timer = QTimer(self)
        self.status_timer.setSingleShot(True)
        self.status_timer.timeout.connect(
            lambda: self.set_status("就绪 · 勾选脚本或目录后按 Enter 保存至项目根目录", "muted")
        )

        self._init_ui()
        self._wire_signals()
        self.apply_transparency_theme(self.transparency, save=False)

        QApplication.instance().installEventFilter(self)

        self.inspector.set_project_root(self.project_root)
        self.inspector.set_utf8_console(self.utf8_chk.isChecked())
        # Initial scan automatically loads remembered preset if present
        self.scan_git_command(apply_preset=True)

    # --------------------------------------------------------------------------
    # UI Construction
    # --------------------------------------------------------------------------
    def _init_ui(self) -> None:
        outer = QVBoxLayout(self)
        outer.setContentsMargins(10, 10, 10, 10)

        self.card = QWidget(self)
        self.card.setObjectName("mainCard")
        self.card.setMouseTracking(True)

        self.shadow_effect = QGraphicsDropShadowEffect(self)
        self.shadow_effect.setBlurRadius(28)
        self.shadow_effect.setOffset(0, 6)
        self.shadow_effect.setColor(QColor(24, 24, 27, 52))
        self.card.setGraphicsEffect(self.shadow_effect)

        card_layout = QVBoxLayout(self.card)
        card_layout.setContentsMargins(14, 11, 14, 12)
        card_layout.setSpacing(8)

        # --- 1. Draggable Header Bar ---
        self.header_bar = QWidget(self.card)
        self.header_bar.setMouseTracking(True)
        self.header_bar.setCursor(CURSOR_SIZEALL)
        header = QHBoxLayout(self.header_bar)
        header.setContentsMargins(2, 0, 2, 0)
        header.setSpacing(7)

        self.count_lbl = QLabel("已选 0 / 0 项", self.header_bar)
        self.count_lbl.setFont(make_ui_font(8.5, bold=True))

        self.project_badge = QLabel("", self.header_bar)
        self.project_badge.setFont(make_ui_font(8.5, bold=True))

        self.preset_badge = QLabel("", self.header_bar)
        self.preset_badge.setFont(make_ui_font(7.8, bold=True))
        self.preset_badge.setVisible(False)

        self.switch_proj_btn = QPushButton("切换项目", self.header_bar)
        self.switch_proj_btn.setCursor(CURSOR_POINTER)
        self.switch_proj_btn.setFont(make_ui_font(8.0, bold=True))
        self.switch_proj_btn.clicked.connect(self.browse_project_root)

        self.setting_btn = QPushButton("setting", self.header_bar)
        self.setting_btn.setCursor(CURSOR_POINTER)
        self.setting_btn.setFont(make_ui_font(8.0, bold=True))
        self.setting_btn.setToolTip("透明度、扫描选项与记忆管理")
        self.setting_btn.clicked.connect(self.toggle_setting_panel)

        self.min_btn = QPushButton("—", self.header_bar)
        self.min_btn.setFixedSize(26, 26)
        self.min_btn.setCursor(CURSOR_POINTER)
        self.min_btn.setFont(make_ui_font(9.0, bold=True))
        self.min_btn.setToolTip("最小化")
        self.min_btn.clicked.connect(self.showMinimized)

        self.close_btn = QPushButton("×", self.header_bar)
        self.close_btn.setFixedSize(26, 26)
        self.close_btn.setCursor(CURSOR_POINTER)
        self.close_btn.setFont(make_ui_font(12.5, bold=True))
        self.close_btn.setToolTip("关闭 (Esc)")
        self.close_btn.clicked.connect(self.close)

        header.addWidget(self.count_lbl)
        header.addWidget(self.project_badge)
        header.addWidget(self.preset_badge)
        header.addWidget(self.switch_proj_btn)
        header.addStretch(1)
        header.addWidget(self.setting_btn)
        header.addWidget(self.min_btn)
        header.addWidget(self.close_btn)
        card_layout.addWidget(self.header_bar)

        # --- 2. Collapsible Setting Panel ---
        self.setting_panel = QFrame(self.card)
        self.setting_panel.setObjectName("settingPanel")
        self.setting_panel.setVisible(False)
        sp_layout = QVBoxLayout(self.setting_panel)
        sp_layout.setContentsMargins(10, 8, 10, 8)
        sp_layout.setSpacing(6)

        sp_top = QHBoxLayout()
        sp_top.setContentsMargins(0, 0, 0, 0)
        self.sp_title_lbl = QLabel("Setting · 透明度、扫描与记忆配置", self.setting_panel)
        self.sp_title_lbl.setFont(make_ui_font(8.5, bold=True))
        self.opacity_val_lbl = QLabel("", self.setting_panel)
        self.opacity_val_lbl.setFont(make_ui_font(8.0, bold=True))
        sp_top.addWidget(self.sp_title_lbl)
        sp_top.addStretch(1)
        sp_top.addWidget(self.opacity_val_lbl)
        sp_layout.addLayout(sp_top)

        self.opacity_slider = QSlider(ORIENT_HORIZONTAL, self.setting_panel)
        self.opacity_slider.setRange(0, 95)
        self.opacity_slider.setValue(self.transparency)
        self.opacity_slider.setCursor(CURSOR_POINTER)
        self.opacity_slider.valueChanged.connect(lambda v: self.apply_transparency_theme(v, save=True))
        sp_layout.addWidget(self.opacity_slider)

        preset_row = QHBoxLayout()
        preset_row.setContentsMargins(0, 0, 0, 0)
        preset_row.setSpacing(5)
        self.preset_buttons: list[tuple[QPushButton, int]] = []
        for lbl_txt, val in [("0% 白底", 0), ("15%", 15), ("30%", 30), ("50%", 50), ("80%", 80)]:
            btn = QPushButton(lbl_txt, self.setting_panel)
            btn.setCursor(CURSOR_POINTER)
            btn.setFont(make_ui_font(7.5, bold=True))
            btn.clicked.connect(lambda checked=False, v=val: self._set_transparency_preset(v))
            preset_row.addWidget(btn)
            self.preset_buttons.append((btn, val))
        preset_row.addStretch(1)

        self.utf8_chk = QCheckBox("UTF-8 终端 (chcp 65001)", self.setting_panel)
        self.utf8_chk.setFont(make_ui_font(7.8))
        self.utf8_chk.setChecked(bool(self.cfg.get("utf8_console", True)))

        self.overwrite_chk = QCheckBox("覆盖同名 .lnk", self.setting_panel)
        self.overwrite_chk.setFont(make_ui_font(7.8))
        self.overwrite_chk.setChecked(bool(self.cfg.get("overwrite", True)))

        self.hidden_chk = QCheckBox("显示隐藏项", self.setting_panel)
        self.hidden_chk.setFont(make_ui_font(7.8))
        self.hidden_chk.setChecked(bool(self.cfg.get("show_hidden", False)))

        self.tool_dir_chk = QCheckBox("显示 create-shortcut 自身", self.setting_panel)
        self.tool_dir_chk.setFont(make_ui_font(7.8))
        self.tool_dir_chk.setChecked(bool(self.cfg.get("show_tool_dir", False)))

        preset_row.addWidget(self.utf8_chk)
        preset_row.addWidget(self.overwrite_chk)
        preset_row.addWidget(self.hidden_chk)
        preset_row.addWidget(self.tool_dir_chk)
        sp_layout.addLayout(preset_row)

        # Memory management row inside setting panel
        mem_row = QHBoxLayout()
        mem_row.setContentsMargins(0, 2, 0, 0)
        mem_row.setSpacing(6)
        self.mem_path_lbl = QLabel("", self.setting_panel)
        self.mem_path_lbl.setFont(make_ui_font(7.5))

        self.btn_reload_preset = QPushButton("还原上次记忆", self.setting_panel)
        self.btn_save_preset_only = QPushButton("仅保存当前记忆", self.setting_panel)
        self.btn_clear_preset = QPushButton("清除记忆", self.setting_panel)
        for b in (self.btn_reload_preset, self.btn_save_preset_only, self.btn_clear_preset):
            b.setCursor(CURSOR_POINTER)
            b.setFont(make_ui_font(7.5, bold=True))

        self.btn_reload_preset.clicked.connect(self.reload_saved_preset)
        self.btn_save_preset_only.clicked.connect(self.save_current_preset_only)
        self.btn_clear_preset.clicked.connect(self.clear_saved_preset)

        mem_row.addWidget(self.mem_path_lbl, 1)
        mem_row.addWidget(self.btn_reload_preset)
        mem_row.addWidget(self.btn_save_preset_only)
        mem_row.addWidget(self.btn_clear_preset)
        sp_layout.addLayout(mem_row)

        card_layout.addWidget(self.setting_panel)

        # --- 3. Split Workspace (Left: File Tree, Right: Inspector) ---
        self.splitter = QSplitter(ORIENT_HORIZONTAL, self.card)
        self.splitter.setChildrenCollapsible(False)
        self.splitter.setHandleWidth(8)

        self.tree_selector = FileTreeSelector(self.splitter)
        self.inspector = InspectorPanel(self.splitter)

        self.splitter.addWidget(self.tree_selector)
        self.splitter.addWidget(self.inspector)
        self.splitter.setSizes([640, 360])
        card_layout.addWidget(self.splitter, 1)

        # --- 4. Footer: Save Path Confirmation + Quick Memory Generate + Generate ---
        self.footer_box = QFrame(self.card)
        self.footer_box.setObjectName("footerCard")
        footer_v = QVBoxLayout(self.footer_box)
        footer_v.setContentsMargins(10, 8, 10, 8)
        footer_v.setSpacing(7)

        save_row = QHBoxLayout()
        save_row.setContentsMargins(0, 0, 0, 0)
        save_row.setSpacing(6)

        self.lbl_save_title = QLabel("保存位置:", self.footer_box)
        self.lbl_save_title.setFont(make_ui_font(8.2, bold=True))

        self.save_dir_input = QLineEdit(self.footer_box)
        self.save_dir_input.setFont(make_ui_font(8.5))
        self.save_dir_input.setText(str(self.project_root))
        self.save_dir_input.setPlaceholderText("留空按 Enter 默认保存到项目根目录 (Git 便携相对路径模式)")

        self.save_mode_pill = QLabel("", self.footer_box)
        self.save_mode_pill.setFont(make_ui_font(7.5, bold=True))

        self.btn_reset_save = QPushButton("默认根目录", self.footer_box)
        self.btn_reset_save.setCursor(CURSOR_POINTER)
        self.btn_reset_save.setFont(make_ui_font(7.8, bold=True))
        self.btn_reset_save.clicked.connect(self.reset_save_dir)

        self.btn_browse_save = QPushButton("浏览...", self.footer_box)
        self.btn_browse_save.setCursor(CURSOR_POINTER)
        self.btn_browse_save.setFont(make_ui_font(7.8, bold=True))
        self.btn_browse_save.clicked.connect(self.browse_save_dir)

        save_row.addWidget(self.lbl_save_title)
        save_row.addWidget(self.save_dir_input, 1)
        save_row.addWidget(self.save_mode_pill)
        save_row.addWidget(self.btn_reset_save)
        save_row.addWidget(self.btn_browse_save)
        footer_v.addLayout(save_row)

        action_row = QHBoxLayout()
        action_row.setContentsMargins(0, 0, 0, 0)
        action_row.setSpacing(8)

        self.status_lbl = QLabel("就绪 · 勾选脚本或目录后按 Enter 保存至项目根目录", self.footer_box)
        self.status_lbl.setFont(make_ui_font(8.0))

        self.quick_mem_btn = QPushButton("按记忆一键生成", self.footer_box)
        self.quick_mem_btn.setCursor(CURSOR_POINTER)
        self.quick_mem_btn.setFont(make_ui_font(8.5, bold=True))
        self.quick_mem_btn.setToolTip("直接读取 create-shortcut/shortcuts_preset.json 一键生成全部快捷方式")
        self.quick_mem_btn.clicked.connect(self.run_quick_memory_generate)
        self.quick_mem_btn.setVisible(False)

        self.generate_btn = QPushButton("生成并记忆所选 (Enter)", self.footer_box)
        self.generate_btn.setCursor(CURSOR_POINTER)
        self.generate_btn.setFont(make_ui_font(8.8, bold=True))
        self.generate_btn.clicked.connect(self.generate_shortcuts)

        action_row.addWidget(self.status_lbl, 1)
        action_row.addWidget(self.quick_mem_btn)
        action_row.addWidget(self.generate_btn)
        footer_v.addLayout(action_row)

        card_layout.addWidget(self.footer_box)
        outer.addWidget(self.card)

        self.setMinimumSize(820, 580)
        self.resize(DEFAULT_PANEL_WIDTH, DEFAULT_PANEL_HEIGHT)
        self._update_project_header()

    def _wire_signals(self) -> None:
        self.utf8_chk.toggled.connect(self._on_utf8_toggled)
        self.overwrite_chk.toggled.connect(lambda *_: self.save_cfg_timer.start(220))
        self.hidden_chk.toggled.connect(self._on_scan_option_toggled)
        self.tool_dir_chk.toggled.connect(self._on_scan_option_toggled)

        self.tree_selector.item_focused.connect(self._on_tree_item_focused)
        self.tree_selector.selection_changed.connect(self._update_counts_header)
        self.tree_selector.request_refresh.connect(lambda: self.scan_git_command(apply_preset=False))
        self.tree_selector.paths_added.connect(self._add_external_paths)
        self.tree_selector.request_rename.connect(self._on_request_rename)
        self.tree_selector.request_apply_icon_selected.connect(self._on_apply_item_icon_to_selected)
        self.tree_selector.request_reset_item.connect(self._on_reset_item)
        self.tree_selector.status_message.connect(self.set_status)

        self.inspector.item_modified.connect(self._on_inspector_item_modified)
        self.inspector.apply_icon_batch.connect(self._on_apply_icon_batch)
        self.inspector.confirm_save_requested.connect(self._focus_save_dir_for_confirm)

        self.save_dir_input.textChanged.connect(self._on_save_dir_changed)
        self.save_dir_input.returnPressed.connect(self.generate_shortcuts)

    # --------------------------------------------------------------------------
    # Theme & Transparency
    # --------------------------------------------------------------------------
    def _persist_config(self) -> None:
        self.cfg["transparency"] = self.transparency
        self.cfg["utf8_console"] = self.utf8_chk.isChecked()
        self.cfg["overwrite"] = self.overwrite_chk.isChecked()
        self.cfg["show_hidden"] = self.hidden_chk.isChecked()
        self.cfg["show_tool_dir"] = self.tool_dir_chk.isChecked()
        save_ui_config(self.cfg)

    def toggle_setting_panel(self) -> None:
        self.is_setting_open = not self.is_setting_open
        self.setting_panel.setVisible(self.is_setting_open)
        self._update_setting_btn_style()

    def _set_transparency_preset(self, val: int) -> None:
        v = clamp_transparency(val)
        if self.opacity_slider.value() != v:
            self.opacity_slider.setValue(v)
        else:
            self.apply_transparency_theme(v, save=True)

    def _update_setting_btn_style(self) -> None:
        variant = "rose_soft" if self.is_setting_open else "neutral"
        self.setting_btn.setStyleSheet(build_button_stylesheet(self.palette, variant, "4px 10px"))

    def apply_transparency_theme(self, transparency: int, save: bool = True) -> None:
        t = clamp_transparency(transparency)
        self.transparency = t
        p = compute_theme_palette(t)
        self.palette = p

        opacity_pct = 100 - t
        if t == 0:
            self.opacity_val_lbl.setText("0% (纯白底)")
        elif t == 95:
            self.opacity_val_lbl.setText("95% (最低5%可见)")
        else:
            self.opacity_val_lbl.setText(f"{t}% (可见{opacity_pct}%)")

        self.shadow_effect.setEnabled(not p.is_dark)

        self.card.setStyleSheet(f"""
            QWidget#mainCard {{
                {FONT_STYLE_BASE}
                background-color: {p.card_bg};
                border: {p.card_bd};
                border-radius: 12px;
            }}
        """)

        for name, frame in [("settingPanel", self.setting_panel), ("footerCard", self.footer_box)]:
            frame.setStyleSheet(f"""
                QFrame#{name} {{
                    background-color: {p.sub_card_bg};
                    border: {p.sub_card_bd};
                    border-radius: 9px;
                }}
            """)

        self.count_lbl.setStyleSheet(
            f"{FONT_STYLE_BASE} color: {p.count_fg}; background: {p.count_bg}; "
            f"border: {p.count_bd}; border-radius: 5px; padding: 3px 8px;"
        )
        self.project_badge.setStyleSheet(
            f"{FONT_STYLE_BASE} color: {p.org_accent}; background: {p.org_pill_bg}; "
            f"border-radius: 5px; padding: 3px 8px;"
        )
        self.preset_badge.setStyleSheet(
            f"{FONT_STYLE_BASE} color: {p.rose_accent}; background: {p.rose_pill_bg}; "
            f"border-radius: 5px; padding: 3px 8px;"
        )
        self.sp_title_lbl.setStyleSheet(f"{FONT_STYLE_BASE} color: {p.text_fg}; background: transparent;")
        self.mem_path_lbl.setStyleSheet(f"{FONT_STYLE_BASE} color: {p.muted_fg}; background: transparent;")
        self.lbl_save_title.setStyleSheet(f"{FONT_STYLE_BASE} color: {p.text_fg}; background: transparent;")
        self.opacity_val_lbl.setStyleSheet(
            f"{FONT_STYLE_BASE} color: {p.rose_accent}; background: {p.rose_pill_bg}; "
            f"border-radius: 5px; padding: 2px 7px;"
        )

        self.opacity_slider.setStyleSheet(build_slider_stylesheet(p))
        for btn, p_val in self.preset_buttons:
            btn.setStyleSheet(build_pill_stylesheet(p, active=(p_val == t), accent="rose"))

        chk_css = build_checkbox_stylesheet(p)
        for chk in (self.utf8_chk, self.overwrite_chk, self.hidden_chk, self.tool_dir_chk):
            chk.setStyleSheet(chk_css)

        self.save_dir_input.setStyleSheet(build_input_stylesheet(p))
        neutral_css = build_button_stylesheet(p, "neutral", "4px 9px")
        for b in (
            self.switch_proj_btn,
            self.btn_reset_save,
            self.btn_browse_save,
            self.btn_reload_preset,
            self.btn_save_preset_only,
            self.btn_clear_preset,
        ):
            b.setStyleSheet(neutral_css)

        self.min_btn.setStyleSheet(f"""
            QPushButton {{
                {FONT_STYLE_BASE} background-color: transparent; color: {p.muted_fg};
                border: none; border-radius: 6px;
            }}
            QPushButton:hover {{ background-color: {p.ctrl_hv}; color: {p.text_fg}; }}
        """)
        self.close_btn.setStyleSheet(f"""
            QPushButton {{
                {FONT_STYLE_BASE} background-color: transparent; color: {p.muted_fg};
                border: none; border-radius: 6px;
            }}
            QPushButton:hover {{ background-color: {p.rose_pill_bg}; color: {p.rose_accent}; }}
        """)

        self.quick_mem_btn.setStyleSheet(build_button_stylesheet(p, "orange", "7px 14px"))
        self.generate_btn.setStyleSheet(build_button_stylesheet(p, "rose", "7px 18px"))
        self.splitter.setStyleSheet("QSplitter::handle { background: transparent; }")

        self._update_setting_btn_style()
        self._update_save_mode_badge()
        self.tree_selector.apply_theme(p)
        self.inspector.apply_theme(p)
        self.set_status(self.status_lbl.text(), "muted", auto_reset=False)

        if save:
            self.save_cfg_timer.start(220)

    # --------------------------------------------------------------------------
    # Borderless Resize & Drag-to-Move
    # --------------------------------------------------------------------------
    def _detect_resize_edges(self, local_pos) -> str:
        x, y = local_pos.x(), local_pos.y()
        w, h = self.width(), self.height()
        m = self.RESIZE_MARGIN
        edges = ""
        if y <= m:
            edges += "T"
        elif y >= h - m:
            edges += "B"
        if x <= m:
            edges += "L"
        elif x >= w - m:
            edges += "R"
        return edges

    def _apply_edge_cursor(self, edges: str) -> None:
        if edges in ("TL", "BR"):
            self.setCursor(CURSOR_FDIAG)
        elif edges in ("TR", "BL"):
            self.setCursor(CURSOR_BDIAG)
        elif edges in ("L", "R"):
            self.setCursor(CURSOR_HOR)
        elif edges in ("T", "B"):
            self.setCursor(CURSOR_VER)
        else:
            self.unsetCursor()

    def eventFilter(self, obj, event):
        if not self.isVisible():
            return super().eventFilter(obj, event)

        ev_type = event.type()
        if ev_type in (EV_MOVE, EV_PRESS, EV_RELEASE):
            if isinstance(obj, QWidget) and (obj is self or self.isAncestorOf(obj)):
                gpos = event_global_pos(event)
                lpos = self.mapFromGlobal(gpos)

                if ev_type == EV_MOVE:
                    if self._resize_edges and self._resize_start_geom is not None:
                        dx = gpos.x() - self._resize_start_global.x()
                        dy = gpos.y() - self._resize_start_global.y()
                        geom = QRect(self._resize_start_geom)
                        min_w, min_h = self.minimumWidth(), self.minimumHeight()
                        if "L" in self._resize_edges:
                            geom.setLeft(min(geom.right() - min_w + 1, geom.left() + dx))
                        if "R" in self._resize_edges:
                            geom.setWidth(max(min_w, geom.width() + dx))
                        if "T" in self._resize_edges:
                            geom.setTop(min(geom.bottom() - min_h + 1, geom.top() + dy))
                        if "B" in self._resize_edges:
                            geom.setHeight(max(min_h, geom.height() + dy))
                        self.setGeometry(geom)
                        return True

                    if self._is_dragging and self._drag_offset is not None:
                        self.move(gpos - self._drag_offset)
                        return True

                    self._apply_edge_cursor(self._detect_resize_edges(lpos))

                elif ev_type == EV_PRESS and event.button() == MOUSE_LEFT:
                    edges = self._detect_resize_edges(lpos)
                    if edges:
                        self._resize_edges = edges
                        self._resize_start_global = gpos
                        self._resize_start_geom = QRect(self.geometry())
                        return True

                    child = self.childAt(lpos)
                    draggable = (
                        child is None
                        or child is self.card
                        or child is self.header_bar
                        or (self.header_bar.isAncestorOf(child) and not isinstance(child, (QPushButton, QComboBox)))
                    )
                    if draggable:
                        self._is_dragging = True
                        self._drag_offset = gpos - self.frameGeometry().topLeft()
                        return True

                elif ev_type == EV_RELEASE and event.button() == MOUSE_LEFT:
                    if self._resize_edges:
                        self._resize_edges = ""
                        self._resize_start_global = None
                        self._resize_start_geom = None
                        return True
                    if self._is_dragging:
                        self._is_dragging = False
                        self._drag_offset = None
                        return True

        return super().eventFilter(obj, event)

    # --------------------------------------------------------------------------
    # Preset UI State & Project Header
    # --------------------------------------------------------------------------
    def _update_project_header(self) -> None:
        self.project_badge.setText(f"项目: {self.project_root.name}")
        self.project_badge.setToolTip(str(self.project_root))
        self._refresh_preset_ui_state()

    def _refresh_preset_ui_state(self) -> None:
        preset_path = resolve_preset_path(self.project_root)
        preset = load_preset(self.project_root)

        if preset is not None:
            cnt = len(preset.get("items", []))
            updated = preset.get("updated_at", "")
            self.preset_badge.setText(f"已记忆 {cnt} 项")
            self.preset_badge.setToolTip(f"记忆文件: {preset_path}\n上次保存: {updated}")
            self.preset_badge.setVisible(True)
            self.quick_mem_btn.setText(f"按记忆一键生成 ({cnt})")
            self.quick_mem_btn.setVisible(True)
            self.btn_reload_preset.setEnabled(True)
            self.btn_clear_preset.setEnabled(True)
            self.mem_path_lbl.setText(f"记忆文件: {preset_path.name}（已保存 {cnt} 项 · {updated}）")
        else:
            self.preset_badge.setVisible(False)
            self.quick_mem_btn.setVisible(False)
            self.btn_reload_preset.setEnabled(False)
            self.btn_clear_preset.setEnabled(False)
            self.mem_path_lbl.setText(f"记忆文件: 尚未保存（首次生成后将自动写入 {PRESET_FILENAME}）")

    def _resolve_save_dir(self) -> Optional[Path]:
        raw = self.save_dir_input.text().strip()
        if not raw:
            return self.project_root.resolve()
        try:
            return Path(raw).expanduser().resolve()
        except OSError:
            return None

    def _lnk_exists_for(self, item: TargetItem) -> bool:
        save_dir = self._resolve_save_dir()
        if not save_dir or not item.shortcut_name.strip():
            return False
        return (save_dir / f"{item.shortcut_name.strip()}.lnk").exists()

    def _update_save_mode_badge(self) -> None:
        p = self.palette
        raw = self.save_dir_input.text().strip()
        save_dir = self._resolve_save_dir()
        if save_dir is None:
            self.save_mode_pill.setText("路径无效")
            self.save_mode_pill.setStyleSheet(
                f"{FONT_STYLE_BASE} color: #FFFFFF; background: {PALETTE_ROSE}; border-radius: 5px; padding: 3px 8px;"
            )
            return

        if not raw or save_dir == self.project_root.resolve():
            self.save_mode_pill.setText("Git 便携 · 相对路径")
            self.save_mode_pill.setStyleSheet(
                f"{FONT_STYLE_BASE} color: {p.rose_accent}; background: {p.rose_pill_bg}; border-radius: 5px; padding: 3px 8px;"
            )
        else:
            self.save_mode_pill.setText("外部目录 · 锁定项目根目录")
            self.save_mode_pill.setStyleSheet(
                f"{FONT_STYLE_BASE} color: {p.org_accent}; background: {p.org_pill_bg}; border-radius: 5px; padding: 3px 8px;"
            )

    def _update_counts_header(self) -> None:
        total = len(self.items)
        selected = sum(1 for x in self.items.values() if x.selected)
        scripts = sum(1 for x in self.items.values() if x.is_script)
        self.count_lbl.setText(f"已选 {selected} / {total} 项 ({scripts} 脚本)")

    # --------------------------------------------------------------------------
    # Scanning, Preset Loading & Editing
    # --------------------------------------------------------------------------
    def scan_git_command(self, focus_item_id: Optional[str] = None, apply_preset: bool = False) -> None:
        old_items = {} if apply_preset else dict(self.items)
        self.items.clear()

        def_icon = default_icon_path(self.project_root)
        paths = scan_git_command_paths(
            self.project_root,
            show_hidden=self.hidden_chk.isChecked(),
            show_tool_dir=self.tool_dir_chk.isChecked(),
        )

        git_cmd_dir = self.project_root / ".git-command"
        seen: set[str] = set()

        for path in paths:
            key = str(path.resolve()).lower()
            if key in seen:
                continue
            seen.add(key)
            item = create_target_item(path, self.project_root, def_icon, is_external=False)
            if key in old_items:
                prev = old_items[key]
                item.selected = prev.selected
                item.shortcut_name = prev.shortcut_name
                item.run_mode = prev.run_mode
                item.icon_value = prev.icon_value
            self.items[key] = item

        for ep in list(self.extra_paths):
            if not ep.exists():
                continue
            key = str(ep.resolve()).lower()
            if key in seen:
                continue
            seen.add(key)
            item = create_target_item(ep, self.project_root, def_icon, is_external=True, preselect=True)
            if key in old_items:
                prev = old_items[key]
                item.selected = prev.selected
                item.shortcut_name = prev.shortcut_name
                item.run_mode = prev.run_mode
                item.icon_value = prev.icon_value
            self.items[key] = item

        loaded_preset_msg: Optional[str] = None
        if apply_preset:
            preset = load_preset(self.project_root)
            if preset is not None:
                saved_dir, utf8_val, overwrite_val, matched, missing = apply_preset_to_items(
                    project_root=self.project_root,
                    items=self.items,
                    extra_paths=self.extra_paths,
                    preset=preset,
                )
                self.save_dir_input.blockSignals(True)
                self.save_dir_input.setText(str(saved_dir))
                self.save_dir_input.blockSignals(False)
                self._update_save_mode_badge()

                self.utf8_chk.blockSignals(True)
                self.utf8_chk.setChecked(utf8_val)
                self.utf8_chk.blockSignals(False)
                self.inspector.set_utf8_console(utf8_val)

                self.overwrite_chk.blockSignals(True)
                self.overwrite_chk.setChecked(overwrite_val)
                self.overwrite_chk.blockSignals(False)

                miss_note = f"（{len(missing)} 项源文件已不存在）" if missing else ""
                loaded_preset_msg = f"已自动载入上次记忆：选中 {matched} 项{miss_note} · 按 Enter 可直接一键生成"

        self.tree_selector.load_items(
            self.items,
            self.project_root,
            self._lnk_exists_for,
            focus_item_id=focus_item_id,
        )
        self._update_counts_header()
        self._refresh_preset_ui_state()

        if not git_cmd_dir.is_dir():
            self.set_status(f"未找到 {git_cmd_dir} · 请点击切换项目或直接拖入文件", "warn", auto_reset=False)
        elif loaded_preset_msg:
            self.set_status(loaded_preset_msg, "ok", auto_reset=False)
        else:
            scripts = sum(1 for x in self.items.values() if x.is_script)
            self.set_status(f"已递归扫描 .git-command：发现 {len(self.items)} 项（含 {scripts} 个脚本）", "muted")

    def reload_saved_preset(self) -> None:
        self.extra_paths.clear()
        self.scan_git_command(apply_preset=True)

    def save_current_preset_only(self) -> None:
        selected_items = [it for it in self.items.values() if it.selected]
        if not selected_items:
            self.set_status("当前未勾选任何项，无法保存记忆", "warn")
            return
        save_dir = self._resolve_save_dir() or self.project_root.resolve()
        preset_file = save_preset(
            project_root=self.project_root,
            save_dir=save_dir,
            selected_items=selected_items,
            utf8_console=self.utf8_chk.isChecked(),
            overwrite=self.overwrite_chk.isChecked(),
        )
        self._refresh_preset_ui_state()
        self.set_status(f"已保存 {len(selected_items)} 项记忆至 {preset_file.name}", "ok")

    def clear_saved_preset(self) -> None:
        if delete_preset(self.project_root):
            self._refresh_preset_ui_state()
            self.set_status(f"已清除 {PRESET_FILENAME} 记忆配置", "ok")
        else:
            self.set_status("未找到可清除的记忆文件", "muted")

    def _add_external_paths(self, paths: list[Path]) -> None:
        def_icon = default_icon_path(self.project_root)
        added = 0
        last_id: Optional[str] = None
        for p in paths:
            rp = p.resolve()
            if not rp.exists():
                continue
            key = str(rp).lower()
            if key in self.items:
                self.items[key].selected = True
                last_id = key
                continue
            if rp not in self.extra_paths:
                self.extra_paths.append(rp)
            self.items[key] = create_target_item(rp, self.project_root, def_icon, is_external=True, preselect=True)
            added += 1
            last_id = key

        self.tree_selector.load_items(self.items, self.project_root, self._lnk_exists_for, focus_item_id=last_id)
        self._update_counts_header()
        if added > 0:
            self.set_status(f"已添加并勾选 {added} 个项目", "ok")
        elif last_id:
            self.set_status("目标已在文件树中，已为你勾选", "muted")

    def _on_utf8_toggled(self, checked: bool) -> None:
        self.inspector.set_utf8_console(checked)
        self.save_cfg_timer.start(220)

    def _on_scan_option_toggled(self) -> None:
        self.save_cfg_timer.start(220)
        self.scan_git_command(apply_preset=False)

    def _on_tree_item_focused(self, item_id: str) -> None:
        item = self.items.get(item_id) if item_id else None
        self.inspector.load_item(item)

    def _on_inspector_item_modified(self, item_id: str) -> None:
        self.tree_selector.refresh_single_item(item_id)

    def _on_request_rename(self, item_id: str) -> None:
        if item_id in self.items:
            self.inspector.load_item(self.items[item_id])
            self.inspector.focus_rename()

    def _on_apply_item_icon_to_selected(self, item_id: str) -> None:
        if item_id in self.items:
            self._on_apply_icon_batch(self.items[item_id].icon_value, only_selected=True)

    def _on_apply_icon_batch(self, icon_value: str, only_selected: bool) -> None:
        cnt = 0
        for it in self.items.values():
            if only_selected and not it.selected:
                continue
            it.icon_value = icon_value
            cnt += 1
        self.tree_selector.refresh_all_status_badges()
        cur_id = self.tree_selector.current_item_id()
        if cur_id in self.items:
            self.inspector.load_item(self.items[cur_id])
        scope = "已选项目" if only_selected else "全部项目"
        self.set_status(f"已将当前图标应用到 {cnt} 个{scope}", "ok")

    def _on_reset_item(self, item_id: str) -> None:
        if item_id not in self.items:
            return
        it = self.items[item_id]
        it.shortcut_name = it.default_name
        it.run_mode = MODE_AUTO
        it.icon_value = default_icon_path(self.project_root)
        self.tree_selector.refresh_single_item(item_id)
        if self.tree_selector.current_item_id() == item_id:
            self.inspector.load_item(it)

    def _on_save_dir_changed(self) -> None:
        self._update_save_mode_badge()
        self.tree_selector.refresh_all_status_badges()

    def browse_project_root(self) -> None:
        chosen = QFileDialog.getExistingDirectory(self, "选择项目根目录", str(self.project_root))
        if not chosen:
            return
        self.project_root = Path(chosen).resolve()
        self.extra_paths.clear()
        self._update_project_header()
        self.save_dir_input.setText(str(self.project_root))
        self.inspector.set_project_root(self.project_root)
        self.scan_git_command(apply_preset=True)

    def reset_save_dir(self) -> None:
        self.save_dir_input.setText(str(self.project_root))
        self.save_dir_input.setFocus()

    def browse_save_dir(self) -> None:
        start = str(self._resolve_save_dir() or self.project_root)
        chosen = QFileDialog.getExistingDirectory(self, "选择快捷方式保存目录", start)
        if chosen:
            self.save_dir_input.setText(str(Path(chosen).resolve()))
            self.save_dir_input.setFocus()

    def _focus_save_dir_for_confirm(self) -> None:
        self.save_dir_input.setFocus()
        self.save_dir_input.end(False)
        self.set_status("再次按 Enter 确认保存到当前路径（留空默认项目根目录）", "muted")

    # --------------------------------------------------------------------------
    # Status Banner, Popup Notification & Generation
    # --------------------------------------------------------------------------
    def set_status(self, text: str, level: str = "muted", auto_reset: bool = True) -> None:
        p = self.palette
        if level == "ok":
            col = p.org_accent
        elif level == "warn":
            col = p.rose_accent
        else:
            col = p.muted_fg

        self.status_lbl.setText(text)
        self.status_lbl.setStyleSheet(f"{FONT_STYLE_BASE} color: {col}; background: transparent;")
        if auto_reset and level != "muted":
            self.status_timer.start(4500)
        else:
            self.status_timer.stop()

    def _show_result_popup(
        self,
        title: str,
        summary: str,
        save_dir: Optional[Path] = None,
        created_names: Optional[list[str]] = None,
        skipped_names: Optional[list[str]] = None,
        missing_targets: Optional[list[str]] = None,
        preset_note: str = "",
        is_error: bool = False,
    ) -> None:
        dlg = GenerationResultDialog(
            parent=self,
            palette=self.palette,
            title=title,
            summary=summary,
            save_dir=save_dir,
            created_names=created_names or [],
            skipped_names=skipped_names or [],
            missing_targets=missing_targets or [],
            preset_note=preset_note,
            is_error=is_error,
        )
        exec_dialog(dlg)

    def run_quick_memory_generate(self) -> None:
        """One-click regenerate directly from saved shortcuts_preset.json."""
        res = quick_generate_from_preset(self.project_root)
        self.tree_selector.refresh_all_status_badges()

        if not res.ok:
            self.set_status(res.summary, "warn", auto_reset=False)
            send_companion_toast(res.summary, 2400, "error")
            self._show_result_popup(
                title="一键生成失败",
                summary=res.summary,
                save_dir=res.save_dir,
                missing_targets=res.missing_targets,
                is_error=True,
            )
            return

        self.set_status(res.summary, "ok", auto_reset=False)
        send_companion_toast(res.summary, 2200, "info")
        self._show_result_popup(
            title="按记忆一键生成完成",
            summary=res.summary,
            save_dir=res.save_dir,
            created_names=res.created_names,
            skipped_names=res.skipped_names,
            missing_targets=res.missing_targets,
            preset_note=f"读取自: .git-command/create-shortcut/{PRESET_FILENAME}",
            is_error=False,
        )

    def generate_shortcuts(self) -> None:
        selected_items = [it for it in self.items.values() if it.selected]
        if not selected_items:
            msg = "请至少在左侧文件树中勾选一个脚本或文件夹。"
            self.set_status(msg, "warn")
            self._show_result_popup("未选择目标", msg, is_error=True)
            return

        # Empty save location -> default to project root on Enter
        raw_save = self.save_dir_input.text().strip()
        if not raw_save:
            save_dir = self.project_root.resolve()
            self.save_dir_input.setText(str(save_dir))
        else:
            save_dir = self._resolve_save_dir()
            if save_dir is None:
                msg = "保存位置路径格式无效，请检查路径输入。"
                self.set_status(msg, "warn")
                self._show_result_popup("路径无效", msg, is_error=True)
                return

        if not save_dir.exists():
            try:
                save_dir.mkdir(parents=True, exist_ok=True)
            except OSError as exc:
                msg = f"无法创建保存目录：{exc}"
                self.set_status(msg, "warn")
                self._show_result_popup("创建目录失败", msg, is_error=True)
                return

        # Validate names & duplicates
        seen_names: set[str] = set()
        for item in selected_items:
            name = item.shortcut_name.strip()
            if name.lower().endswith(".lnk"):
                name = name[:-4].strip()
                item.shortcut_name = name
            if not name:
                msg = f"快捷方式名称不能为空：{item.display_path}"
                self.set_status(msg, "warn")
                self._show_result_popup("名称为空", msg, is_error=True)
                return
            if INVALID_FILENAME_RE.search(name):
                msg = f"名称包含 Windows 非法字符：{name}"
                self.set_status(msg, "warn")
                self._show_result_popup("名称非法", msg, is_error=True)
                return
            low = name.lower()
            if low in seen_names:
                msg = f"存在重名的快捷方式“{name}”，请在右侧修改其中一个名称后再生成。"
                self.set_status(msg, "warn", auto_reset=False)
                self._show_result_popup("快捷方式重名", msg, is_error=True)
                return
            seen_names.add(low)

        tasks: list[dict[str, object]] = []
        created_names: list[str] = []
        skipped_names: list[str] = []

        try:
            for item in selected_items:
                lnk_file = save_dir / f"{item.shortcut_name}.lnk"
                if lnk_file.exists() and not self.overwrite_chk.isChecked():
                    skipped_names.append(lnk_file.name)
                    continue
                task = build_shortcut_task(
                    item=item,
                    project_root=self.project_root,
                    save_dir=save_dir,
                    utf8_console=self.utf8_chk.isChecked(),
                )
                tasks.append(task)
                created_names.append(lnk_file.name)

            if tasks:
                create_windows_shortcuts(tasks)
        except Exception as exc:
            msg = f"创建快捷方式时出错：{exc}"
            self.set_status(msg, "warn", auto_reset=False)
            send_companion_toast(f"快捷方式生成失败: {exc}", 2600, "error")
            self._show_result_popup("生成失败", msg, save_dir=save_dir, is_error=True)
            return

        # Automatically save remembered selections under create-shortcut/shortcuts_preset.json
        preset_note = ""
        try:
            preset_file = save_preset(
                project_root=self.project_root,
                save_dir=save_dir,
                selected_items=selected_items,
                utf8_console=self.utf8_chk.isChecked(),
                overwrite=self.overwrite_chk.isChecked(),
            )
            self._refresh_preset_ui_state()
            preset_note = f"已记忆本次 {len(selected_items)} 项配置 → {preset_file.name}（下次可直接一键生成）"
        except Exception as exc:
            preset_note = f"记忆配置写入失败: {exc}"

        self.tree_selector.refresh_all_status_badges()

        if created_names:
            skip_note = f"，跳过已存在 {len(skipped_names)} 个" if skipped_names else ""
            summary = f"已成功生成 {len(created_names)} 个快捷方式{skip_note}。"
            self.set_status(f"{summary} → {save_dir}", "ok", auto_reset=False)
            send_companion_toast(f"已生成 {len(created_names)} 个快捷方式并记忆配置", 2200, "info")
            self._show_result_popup(
                title="快捷方式生成完成",
                summary=summary,
                save_dir=save_dir,
                created_names=created_names,
                skipped_names=skipped_names,
                preset_note=preset_note,
                is_error=False,
            )
        else:
            summary = f"选中的 {len(skipped_names)} 个快捷方式均已存在，且当前未开启“覆盖同名 .lnk”。"
            self.set_status(summary, "warn", auto_reset=False)
            send_companion_toast("未生成新快捷方式（目标均已存在）", 2000, "info")
            self._show_result_popup(
                title="未生成新文件",
                summary=summary,
                save_dir=save_dir,
                created_names=[],
                skipped_names=skipped_names,
                preset_note=preset_note,
                is_error=False,
            )

    # --------------------------------------------------------------------------
    # Keyboard Shortcuts
    # --------------------------------------------------------------------------
    def keyPressEvent(self, event) -> None:
        key = event.key()
        mods = event.modifiers()

        if key == KEY_ESC:
            if self.tree_selector.search_input.text():
                self.tree_selector.search_input.clear()
            elif self.is_setting_open:
                self.toggle_setting_panel()
            else:
                self.close()
            return

        if (mods & MOD_CTRL) and key in (KEY_RETURN, KEY_ENTER):
            self.generate_shortcuts()
            return

        if (mods & MOD_CTRL) and key == KEY_F:
            self.tree_selector.search_input.setFocus()
            self.tree_selector.search_input.selectAll()
            return

        if (mods & MOD_CTRL) and key == KEY_A and not isinstance(self.focusWidget(), QLineEdit):
            self.tree_selector.batch_select("visible_all")
            return

        if key == KEY_F2:
            self.inspector.focus_rename()
            return

        super().keyPressEvent(event)