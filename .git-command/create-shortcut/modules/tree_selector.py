# -*- coding: utf-8 -*-
"""
Enhanced File Tree Selector:
- Displays all subdirectories & scripts under .git-command in a real folder hierarchy
- Uses crisp vector folder icons for directory nodes
- Preserves parent hierarchy during live keyword search & category filtering
- Supports drag-and-drop, external file/folder adding, and subtree batch selection via context menu
"""

from __future__ import annotations

from pathlib import Path
from typing import Callable, Optional

from .config import (
    FILTER_ALL,
    FILTER_DIRS,
    FILTER_EXISTING,
    FILTER_SCRIPTS,
    FILTER_SELECTED,
    FONT_STYLE_BASE,
    MODE_TERMINAL,
    PALETTE_BLACK,
    PALETTE_ORANGE,
    PALETTE_ORANGE_LIGHT,
    PALETTE_ROSE,
    PALETTE_ROSE_DEEP,
)
from .models import TargetItem
from .qt_compat import (
    CHECK_CHECKED,
    CHECK_UNCHECKED,
    CONTEXT_CUSTOM,
    CURSOR_POINTER,
    HDR_INTERACTIVE,
    HDR_STRETCH,
    ITEM_ENABLED,
    ITEM_SELECTABLE,
    ITEM_USER_CHECKABLE,
    KEEP_ASPECT,
    QColor,
    QFileDialog,
    QHBoxLayout,
    QIcon,
    QLabel,
    QLineEdit,
    QMenu,
    QPixmap,
    QPushButton,
    QSize,
    QTreeWidget,
    QTreeWidgetItem,
    QVBoxLayout,
    QWidget,
    SCROLL_PER_PIXEL,
    SMOOTH_TRANSFORM,
    Signal,
    USER_ROLE,
    exec_menu,
    make_ui_font,
)
from .shortcut_engine import reveal_in_explorer
from .theme import (
    ThemePalette,
    build_button_stylesheet,
    build_input_stylesheet,
    build_menu_stylesheet,
    build_pill_stylesheet,
    build_tree_stylesheet,
    make_badge_pixmap,
    make_folder_pixmap,
)


class DropTreeWidget(QTreeWidget):
    paths_dropped = Signal(list)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAcceptDrops(True)

    def dragEnterEvent(self, event):
        if event.mimeData().hasUrls():
            event.acceptProposedAction()
            self.setProperty("dragActive", True)
            self.style().unpolish(self)
            self.style().polish(self)
        else:
            event.ignore()

    def dragMoveEvent(self, event):
        if event.mimeData().hasUrls():
            event.acceptProposedAction()
        else:
            event.ignore()

    def dragLeaveEvent(self, event):
        self.setProperty("dragActive", False)
        self.style().unpolish(self)
        self.style().polish(self)
        super().dragLeaveEvent(event)

    def dropEvent(self, event):
        self.setProperty("dragActive", False)
        self.style().unpolish(self)
        self.style().polish(self)
        if event.mimeData().hasUrls():
            paths = [Path(u.toLocalFile()) for u in event.mimeData().urls() if u.toLocalFile()]
            if paths:
                self.paths_dropped.emit(paths)
            event.acceptProposedAction()
        else:
            event.ignore()


class FileTreeSelector(QWidget):
    item_focused = Signal(str)                  # item_id or ""
    selection_changed = Signal()
    request_refresh = Signal()
    paths_added = Signal(list)                  # list[Path]
    request_rename = Signal(str)                # item_id
    request_apply_icon_selected = Signal(str)   # item_id
    request_reset_item = Signal(str)            # item_id
    status_message = Signal(str, str)           # text, level

    def __init__(self, parent=None):
        super().__init__(parent)
        self.items: dict[str, TargetItem] = {}
        self.project_root: Path = Path.cwd()
        self.lnk_exists_fn: Callable[[TargetItem], bool] = lambda _: False
        self.palette: Optional[ThemePalette] = None

        self.active_filter: str = FILTER_ALL
        self._node_map: dict[str, QTreeWidgetItem] = {}
        self._icon_cache: dict[str, QIcon] = {}
        self._rebuilding: bool = False

        self._init_ui()

    def _init_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 2, 0)
        layout.setSpacing(6)

        # 1. Search Bar
        self.search_input = QLineEdit(self)
        self.search_input.setFont(make_ui_font(9.0))
        self.search_input.setPlaceholderText("filter: 搜索任意子目录脚本 / 文件夹 / 后缀 / 快捷方式名 (Ctrl+F)")
        self.search_input.setClearButtonEnabled(True)
        self.search_input.textChanged.connect(self.apply_filter_and_search)
        layout.addWidget(self.search_input)

        # 2. Filter Pills + Expand/Collapse Controls
        filter_row = QHBoxLayout()
        filter_row.setContentsMargins(0, 0, 0, 0)
        filter_row.setSpacing(5)

        self.filter_buttons: dict[str, QPushButton] = {}
        for key, label in [
            (FILTER_ALL, "全部"),
            (FILTER_SCRIPTS, "脚本"),
            (FILTER_DIRS, "文件夹"),
            (FILTER_SELECTED, "已选"),
            (FILTER_EXISTING, "已有.lnk"),
        ]:
            btn = QPushButton(label, self)
            btn.setCursor(CURSOR_POINTER)
            btn.setFont(make_ui_font(7.8, bold=True))
            btn.clicked.connect(lambda checked=False, k=key: self.set_filter(k))
            filter_row.addWidget(btn)
            self.filter_buttons[key] = btn

        filter_row.addStretch(1)

        self.btn_expand_all = QPushButton("展开", self)
        self.btn_collapse_all = QPushButton("折叠", self)
        for b in (self.btn_expand_all, self.btn_collapse_all):
            b.setCursor(CURSOR_POINTER)
            b.setFont(make_ui_font(7.6, bold=True))
        self.btn_expand_all.setToolTip("展开所有子目录")
        self.btn_collapse_all.setToolTip("折叠所有子目录")
        self.btn_expand_all.clicked.connect(self.expand_all)
        self.btn_collapse_all.clicked.connect(self.collapse_all)
        filter_row.addWidget(self.btn_expand_all)
        filter_row.addWidget(self.btn_collapse_all)
        layout.addLayout(filter_row)

        # 3. Batch Selection & Add Toolbar
        batch_row = QHBoxLayout()
        batch_row.setContentsMargins(0, 0, 0, 0)
        batch_row.setSpacing(5)

        self.btn_sel_visible = QPushButton("全选可见", self)
        self.btn_sel_scripts = QPushButton("仅选脚本", self)
        self.btn_invert = QPushButton("反选", self)
        self.btn_clear = QPushButton("清空", self)
        self.btn_add_files = QPushButton("+ 文件", self)
        self.btn_add_folder = QPushButton("+ 文件夹", self)
        self.btn_refresh = QPushButton("刷新", self)

        self.action_buttons = [
            self.btn_sel_visible,
            self.btn_sel_scripts,
            self.btn_invert,
            self.btn_clear,
            self.btn_add_files,
            self.btn_add_folder,
            self.btn_refresh,
            self.btn_expand_all,
            self.btn_collapse_all,
        ]
        for b in (
            self.btn_sel_visible,
            self.btn_sel_scripts,
            self.btn_invert,
            self.btn_clear,
            self.btn_add_files,
            self.btn_add_folder,
            self.btn_refresh,
        ):
            b.setCursor(CURSOR_POINTER)
            b.setFont(make_ui_font(7.6, bold=True))

        self.btn_sel_visible.clicked.connect(lambda: self.batch_select("visible_all"))
        self.btn_sel_scripts.clicked.connect(lambda: self.batch_select("scripts"))
        self.btn_invert.clicked.connect(lambda: self.batch_select("invert"))
        self.btn_clear.clicked.connect(lambda: self.batch_select("none"))
        self.btn_add_files.setToolTip("添加外部文件（或直接拖入文件树）")
        self.btn_add_files.clicked.connect(self._browse_add_files)
        self.btn_add_folder.setToolTip("添加外部文件夹（或直接拖入文件树）")
        self.btn_add_folder.clicked.connect(self._browse_add_folder)
        self.btn_refresh.clicked.connect(self.request_refresh.emit)

        batch_row.addWidget(self.btn_sel_visible)
        batch_row.addWidget(self.btn_sel_scripts)
        batch_row.addWidget(self.btn_invert)
        batch_row.addWidget(self.btn_clear)
        batch_row.addStretch(1)
        batch_row.addWidget(self.btn_add_files)
        batch_row.addWidget(self.btn_add_folder)
        batch_row.addWidget(self.btn_refresh)
        layout.addLayout(batch_row)

        # 4. Hierarchical File Tree
        self.tree = DropTreeWidget(self)
        self.tree.setColumnCount(4)
        self.tree.setHeaderLabels(["目录 / 文件 (.git-command)", "快捷方式名", "类型", "运行方式"])
        self.tree.setUniformRowHeights(True)
        self.tree.setAnimated(True)
        self.tree.setIndentation(18)
        self.tree.setIconSize(QSize(18, 18))
        self.tree.setVerticalScrollMode(SCROLL_PER_PIXEL)
        self.tree.setContextMenuPolicy(CONTEXT_CUSTOM)

        hdr = self.tree.header()
        hdr.setStretchLastSection(False)
        hdr.setSectionResizeMode(0, HDR_STRETCH)
        hdr.setSectionResizeMode(1, HDR_INTERACTIVE)
        hdr.setSectionResizeMode(2, HDR_INTERACTIVE)
        hdr.setSectionResizeMode(3, HDR_INTERACTIVE)
        self.tree.setColumnWidth(1, 138)
        self.tree.setColumnWidth(2, 94)
        self.tree.setColumnWidth(3, 96)

        self.tree.itemChanged.connect(self._on_tree_item_changed)
        self.tree.currentItemChanged.connect(self._on_current_item_changed)
        self.tree.itemDoubleClicked.connect(self._on_item_double_clicked)
        self.tree.customContextMenuRequested.connect(self._on_context_menu)
        self.tree.paths_dropped.connect(self.paths_added.emit)
        layout.addWidget(self.tree, 1)

        # 5. Hint Bar
        self.hint_lbl = QLabel(
            "提示: 勾选节点创建快捷方式 · 右键文件夹可一键勾选子目录内全部脚本 · 支持拖入任意文件/目录",
            self,
        )
        self.hint_lbl.setFont(make_ui_font(7.5))
        layout.addWidget(self.hint_lbl)

    # --------------------------------------------------------------------------
    # Theme Application
    # --------------------------------------------------------------------------
    def apply_theme(self, p: ThemePalette) -> None:
        self.palette = p
        self.search_input.setStyleSheet(build_input_stylesheet(p))
        self.tree.setStyleSheet(build_tree_stylesheet(p))
        self.hint_lbl.setStyleSheet(f"{FONT_STYLE_BASE} color: {p.muted_fg}; background: transparent;")

        neutral_css = build_button_stylesheet(p, "neutral", "4px 8px")
        for b in self.action_buttons:
            b.setStyleSheet(neutral_css)

        self._refresh_filter_pills_style()
        self._recolor_all_nodes()

    def _refresh_filter_pills_style(self) -> None:
        if not self.palette:
            return
        for key, btn in self.filter_buttons.items():
            btn.setStyleSheet(build_pill_stylesheet(self.palette, active=(key == self.active_filter), accent="rose"))

    # --------------------------------------------------------------------------
    # Tree Building & Node Visuals
    # --------------------------------------------------------------------------
    def _icon_for_item(self, item: TargetItem) -> QIcon:
        if item.is_dir:
            key = "folder:checked" if item.selected else "folder:normal"
            if key not in self._icon_cache:
                if item.selected:
                    pm = make_folder_pixmap(back_hex=PALETTE_ROSE_DEEP, front_hex=PALETTE_ROSE, size=18)
                else:
                    pm = make_folder_pixmap(back_hex=PALETTE_ORANGE, front_hex=PALETTE_ORANGE_LIGHT, size=18)
                self._icon_cache[key] = QIcon(pm)
            return self._icon_cache[key]

        val = item.icon_value.strip()
        if val and "," not in val and Path(val).is_file():
            key = f"file:{val}"
            if key not in self._icon_cache:
                pm = QPixmap(val)
                if not pm.isNull():
                    self._icon_cache[key] = QIcon(pm.scaled(18, 18, KEEP_ASPECT, SMOOTH_TRANSFORM))
            if key in self._icon_cache:
                return self._icon_cache[key]

        ext_map = {
            ".sh": ("SH", PALETTE_ROSE),
            ".py": ("PY", PALETTE_ORANGE),
            ".bat": ("BAT", PALETTE_BLACK),
            ".cmd": ("CMD", PALETTE_BLACK),
            ".ps1": ("PS", PALETTE_BLACK),
            ".js": ("JS", PALETTE_ORANGE),
            ".mjs": ("JS", PALETTE_ORANGE),
        }
        tag, col = ext_map.get(item.ext, (item.ext.lstrip(".").upper()[:3] or "F", "#52525B"))
        key = f"badge:{tag}:{col}"
        if key not in self._icon_cache:
            self._icon_cache[key] = QIcon(make_badge_pixmap(tag, col, "#FFFFFF", 18))
        return self._icon_cache[key]

    def _count_descendant_scripts(self, dir_path: Path) -> int:
        prefix = str(dir_path.resolve()).lower()
        cnt = 0
        for it in self.items.values():
            if it.is_script:
                try:
                    it.abs_path.relative_to(dir_path)
                    cnt += 1
                except ValueError:
                    if str(it.abs_path).lower().startswith(prefix + "\\"):
                        cnt += 1
        return cnt

    def _style_tree_node(self, node: QTreeWidgetItem, item: TargetItem) -> None:
        exists_lnk = self.lnk_exists_fn(item)

        # Col 0: Node name (folders show script count hint if > 0)
        col0 = item.node_label
        if item.is_dir:
            sc = self._count_descendant_scripts(item.abs_path)
            if sc > 0:
                col0 = f"{item.node_label}  ({sc} 脚本)"
        node.setText(0, col0)
        node.setIcon(0, self._icon_for_item(item))
        node.setToolTip(0, item.display_path)

        # Col 1: Shortcut Name + visual badges
        tags: list[str] = []
        if item.selected:
            tags.append("✓")
        if item.is_renamed:
            tags.append("改名")
        if exists_lnk:
            tags.append("已有")
        prefix = ("[" + "·".join(tags) + "] ") if tags else ""
        node.setText(1, f"{prefix}{item.shortcut_name or '(未命名)'}")
        node.setToolTip(1, f"将生成: {item.shortcut_name}.lnk")

        # Col 2 & 3
        node.setText(2, item.runner_tag)
        node.setText(3, item.mode_short_label)

        node.setCheckState(0, CHECK_CHECKED if item.selected else CHECK_UNCHECKED)

        if self.palette:
            p = self.palette
            if item.selected:
                c0 = QColor(p.rose_accent)
                c1 = QColor(p.rose_accent)
                c2 = QColor(p.text_fg)
                c3 = QColor(p.org_accent if item.resolved_mode() == MODE_TERMINAL else p.text_fg)
            elif item.is_dir:
                c0 = QColor(p.org_accent)
                c1 = QColor(p.muted_fg)
                c2 = QColor(p.org_accent)
                c3 = QColor(p.muted_fg)
            else:
                c0 = QColor(p.text_fg)
                c1 = QColor(p.muted_fg)
                c2 = QColor(p.muted_fg)
                c3 = QColor(p.muted_fg)

            node.setForeground(0, c0)
            node.setForeground(1, c1)
            node.setForeground(2, c2)
            node.setForeground(3, c3)

    def _recolor_all_nodes(self) -> None:
        self._rebuilding = True
        try:
            for item_id, node in self._node_map.items():
                if item_id in self.items:
                    self._style_tree_node(node, self.items[item_id])
        finally:
            self._rebuilding = False

    def load_items(
        self,
        items: dict[str, TargetItem],
        project_root: Path,
        lnk_exists_fn: Callable[[TargetItem], bool],
        focus_item_id: Optional[str] = None,
    ) -> None:
        self.items = items
        self.project_root = project_root
        self.lnk_exists_fn = lnk_exists_fn

        prev_id = focus_item_id or self.current_item_id()
        self._rebuilding = True
        try:
            self.tree.clear()
            self._node_map.clear()

            internal_items: list[TargetItem] = []
            external_items: list[TargetItem] = []

            for it in items.values():
                if it.rel_to_git_cmd is not None:
                    internal_items.append(it)
                else:
                    external_items.append(it)

            # Sort internal items by depth first so parent folders are created before children
            internal_items.sort(
                key=lambda x: (
                    len(x.rel_to_git_cmd.parts) if x.rel_to_git_cmd else 999,
                    0 if x.is_dir else 1,
                    x.rel_to_git_cmd.as_posix().lower() if x.rel_to_git_cmd else "",
                )
            )

            path_to_node: dict[Path, QTreeWidgetItem] = {}

            for it in internal_items:
                assert it.rel_to_git_cmd is not None
                parent_rel = it.rel_to_git_cmd.parent
                if parent_rel == Path(".") or parent_rel not in path_to_node:
                    parent_widget = self.tree
                else:
                    parent_widget = path_to_node[parent_rel]

                node = QTreeWidgetItem(parent_widget)
                node.setFlags(ITEM_ENABLED | ITEM_SELECTABLE | ITEM_USER_CHECKABLE)
                node.setData(0, USER_ROLE, it.item_id)
                self._style_tree_node(node, it)

                self._node_map[it.item_id] = node
                if it.is_dir:
                    path_to_node[it.rel_to_git_cmd] = node

            # External items (outside .git-command) grouped cleanly under one collapsible folder
            if external_items:
                ext_group = QTreeWidgetItem(self.tree)
                ext_group.setFlags(ITEM_ENABLED | ITEM_SELECTABLE)
                ext_group.setData(0, USER_ROLE, None)
                ext_group.setText(0, f"外部添加 ({len(external_items)})")
                ext_group.setText(2, "GROUP")
                if "folder:ext" not in self._icon_cache:
                    self._icon_cache["folder:ext"] = QIcon(
                        make_folder_pixmap(back_hex="#52525B", front_hex="#71717A", size=18)
                    )
                ext_group.setIcon(0, self._icon_cache["folder:ext"])
                if self.palette:
                    ext_group.setForeground(0, QColor(self.palette.org_accent))
                    ext_group.setForeground(2, QColor(self.palette.muted_fg))

                external_items.sort(key=lambda x: (0 if x.is_dir else 1, x.display_path.lower()))
                for it in external_items:
                    node = QTreeWidgetItem(ext_group)
                    node.setFlags(ITEM_ENABLED | ITEM_SELECTABLE | ITEM_USER_CHECKABLE)
                    node.setData(0, USER_ROLE, it.item_id)
                    self._style_tree_node(node, it)
                    self._node_map[it.item_id] = node

            # Expand all directories by default so every nested script is immediately visible
            self.tree.expandAll()
        finally:
            self._rebuilding = False

        self.apply_filter_and_search()
        self._update_selected_pill_count()

        if prev_id and prev_id in self._node_map and not self._node_map[prev_id].isHidden():
            self.tree.setCurrentItem(self._node_map[prev_id])
        else:
            first = self._first_visible_item_node()
            if first is not None:
                self.tree.setCurrentItem(first)
            else:
                self.item_focused.emit("")

    def refresh_single_item(self, item_id: str) -> None:
        if item_id not in self._node_map or item_id not in self.items:
            return
        self._rebuilding = True
        try:
            self._style_tree_node(self._node_map[item_id], self.items[item_id])
        finally:
            self._rebuilding = False
        self._update_selected_pill_count()

    def refresh_all_status_badges(self) -> None:
        self._recolor_all_nodes()
        if self.active_filter == FILTER_EXISTING:
            self.apply_filter_and_search()

    # --------------------------------------------------------------------------
    # Filtering & Searching (Preserves Parent Hierarchy)
    # --------------------------------------------------------------------------
    def set_filter(self, filter_key: str) -> None:
        self.active_filter = filter_key
        self._refresh_filter_pills_style()
        self.apply_filter_and_search()

    def _matches_item(self, item: TargetItem, kw: str) -> bool:
        if self.active_filter == FILTER_SCRIPTS and not item.is_script:
            return False
        if self.active_filter == FILTER_DIRS and not item.is_dir:
            return False
        if self.active_filter == FILTER_SELECTED and not item.selected:
            return False
        if self.active_filter == FILTER_EXISTING and not self.lnk_exists_fn(item):
            return False

        if kw:
            hay = f"{item.node_label} {item.shortcut_name} {item.display_path} {item.runner_tag}".lower()
            if kw not in hay:
                return False
        return True

    def _filter_node_recursive(self, node: QTreeWidgetItem, kw: str) -> bool:
        any_child_visible = False
        for i in range(node.childCount()):
            if self._filter_node_recursive(node.child(i), kw):
                any_child_visible = True

        item_id = node.data(0, USER_ROLE)
        if item_id and item_id in self.items:
            self_match = self._matches_item(self.items[item_id], kw)
        else:
            self_match = False

        visible = self_match or any_child_visible
        node.setHidden(not visible)

        if any_child_visible and (kw or self.active_filter != FILTER_ALL):
            node.setExpanded(True)
        return visible

    def apply_filter_and_search(self) -> None:
        kw = self.search_input.text().strip().lower()
        for i in range(self.tree.topLevelItemCount()):
            self._filter_node_recursive(self.tree.topLevelItem(i), kw)

    def _first_visible_item_node(self) -> Optional[QTreeWidgetItem]:
        def _walk(node: QTreeWidgetItem) -> Optional[QTreeWidgetItem]:
            if node.isHidden():
                return None
            iid = node.data(0, USER_ROLE)
            if iid and iid in self.items:
                return node
            for j in range(node.childCount()):
                found = _walk(node.child(j))
                if found is not None:
                    return found
            return None

        for i in range(self.tree.topLevelItemCount()):
            res = _walk(self.tree.topLevelItem(i))
            if res is not None:
                return res
        return None

    def visible_item_ids(self) -> list[str]:
        kw = self.search_input.text().strip().lower()
        result: list[str] = []
        for iid, node in self._node_map.items():
            if not node.isHidden() and iid in self.items and self._matches_item(self.items[iid], kw):
                result.append(iid)
        return result

    def visible_count(self) -> int:
        return len(self.visible_item_ids())

    def current_item_id(self) -> str:
        cur = self.tree.currentItem()
        if not cur:
            return ""
        iid = cur.data(0, USER_ROLE)
        return iid if isinstance(iid, str) and iid in self.items else ""

    def expand_all(self) -> None:
        self.tree.expandAll()

    def collapse_all(self) -> None:
        self.tree.collapseAll()

    # --------------------------------------------------------------------------
    # Selection, Subtree Batch Operations & Context Menu
    # --------------------------------------------------------------------------
    def _update_selected_pill_count(self) -> None:
        cnt = sum(1 for x in self.items.values() if x.selected)
        self.filter_buttons[FILTER_SELECTED].setText(f"已选 ({cnt})")

    def _on_tree_item_changed(self, node: QTreeWidgetItem, column: int) -> None:
        if self._rebuilding or column != 0:
            return
        item_id = node.data(0, USER_ROLE)
        if not item_id or item_id not in self.items:
            return
        checked = node.checkState(0) == CHECK_CHECKED
        if self.items[item_id].selected != checked:
            self.items[item_id].selected = checked
            self.refresh_single_item(item_id)
            if self.active_filter == FILTER_SELECTED:
                self.apply_filter_and_search()
            self.selection_changed.emit()

    def _on_current_item_changed(self, current: Optional[QTreeWidgetItem], _previous) -> None:
        if not current:
            self.item_focused.emit("")
            return
        iid = current.data(0, USER_ROLE)
        self.item_focused.emit(iid if isinstance(iid, str) and iid in self.items else "")

    def _on_item_double_clicked(self, node: QTreeWidgetItem, _column: int) -> None:
        iid = node.data(0, USER_ROLE)
        if not iid or iid not in self.items:
            return
        item = self.items[iid]
        # Double-clicking a file toggles check; double-clicking a folder expands/collapses naturally
        if not item.is_dir:
            item.selected = not item.selected
            self.refresh_single_item(iid)
            if self.active_filter == FILTER_SELECTED:
                self.apply_filter_and_search()
            self.selection_changed.emit()

    def batch_select(self, mode: str) -> None:
        if mode == "visible_all":
            for iid in self.visible_item_ids():
                self.items[iid].selected = True
        elif mode == "scripts":
            for it in self.items.values():
                it.selected = it.is_script
        elif mode == "invert":
            for iid in self.visible_item_ids():
                self.items[iid].selected = not self.items[iid].selected
        elif mode == "none":
            for it in self.items.values():
                it.selected = False

        self._recolor_all_nodes()
        if self.active_filter == FILTER_SELECTED:
            self.apply_filter_and_search()
        self._update_selected_pill_count()
        self.selection_changed.emit()

    def _collect_subtree_ids(self, node: QTreeWidgetItem, include_self: bool = False) -> list[str]:
        ids: list[str] = []
        if include_self:
            iid = node.data(0, USER_ROLE)
            if iid and iid in self.items:
                ids.append(iid)
        for i in range(node.childCount()):
            ids.extend(self._collect_subtree_ids(node.child(i), include_self=True))
        return ids

    def _on_context_menu(self, pos) -> None:
        node = self.tree.itemAt(pos)
        if not node:
            return
        iid = node.data(0, USER_ROLE)
        if not iid or iid not in self.items:
            return
        item = self.items[iid]

        menu = QMenu(self)
        menu.setFont(make_ui_font(8.8))
        if self.palette:
            menu.setStyleSheet(build_menu_stylesheet(self.palette))

        act_toggle = menu.addAction("取消勾选此项" if item.selected else "勾选此项（创建快捷方式）")

        act_sub_scripts = None
        act_sub_all = None
        act_sub_clear = None
        if item.is_dir and node.childCount() > 0:
            menu.addSeparator()
            act_sub_scripts = menu.addAction("勾选此目录内全部脚本")
            act_sub_all = menu.addAction("勾选此目录内所有子项")
            act_sub_clear = menu.addAction("取消此目录内全部勾选")

        menu.addSeparator()
        same_lbl = (
            f"勾选全部 {item.ext} 文件"
            if item.ext
            else ("勾选全部文件夹" if item.is_dir else "勾选全部无后缀文件")
        )
        act_same_type = menu.addAction(same_lbl)
        act_rename = menu.addAction("快速重命名 (F2)")
        act_apply_icon = menu.addAction("将此项图标应用到所有已选项")
        act_reset = menu.addAction("重置为默认名称与图标")
        menu.addSeparator()
        act_reveal = menu.addAction("在资源管理器中定位源文件")

        chosen = exec_menu(menu, self.tree.viewport().mapToGlobal(pos))
        if chosen is None:
            return

        if chosen == act_toggle:
            item.selected = not item.selected
            self.refresh_single_item(iid)
            self.selection_changed.emit()
        elif chosen == act_sub_scripts:
            sub_ids = self._collect_subtree_ids(node, include_self=False)
            cnt = 0
            for sid in sub_ids:
                if self.items[sid].is_script:
                    self.items[sid].selected = True
                    cnt += 1
            self._recolor_all_nodes()
            self._update_selected_pill_count()
            self.selection_changed.emit()
            self.status_message.emit(f"已勾选 {item.node_label} 下的 {cnt} 个脚本", "ok")
        elif chosen == act_sub_all:
            sub_ids = self._collect_subtree_ids(node, include_self=False)
            for sid in sub_ids:
                self.items[sid].selected = True
            self._recolor_all_nodes()
            self._update_selected_pill_count()
            self.selection_changed.emit()
            self.status_message.emit(f"已勾选 {item.node_label} 下的 {len(sub_ids)} 个子项", "ok")
        elif chosen == act_sub_clear:
            sub_ids = self._collect_subtree_ids(node, include_self=True)
            for sid in sub_ids:
                self.items[sid].selected = False
            self._recolor_all_nodes()
            self._update_selected_pill_count()
            self.selection_changed.emit()
        elif chosen == act_same_type:
            for it in self.items.values():
                if (item.is_dir and it.is_dir) or (not item.is_dir and not it.is_dir and it.ext == item.ext):
                    it.selected = True
            self._recolor_all_nodes()
            self._update_selected_pill_count()
            self.selection_changed.emit()
        elif chosen == act_rename:
            self.request_rename.emit(iid)
        elif chosen == act_apply_icon:
            self.request_apply_icon_selected.emit(iid)
        elif chosen == act_reset:
            self.request_reset_item.emit(iid)
        elif chosen == act_reveal:
            reveal_in_explorer(item.abs_path)

    # --------------------------------------------------------------------------
    # External File / Folder Dialogs
    # --------------------------------------------------------------------------
    def _browse_add_files(self) -> None:
        base = self.project_root / ".git-command"
        start_dir = str(base if base.is_dir() else self.project_root)
        files, _ = QFileDialog.getOpenFileNames(self, "添加文件到树形列表", start_dir, "所有文件 (*.*)")
        if files:
            self.paths_added.emit([Path(f) for f in files])

    def _browse_add_folder(self) -> None:
        base = self.project_root / ".git-command"
        start_dir = str(base if base.is_dir() else self.project_root)
        folder = QFileDialog.getExistingDirectory(self, "添加文件夹到树形列表", start_dir)
        if folder:
            self.paths_added.emit([Path(folder)])