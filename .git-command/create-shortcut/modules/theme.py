# -*- coding: utf-8 -*-
"""
Glassmorphism Theme Tokens & Reusable Stylesheet / Vector Icon Builders
- 0% Transparency: Pure White Opaque (#FFFFFF)
- 1%~95% Transparency: Crystal-Clear Dark Black-Gray Glass (rgba(18, 20, 24, alpha))
- Accent Palette: Black / Rose Red / Dark Orange
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from .config import (
    FONT_STYLE_BASE,
    PALETTE_BLACK,
    PALETTE_BLACK_SUB,
    PALETTE_ORANGE,
    PALETTE_ORANGE_DEEP,
    PALETTE_ORANGE_LIGHT,
    PALETTE_ROSE,
    PALETTE_ROSE_DEEP,
    PALETTE_ROSE_LIGHT,
    clamp_transparency,
)
from .qt_compat import (
    ALIGN_CENTER,
    ANTIALIASING,
    GLOBAL_TRANSPARENT,
    PEN_NONE,
    QBrush,
    QColor,
    QIcon,
    QPainter,
    QPainterPath,
    QPen,
    QPixmap,
    QRect,
    QRectF,
    make_ui_font,
)


@dataclass(frozen=True)
class ThemePalette:
    transparency: int
    is_dark: bool
    card_bg: str
    card_bd: str
    sub_card_bg: str
    sub_card_bd: str
    ctrl_bg: str
    ctrl_hv: str
    text_fg: str
    muted_fg: str
    rose_accent: str
    rose_pill_bg: str
    org_accent: str
    org_pill_bg: str
    count_bg: str
    count_fg: str
    count_bd: str
    scroll_col: str
    popup_bg: str
    popup_bd: str
    popup_fg: str
    tree_sel_bg: str
    tree_hover_bg: str
    tree_hdr_bg: str
    tree_line_col: str


def compute_theme_palette(transparency: int) -> ThemePalette:
    t = clamp_transparency(transparency)
    opacity_pct = 100 - t
    is_dark = t > 0

    if not is_dark:
        return ThemePalette(
            transparency=t,
            is_dark=False,
            card_bg="#FFFFFF",
            card_bd="1px solid #E4E4E7",
            sub_card_bg="#FAFAFA",
            sub_card_bd="1px solid #E4E4E7",
            ctrl_bg="#F4F4F5",
            ctrl_hv="#E4E4E7",
            text_fg=PALETTE_BLACK,
            muted_fg=PALETTE_BLACK_SUB,
            rose_accent=PALETTE_ROSE,
            rose_pill_bg="rgba(225, 29, 72, 22)",
            org_accent=PALETTE_ORANGE,
            org_pill_bg="rgba(194, 65, 12, 20)",
            count_bg=PALETTE_BLACK,
            count_fg="#FFFFFF",
            count_bd="none",
            scroll_col="rgba(24, 24, 27, 68)",
            popup_bg="#FAFAFA",
            popup_bd="1px solid #D4D4D8",
            popup_fg=PALETTE_BLACK,
            tree_sel_bg="rgba(225, 29, 72, 22)",
            tree_hover_bg="rgba(24, 24, 27, 11)",
            tree_hdr_bg="#F4F4F5",
            tree_line_col="rgba(24, 24, 27, 16)",
        )

    card_alpha = max(16, int(round(255 * opacity_pct / 100.0)))
    edge_alpha = max(18, min(52, int(card_alpha * 0.22)))
    sub_alpha = max(12, min(28, int(card_alpha * 0.13)))

    return ThemePalette(
        transparency=t,
        is_dark=True,
        card_bg=f"rgba(18, 20, 24, {card_alpha})",
        card_bd=f"1px solid rgba(255, 255, 255, {edge_alpha})",
        sub_card_bg=f"rgba(255, 255, 255, {sub_alpha})",
        sub_card_bd=f"1px solid rgba(255, 255, 255, {max(16, min(42, int(card_alpha * 0.18)))})",
        ctrl_bg=f"rgba(255, 255, 255, {max(14, min(32, int(card_alpha * 0.15)))})",
        ctrl_hv=f"rgba(255, 255, 255, {max(24, min(52, int(card_alpha * 0.25)))})",
        text_fg="#F4F4F5",
        muted_fg="#A1A1AA",
        rose_accent=PALETTE_ROSE_LIGHT,
        rose_pill_bg="rgba(244, 63, 94, 34)",
        org_accent=PALETTE_ORANGE_LIGHT,
        org_pill_bg="rgba(251, 146, 60, 30)",
        count_bg=f"rgba(255, 255, 255, {max(20, min(44, int(card_alpha * 0.19)))})",
        count_fg="#F4F4F5",
        count_bd=f"1px solid rgba(255, 255, 255, {max(18, min(44, int(card_alpha * 0.20)))})",
        scroll_col="rgba(255, 255, 255, 58)",
        popup_bg="#181A1F",
        popup_bd="1px solid rgba(255, 255, 255, 36)",
        popup_fg="#F4F4F5",
        tree_sel_bg="rgba(244, 63, 94, 38)",
        tree_hover_bg="rgba(255, 255, 255, 18)",
        tree_hdr_bg=f"rgba(255, 255, 255, {max(12, min(26, int(card_alpha * 0.12)))})",
        tree_line_col="rgba(255, 255, 255, 20)",
    )


def build_button_stylesheet(p: ThemePalette, variant: str = "neutral", padding: str = "4px 9px") -> str:
    if variant == "rose":
        return f"""
            QPushButton {{
                {FONT_STYLE_BASE}
                background-color: {PALETTE_ROSE}; color: #FFFFFF;
                border: none; border-radius: 7px; padding: {padding};
            }}
            QPushButton:hover {{ background-color: {PALETTE_ROSE_DEEP}; }}
        """
    if variant == "orange":
        return f"""
            QPushButton {{
                {FONT_STYLE_BASE}
                background-color: {PALETTE_ORANGE}; color: #FFFFFF;
                border: none; border-radius: 6px; padding: {padding};
            }}
            QPushButton:hover {{ background-color: {PALETTE_ORANGE_DEEP}; }}
        """
    if variant == "rose_soft":
        return f"""
            QPushButton {{
                {FONT_STYLE_BASE}
                background-color: {p.rose_pill_bg}; color: {p.rose_accent};
                border: none; border-radius: 6px; padding: {padding};
            }}
            QPushButton:hover {{ background-color: rgba(244, 63, 94, 56); }}
        """
    return f"""
        QPushButton {{
            {FONT_STYLE_BASE}
            background-color: {p.ctrl_bg}; color: {p.text_fg};
            border: none; border-radius: 6px; padding: {padding};
        }}
        QPushButton:hover {{ background-color: {p.ctrl_hv}; color: {p.rose_accent}; }}
    """


def build_pill_stylesheet(p: ThemePalette, active: bool, accent: str = "rose") -> str:
    if active:
        bg = PALETTE_ROSE if accent == "rose" else PALETTE_ORANGE
        return f"""
            QPushButton {{
                {FONT_STYLE_BASE}
                background-color: {bg}; color: #FFFFFF;
                border: none; border-radius: 5px; padding: 3px 9px;
            }}
        """
    hv_bg = p.rose_pill_bg if accent == "rose" else p.org_pill_bg
    hv_fg = p.rose_accent if accent == "rose" else p.org_accent
    return f"""
        QPushButton {{
            {FONT_STYLE_BASE}
            background-color: {p.ctrl_bg}; color: {p.text_fg};
            border: none; border-radius: 5px; padding: 3px 9px;
        }}
        QPushButton:hover {{ background-color: {hv_bg}; color: {hv_fg}; }}
    """


def build_input_stylesheet(p: ThemePalette) -> str:
    return f"""
        QLineEdit {{
            {FONT_STYLE_BASE}
            background-color: {p.ctrl_bg}; color: {p.text_fg};
            border: none; outline: none; border-radius: 7px; padding: 6px 10px;
        }}
        QLineEdit:focus {{
            background-color: {p.ctrl_hv}; border: none; outline: none;
        }}
    """


def build_combo_stylesheet(p: ThemePalette) -> str:
    return f"""
        QComboBox {{
            {FONT_STYLE_BASE}
            background-color: {p.ctrl_bg}; color: {p.text_fg};
            border: none; border-radius: 6px; padding: 4px 9px;
        }}
        QComboBox:hover {{ background-color: {p.ctrl_hv}; }}
        QComboBox::drop-down {{ border: none; }}
        QComboBox QAbstractItemView {{
            background-color: {p.popup_bg}; color: {p.popup_fg};
            border: {p.popup_bd};
            selection-background-color: rgba(244, 63, 94, 42);
            selection-color: {p.rose_accent};
            outline: none;
        }}
    """


def build_checkbox_stylesheet(p: ThemePalette) -> str:
    bd = "rgba(255, 255, 255, 58)" if p.is_dark else "rgba(24, 24, 27, 55)"
    return f"""
        QCheckBox {{
            {FONT_STYLE_BASE}
            color: {p.text_fg}; spacing: 5px; background: transparent;
        }}
        QCheckBox::indicator {{
            width: 14px; height: 14px; border-radius: 4px;
            background: {p.ctrl_bg}; border: 1px solid {bd};
        }}
        QCheckBox::indicator:checked {{
            background: {PALETTE_ROSE}; border: 1px solid {PALETTE_ROSE};
        }}
    """


def build_slider_stylesheet(p: ThemePalette) -> str:
    groove_bg = "rgba(255, 255, 255, 34)" if p.is_dark else "rgba(24, 24, 27, 36)"
    handle_bg = "#18181B" if p.is_dark else "#FFFFFF"
    return f"""
        QSlider::groove:horizontal {{
            height: 5px; background: {groove_bg}; border-radius: 2px;
        }}
        QSlider::sub-page:horizontal {{
            background: {p.rose_accent}; border-radius: 2px;
        }}
        QSlider::handle:horizontal {{
            background: {handle_bg}; border: 2px solid {p.rose_accent};
            width: 13px; height: 13px; margin: -4px 0; border-radius: 7px;
        }}
        QSlider::handle:horizontal:hover {{
            border: 2px solid {p.org_accent};
        }}
    """


def build_tree_stylesheet(p: ThemePalette) -> str:
    ind_bd = "rgba(255, 255, 255, 62)" if p.is_dark else "rgba(24, 24, 27, 56)"
    return f"""
        QTreeWidget {{
            {FONT_STYLE_BASE}
            background-color: transparent;
            color: {p.text_fg};
            border: 1px dashed transparent;
            border-radius: 8px;
            outline: none;
            show-decoration-selected: 1;
        }}
        QTreeWidget[dragActive="true"] {{
            border: 1px dashed {p.rose_accent};
            background-color: {p.rose_pill_bg};
        }}
        QHeaderView::section {{
            {FONT_STYLE_BASE}
            background-color: {p.tree_hdr_bg};
            color: {p.muted_fg};
            border: none;
            border-bottom: 1px solid {p.tree_line_col};
            padding: 5px 8px;
            font-weight: bold;
        }}
        QTreeWidget::item {{
            height: 30px;
            padding: 2px 4px;
            border-radius: 5px;
        }}
        QTreeWidget::item:hover {{
            background-color: {p.tree_hover_bg};
        }}
        QTreeWidget::item:selected {{
            background-color: {p.tree_sel_bg};
            color: {p.text_fg};
        }}
        QTreeWidget::indicator {{
            width: 15px;
            height: 15px;
            border-radius: 4px;
            background-color: {p.ctrl_bg};
            border: 1px solid {ind_bd};
        }}
        QTreeWidget::indicator:hover {{
            border: 1px solid {p.rose_accent};
        }}
        QTreeWidget::indicator:checked {{
            background-color: {PALETTE_ROSE};
            border: 1px solid {PALETTE_ROSE};
        }}
        QScrollBar:vertical {{ width: 5px; background: transparent; }}
        QScrollBar::handle:vertical {{
            background: {p.scroll_col}; border-radius: 2px; min-height: 24px;
        }}
        QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{ height: 0px; }}
        QScrollBar:horizontal {{ height: 5px; background: transparent; }}
        QScrollBar::handle:horizontal {{
            background: {p.scroll_col}; border-radius: 2px; min-width: 24px;
        }}
        QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {{ width: 0px; }}
    """


def build_menu_stylesheet(p: ThemePalette) -> str:
    return f"""
        QMenu {{
            {FONT_STYLE_BASE}
            background-color: {p.popup_bg};
            border: {p.popup_bd};
            border-radius: 8px;
            padding: 4px;
        }}
        QMenu::item {{
            padding: 6px 16px;
            border-radius: 5px;
            color: {p.popup_fg};
        }}
        QMenu::item:selected {{
            background-color: {p.rose_pill_bg};
            color: {p.rose_accent};
        }}
    """


def make_folder_pixmap(
    back_hex: str = "#D97706",
    front_hex: str = "#F59E0B",
    size: int = 18,
) -> QPixmap:
    """Draw a crisp flat-vector folder icon that looks sharp on dark glass and light themes."""
    pm = QPixmap(size, size)
    pm.fill(GLOBAL_TRANSPARENT)

    s = float(size)
    painter = QPainter(pm)
    painter.setRenderHint(ANTIALIASING)
    painter.setPen(PEN_NONE)

    # Back folder plate + top-left tab
    back_path = QPainterPath()
    back_path.moveTo(s * 0.08, s * 0.24)
    back_path.quadTo(s * 0.08, s * 0.14, s * 0.18, s * 0.14)
    back_path.lineTo(s * 0.42, s * 0.14)
    back_path.lineTo(s * 0.52, s * 0.26)
    back_path.lineTo(s * 0.84, s * 0.26)
    back_path.quadTo(s * 0.92, s * 0.26, s * 0.92, s * 0.34)
    back_path.lineTo(s * 0.92, s * 0.80)
    back_path.quadTo(s * 0.92, s * 0.88, s * 0.84, s * 0.88)
    back_path.lineTo(s * 0.16, s * 0.88)
    back_path.quadTo(s * 0.08, s * 0.88, s * 0.08, s * 0.80)
    back_path.closeSubpath()
    painter.setBrush(QBrush(QColor(back_hex)))
    painter.drawPath(back_path)

    # Front folder flap
    front_rect = QRectF(s * 0.08, s * 0.34, s * 0.84, s * 0.54)
    painter.setBrush(QBrush(QColor(front_hex)))
    painter.drawRoundedRect(front_rect, s * 0.11, s * 0.11)

    # Subtle top edge highlight on front flap
    highlight = QPen(QColor(255, 255, 255, 72))
    highlight.setWidthF(max(0.8, s * 0.05))
    painter.setPen(highlight)
    painter.drawLine(
        int(round(s * 0.15)),
        int(round(s * 0.37)),
        int(round(s * 0.85)),
        int(round(s * 0.37)),
    )

    painter.end()
    return pm


def make_badge_pixmap(label: str, bg_hex: str, fg_hex: str = "#FFFFFF", size: int = 18) -> QPixmap:
    pm = QPixmap(size, size)
    pm.fill(GLOBAL_TRANSPARENT)
    painter = QPainter(pm)
    painter.setRenderHint(ANTIALIASING)
    painter.setPen(PEN_NONE)
    painter.setBrush(QBrush(QColor(bg_hex)))
    painter.drawRoundedRect(1, 1, size - 2, size - 2, 4, 4)
    painter.setPen(QColor(fg_hex))
    painter.setFont(make_ui_font(6.2 if len(label) > 2 else 7.0, bold=True))
    painter.drawText(QRect(0, 0, size, size), ALIGN_CENTER, label)
    painter.end()
    return pm


def make_app_window_icon(default_png: Optional[Path] = None) -> QIcon:
    if default_png and default_png.is_file():
        ico = QIcon(str(default_png))
        if not ico.isNull():
            return ico
    pm = QPixmap(32, 32)
    pm.fill(GLOBAL_TRANSPARENT)
    p = QPainter(pm)
    p.setRenderHint(ANTIALIASING)
    p.setPen(PEN_NONE)
    p.setBrush(QBrush(QColor(PALETTE_BLACK)))
    p.drawRoundedRect(2, 2, 28, 28, 7, 7)
    p.setBrush(QBrush(QColor(PALETTE_ROSE)))
    p.drawRoundedRect(6, 7, 11, 8, 2, 2)
    p.setBrush(QBrush(QColor(PALETTE_ORANGE)))
    p.drawRoundedRect(15, 17, 11, 8, 2, 2)
    p.end()
    return QIcon(pm)