# -*- coding: utf-8 -*-
"""
Right Inspector Panel:
- Shortcut naming (F2 / Enter jump to save confirmation)
- Run / Open mode segmented selector (Auto / Terminal Stay-Open / Direct Open)
- Icon preview, built-in Windows icon presets, file browser & .icons quick gallery
- Live command-line preview
"""

from __future__ import annotations

from pathlib import Path
from typing import Optional

from .config import (
    FONT_STYLE_BASE,
    MODE_AUTO,
    MODE_OPEN,
    MODE_TERMINAL,
    PALETTE_ROSE,
    SYSTEM_ICON_PRESETS,
)
from .models import TargetItem
from .qt_compat import (
    ALIGN_CENTER,
    ALIGN_LEFT_VCENTER,
    CURSOR_POINTER,
    KEEP_ASPECT,
    NO_FRAME,
    QComboBox,
    QFileDialog,
    QFrame,
    QHBoxLayout,
    QIcon,
    QLabel,
    QLineEdit,
    QPixmap,
    QPushButton,
    QScrollArea,
    QSize,
    QVBoxLayout,
    QWidget,
    SMOOTH_TRANSFORM,
    Signal,
    make_ui_font,
)
from .shortcut_engine import build_command_preview, default_icon_path
from .theme import (
    ThemePalette,
    build_button_stylesheet,
    build_combo_stylesheet,
    build_input_stylesheet,
    build_pill_stylesheet,
)


class InspectorPanel(QFrame):
    item_modified = Signal(str)              # item_id
    apply_icon_batch = Signal(str, bool)     # icon_value, only_selected
    confirm_save_requested = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("inspectorCard")

        self.project_root: Path = Path.cwd()
        self.current_item: Optional[TargetItem] = None
        self.utf8_console: bool = True
        self.palette: Optional[ThemePalette] = None
        self._updating: bool = False
        self._icon_chips: list[tuple[QPushButton, str]] = []

        self._init_ui()

    def _init_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 10, 12, 10)
        layout.setSpacing(8)

        # Header
        hdr = QHBoxLayout()
        hdr.setContentsMargins(0, 0, 0, 0)
        self.title_lbl = QLabel("当前项配置", self)
        self.title_lbl.setFont(make_ui_font(9.2, bold=True))
        self.type_pill = QLabel("--", self)
        self.type_pill.setFont(make_ui_font(7.5, bold=True))
        hdr.addWidget(self.title_lbl)
        hdr.addStretch(1)
        hdr.addWidget(self.type_pill)
        layout.addLayout(hdr)

        self.path_lbl = QLabel("请在左侧文件树选择一项", self)
        self.path_lbl.setFont(make_ui_font(7.7))
        self.path_lbl.setWordWrap(True)
        layout.addWidget(self.path_lbl)

        # Shortcut Name
        self.lbl_name = QLabel("快捷方式名称 (F2 · 无需填 .lnk)", self)
        self.lbl_name.setFont(make_ui_font(8.0, bold=True))
        layout.addWidget(self.lbl_name)

        name_row = QHBoxLayout()
        name_row.setContentsMargins(0, 0, 0, 0)
        name_row.setSpacing(5)

        self.name_input = QLineEdit(self)
        self.name_input.setFont(make_ui_font(9.0, bold=True))
        self.name_input.setPlaceholderText("输入快捷方式名称")
        self.name_input.textChanged.connect(self._on_name_changed)
        self.name_input.returnPressed.connect(self.confirm_save_requested.emit)

        self.btn_reset_name = QPushButton("还原", self)
        self.btn_reset_name.setCursor(CURSOR_POINTER)
        self.btn_reset_name.setFont(make_ui_font(7.8, bold=True))
        self.btn_reset_name.clicked.connect(self._reset_name)

        name_row.addWidget(self.name_input, 1)
        name_row.addWidget(self.btn_reset_name)
        layout.addLayout(name_row)

        # Run Mode Segmented Buttons
        self.lbl_mode = QLabel("运行 / 打开方式", self)
        self.lbl_mode.setFont(make_ui_font(8.0, bold=True))
        layout.addWidget(self.lbl_mode)

        mode_row = QHBoxLayout()
        mode_row.setContentsMargins(0, 0, 0, 0)
        mode_row.setSpacing(5)
        self.mode_buttons: dict[str, QPushButton] = {}
        for m_key, m_txt in [
            (MODE_AUTO, "自动判断"),
            (MODE_TERMINAL, "终端常驻"),
            (MODE_OPEN, "直接打开"),
        ]:
            btn = QPushButton(m_txt, self)
            btn.setCursor(CURSOR_POINTER)
            btn.setFont(make_ui_font(7.8, bold=True))
            btn.clicked.connect(lambda checked=False, k=m_key: self._on_mode_clicked(k))
            mode_row.addWidget(btn, 1)
            self.mode_buttons[m_key] = btn
        layout.addLayout(mode_row)

        # Icon Controls
        self.lbl_icon = QLabel("图标设置 (默认 .git-command/.icons/github.png)", self)
        self.lbl_icon.setFont(make_ui_font(8.0, bold=True))
        layout.addWidget(self.lbl_icon)

        icon_top = QHBoxLayout()
        icon_top.setContentsMargins(0, 0, 0, 0)
        icon_top.setSpacing(8)

        self.icon_preview = QLabel(self)
        self.icon_preview.setObjectName("iconPreviewBox")
        self.icon_preview.setFixedSize(46, 46)
        self.icon_preview.setAlignment(ALIGN_CENTER)

        icon_right = QVBoxLayout()
        icon_right.setContentsMargins(0, 0, 0, 0)
        icon_right.setSpacing(5)

        self.icon_preset_combo = QComboBox(self)
        self.icon_preset_combo.setFont(make_ui_font(7.8))
        self.icon_preset_combo.setCursor(CURSOR_POINTER)
        for lbl, val in SYSTEM_ICON_PRESETS:
            self.icon_preset_combo.addItem(lbl, val)
        self.icon_preset_combo.currentIndexChanged.connect(self._on_preset_changed)

        icon_path_row = QHBoxLayout()
        icon_path_row.setContentsMargins(0, 0, 0, 0)
        icon_path_row.setSpacing(5)
        self.icon_path_input = QLineEdit(self)
        self.icon_path_input.setFont(make_ui_font(7.8))
        self.icon_path_input.setPlaceholderText("图标路径 (.png / .ico / .exe / dll,index)")
        self.icon_path_input.textChanged.connect(self._on_icon_path_changed)

        self.btn_browse_icon = QPushButton("浏览", self)
        self.btn_browse_icon.setCursor(CURSOR_POINTER)
        self.btn_browse_icon.setFont(make_ui_font(7.6, bold=True))
        self.btn_browse_icon.clicked.connect(self._browse_icon)

        icon_path_row.addWidget(self.icon_path_input, 1)
        icon_path_row.addWidget(self.btn_browse_icon)

        icon_right.addWidget(self.icon_preset_combo)
        icon_right.addLayout(icon_path_row)

        icon_top.addWidget(self.icon_preview)
        icon_top.addLayout(icon_right, 1)
        layout.addLayout(icon_top)

        # .icons Quick Gallery
        self.lbl_gallery = QLabel(".icons 快捷图标库 (点击切换)", self)
        self.lbl_gallery.setFont(make_ui_font(7.6, bold=True))
        layout.addWidget(self.lbl_gallery)

        self.gallery_scroll = QScrollArea(self)
        self.gallery_scroll.setWidgetResizable(True)
        self.gallery_scroll.setFixedHeight(56)
        self.gallery_scroll.setFrameShape(NO_FRAME)

        self.gallery_container = QWidget()
        self.gallery_layout = QHBoxLayout(self.gallery_container)
        self.gallery_layout.setContentsMargins(2, 2, 2, 2)
        self.gallery_layout.setSpacing(6)
        self.gallery_scroll.setWidget(self.gallery_container)
        layout.addWidget(self.gallery_scroll)

        icon_btns = QHBoxLayout()
        icon_btns.setContentsMargins(0, 0, 0, 0)
        icon_btns.setSpacing(5)

        self.btn_default_icon = QPushButton("默认 github.png", self)
        self.btn_apply_sel = QPushButton("应用到已选", self)
        self.btn_apply_all = QPushButton("应用到全部", self)
        for b in (self.btn_default_icon, self.btn_apply_sel, self.btn_apply_all):
            b.setCursor(CURSOR_POINTER)
            b.setFont(make_ui_font(7.6, bold=True))
        self.btn_default_icon.clicked.connect(self._reset_icon)
        self.btn_apply_sel.clicked.connect(
            lambda: self.apply_icon_batch.emit(self.icon_path_input.text().strip(), True)
        )
        self.btn_apply_all.clicked.connect(
            lambda: self.apply_icon_batch.emit(self.icon_path_input.text().strip(), False)
        )
        icon_btns.addWidget(self.btn_default_icon)
        icon_btns.addWidget(self.btn_apply_sel)
        icon_btns.addWidget(self.btn_apply_all)
        layout.addLayout(icon_btns)

        # Command Preview
        self.lbl_cmd = QLabel("快捷方式命令预览", self)
        self.lbl_cmd.setFont(make_ui_font(7.8, bold=True))
        layout.addWidget(self.lbl_cmd)

        self.cmd_preview = QLabel("--", self)
        self.cmd_preview.setObjectName("cmdPreview")
        self.cmd_preview.setFont(make_ui_font(7.4))
        self.cmd_preview.setWordWrap(True)
        self.cmd_preview.setMinimumHeight(60)
        self.cmd_preview.setAlignment(ALIGN_LEFT_VCENTER)
        layout.addWidget(self.cmd_preview)

        layout.addStretch(1)

    # --------------------------------------------------------------------------
    # Public API
    # --------------------------------------------------------------------------
    def set_project_root(self, project_root: Path) -> None:
        self.project_root = project_root
        self.rebuild_icon_gallery()

    def set_utf8_console(self, enabled: bool) -> None:
        self.utf8_console = enabled
        self._update_cmd_preview()

    def focus_rename(self) -> None:
        if self.current_item is not None:
            self.name_input.setFocus()
            self.name_input.selectAll()

    def load_item(self, item: Optional[TargetItem]) -> None:
        self._updating = True
        try:
            self.current_item = item
            if item is None:
                self.type_pill.setText("--")
                self.path_lbl.setText("当前列表无选中项")
                self.name_input.clear()
                self.icon_path_input.clear()
                self.icon_preview.setPixmap(QPixmap())
                self.icon_preview.setText("--")
                self.cmd_preview.setText("--")
                self._refresh_mode_styles()
                self._refresh_gallery_chip_styles()
                return

            self.type_pill.setText(item.runner_tag)
            self.path_lbl.setText(item.display_path)
            self.name_input.setText(item.shortcut_name)
            self.icon_path_input.setText(item.icon_value)

            matched_idx = 0
            for idx, (_lbl, val) in enumerate(SYSTEM_ICON_PRESETS):
                if val and val.lower() == item.icon_value.lower():
                    matched_idx = idx
                    break
            self.icon_preset_combo.setCurrentIndex(matched_idx)

            self._refresh_mode_styles()
            self._update_icon_preview(item.icon_value)
            self._refresh_gallery_chip_styles()
            self._update_cmd_preview()
        finally:
            self._updating = False

    def rebuild_icon_gallery(self) -> None:
        while self.gallery_layout.count():
            child = self.gallery_layout.takeAt(0)
            if child.widget():
                child.widget().deleteLater()
        self._icon_chips.clear()

        icons_dir = self.project_root / ".git-command" / ".icons"
        found: list[Path] = []
        if icons_dir.is_dir():
            for p in sorted(icons_dir.iterdir(), key=lambda x: (x.name.lower() != "github.png", x.name.lower())):
                if p.is_file() and p.suffix.lower() in {".png", ".ico", ".jpg", ".jpeg", ".bmp"}:
                    found.append(p)

        if not found:
            lbl = QLabel("未在 .git-command/.icons 中发现图标文件", self.gallery_container)
            lbl.setFont(make_ui_font(7.5))
            lbl.setStyleSheet(f"{FONT_STYLE_BASE} color: #8E8E98; background: transparent;")
            self.gallery_layout.addWidget(lbl)
            self.gallery_layout.addStretch(1)
            return

        for p in found:
            btn = QPushButton(self.gallery_container)
            btn.setFixedSize(38, 38)
            btn.setCursor(CURSOR_POINTER)
            btn.setToolTip(f"{p.name} (点击设为当前项图标)")
            ico = QIcon(str(p))
            if not ico.isNull():
                btn.setIcon(ico)
                btn.setIconSize(QSize(24, 24))
            else:
                btn.setText(p.suffix.upper().lstrip("."))
            path_str = str(p.resolve())
            btn.clicked.connect(lambda checked=False, ps=path_str: self._pick_gallery_icon(ps))
            self.gallery_layout.addWidget(btn)
            self._icon_chips.append((btn, path_str))

        self.gallery_layout.addStretch(1)
        self._refresh_gallery_chip_styles()

    # --------------------------------------------------------------------------
    # Theme Application
    # --------------------------------------------------------------------------
    def apply_theme(self, p: ThemePalette) -> None:
        self.palette = p
        self.setStyleSheet(f"""
            QFrame#inspectorCard {{
                background-color: {p.sub_card_bg};
                border: {p.sub_card_bd};
                border-radius: 9px;
            }}
        """)

        for lbl in (
            self.title_lbl,
            self.lbl_name,
            self.lbl_mode,
            self.lbl_icon,
            self.lbl_gallery,
            self.lbl_cmd,
        ):
            lbl.setStyleSheet(f"{FONT_STYLE_BASE} color: {p.text_fg}; background: transparent;")

        self.path_lbl.setStyleSheet(f"{FONT_STYLE_BASE} color: {p.muted_fg}; background: transparent;")
        self.type_pill.setStyleSheet(
            f"{FONT_STYLE_BASE} color: {p.rose_accent}; background: {p.rose_pill_bg}; "
            f"border-radius: 5px; padding: 2px 7px;"
        )

        self.icon_preview.setStyleSheet(f"""
            QLabel#iconPreviewBox {{
                {FONT_STYLE_BASE}
                background-color: {p.ctrl_bg};
                color: {p.muted_fg};
                border: {p.sub_card_bd};
                border-radius: 8px;
            }}
        """)
        self.cmd_preview.setStyleSheet(f"""
            QLabel#cmdPreview {{
                {FONT_STYLE_BASE}
                background-color: {p.ctrl_bg};
                color: {p.muted_fg};
                border-radius: 7px;
                padding: 7px 9px;
            }}
        """)

        input_css = build_input_stylesheet(p)
        self.name_input.setStyleSheet(input_css)
        self.icon_path_input.setStyleSheet(input_css)
        self.icon_preset_combo.setStyleSheet(build_combo_stylesheet(p))

        neutral_css = build_button_stylesheet(p, "neutral", "4px 8px")
        for b in (
            self.btn_reset_name,
            self.btn_browse_icon,
            self.btn_default_icon,
            self.btn_apply_sel,
            self.btn_apply_all,
        ):
            b.setStyleSheet(neutral_css)

        self.gallery_scroll.setStyleSheet(f"""
            QScrollArea {{ background: transparent; border: none; }}
            QScrollBar:horizontal {{ height: 4px; background: transparent; }}
            QScrollBar::handle:horizontal {{ background: {p.scroll_col}; border-radius: 2px; }}
            QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {{ width: 0px; }}
        """)
        self.gallery_container.setStyleSheet("background: transparent;")

        self._refresh_mode_styles()
        self._refresh_gallery_chip_styles()

    def _refresh_mode_styles(self) -> None:
        if not self.palette:
            return
        cur_mode = self.current_item.run_mode if self.current_item else MODE_AUTO
        for m_key, btn in self.mode_buttons.items():
            btn.setStyleSheet(build_pill_stylesheet(self.palette, active=(m_key == cur_mode), accent="orange"))

    def _refresh_gallery_chip_styles(self) -> None:
        if not self.palette:
            return
        p = self.palette
        cur_val = self.icon_path_input.text().strip()
        cur_norm = Path(cur_val).as_posix().lower() if (cur_val and "," not in cur_val) else ""

        for btn, path_str in self._icon_chips:
            is_active = bool(cur_norm) and (Path(path_str).as_posix().lower() == cur_norm)
            if is_active:
                btn.setStyleSheet(f"""
                    QPushButton {{
                        background-color: {p.rose_pill_bg};
                        border: 2px solid {PALETTE_ROSE};
                        border-radius: 7px;
                    }}
                """)
            else:
                btn.setStyleSheet(f"""
                    QPushButton {{
                        background-color: {p.ctrl_bg};
                        border: 1px solid transparent;
                        border-radius: 7px;
                    }}
                    QPushButton:hover {{ border: 1px solid {p.rose_accent}; }}
                """)

    # --------------------------------------------------------------------------
    # Internal Handlers
    # --------------------------------------------------------------------------
    def _update_icon_preview(self, icon_value: str) -> None:
        val = icon_value.strip()
        if not val:
            self.icon_preview.setPixmap(QPixmap())
            self.icon_preview.setText("默认")
            return
        if "," in val and not Path(val).exists():
            self.icon_preview.setPixmap(QPixmap())
            self.icon_preview.setText("SYS")
            return
        p = Path(val)
        if p.is_file():
            pm = QPixmap(str(p))
            if not pm.isNull():
                self.icon_preview.setText("")
                self.icon_preview.setPixmap(pm.scaled(32, 32, KEEP_ASPECT, SMOOTH_TRANSFORM))
                return
            self.icon_preview.setPixmap(QPixmap())
            self.icon_preview.setText(p.suffix.upper().lstrip(".") or "ICO")
        else:
            self.icon_preview.setPixmap(QPixmap())
            self.icon_preview.setText("缺失")

    def _update_cmd_preview(self) -> None:
        if self.current_item is None:
            self.cmd_preview.setText("--")
            return
        target, args, _ = build_command_preview(self.current_item, self.utf8_console)
        self.cmd_preview.setText(f"{target} {args}")

    def _on_name_changed(self, text: str) -> None:
        if self._updating or self.current_item is None:
            return
        self.current_item.shortcut_name = text.strip()
        self.item_modified.emit(self.current_item.item_id)

    def _reset_name(self) -> None:
        if self.current_item is None:
            return
        self.name_input.setText(self.current_item.default_name)

    def _on_mode_clicked(self, mode_key: str) -> None:
        if self.current_item is None:
            return
        self.current_item.run_mode = mode_key
        self._refresh_mode_styles()
        self._update_cmd_preview()
        self.item_modified.emit(self.current_item.item_id)

    def _on_preset_changed(self, index: int) -> None:
        if self._updating or self.current_item is None:
            return
        val = str(self.icon_preset_combo.itemData(index) or "")
        self.icon_path_input.setText(val if val else default_icon_path(self.project_root))

    def _on_icon_path_changed(self, text: str) -> None:
        if self._updating or self.current_item is None:
            return
        self.current_item.icon_value = text.strip()
        self._update_icon_preview(self.current_item.icon_value)
        self._refresh_gallery_chip_styles()
        self.item_modified.emit(self.current_item.item_id)

    def _pick_gallery_icon(self, path_str: str) -> None:
        if self.current_item is None:
            return
        self.icon_preset_combo.blockSignals(True)
        self.icon_preset_combo.setCurrentIndex(0)
        self.icon_preset_combo.blockSignals(False)
        self.icon_path_input.setText(path_str)

    def _browse_icon(self) -> None:
        if self.current_item is None:
            return
        icons_dir = self.project_root / ".git-command" / ".icons"
        init_dir = str(icons_dir if icons_dir.is_dir() else self.project_root)
        chosen, _ = QFileDialog.getOpenFileName(
            self,
            "选择快捷方式图标",
            init_dir,
            "图标与图片 (*.png *.ico *.exe *.dll *.jpg *.jpeg *.bmp);;PNG 图片 (*.png);;Windows 图标 (*.ico);;所有文件 (*.*)",
        )
        if chosen:
            self.icon_preset_combo.blockSignals(True)
            self.icon_preset_combo.setCurrentIndex(0)
            self.icon_preset_combo.blockSignals(False)
            self.icon_path_input.setText(str(Path(chosen).resolve()))

    def _reset_icon(self) -> None:
        if self.current_item is None:
            return
        self.icon_preset_combo.blockSignals(True)
        self.icon_preset_combo.setCurrentIndex(0)
        self.icon_preset_combo.blockSignals(False)
        self.icon_path_input.setText(default_icon_path(self.project_root))