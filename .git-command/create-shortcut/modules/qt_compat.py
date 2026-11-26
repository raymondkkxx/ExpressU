# -*- coding: utf-8 -*-
"""
Qt Adaptive Compatibility Layer (PySide6 / PyQt6 / PyQt5)
"""

from __future__ import annotations

import sys

try:
    from PySide6 import QtCore, QtGui, QtWidgets
    from PySide6.QtCore import (
        Qt, QTimer, Signal, QSize, QRect, QRectF, QBuffer, QIODevice, QByteArray,
    )
    from PySide6.QtWidgets import (
        QApplication, QWidget, QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
        QTreeWidget, QTreeWidgetItem, QHeaderView, QGraphicsDropShadowEffect,
        QMenu, QComboBox, QLineEdit, QAbstractItemView, QSlider, QFrame,
        QFileDialog, QSplitter, QScrollArea, QCheckBox,
    )
    from PySide6.QtGui import (
        QIcon, QFont, QColor, QPixmap, QImage, QPainter, QPainterPath, QBrush, QPen,
    )
except ImportError:
    try:
        from PyQt6 import QtCore, QtGui, QtWidgets
        from PyQt6.QtCore import (
            Qt, QTimer, pyqtSignal as Signal, QSize, QRect, QRectF, QBuffer, QIODevice, QByteArray,
        )
        from PyQt6.QtWidgets import (
            QApplication, QWidget, QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
            QTreeWidget, QTreeWidgetItem, QHeaderView, QGraphicsDropShadowEffect,
            QMenu, QComboBox, QLineEdit, QAbstractItemView, QSlider, QFrame,
            QFileDialog, QSplitter, QScrollArea, QCheckBox,
        )
        from PyQt6.QtGui import (
            QIcon, QFont, QColor, QPixmap, QImage, QPainter, QPainterPath, QBrush, QPen,
        )
    except ImportError:
        try:
            from PyQt5 import QtCore, QtGui, QtWidgets
            from PyQt5.QtCore import (
                Qt, QTimer, pyqtSignal as Signal, QSize, QRect, QRectF, QBuffer, QIODevice, QByteArray,
            )
            from PyQt5.QtWidgets import (
                QApplication, QWidget, QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
                QTreeWidget, QTreeWidgetItem, QHeaderView, QGraphicsDropShadowEffect,
                QMenu, QComboBox, QLineEdit, QAbstractItemView, QSlider, QFrame,
                QFileDialog, QSplitter, QScrollArea, QCheckBox,
            )
            from PyQt5.QtGui import (
                QIcon, QFont, QColor, QPixmap, QImage, QPainter, QPainterPath, QBrush, QPen,
            )
        except ImportError:
            print("未检测到 PySide6 / PyQt6 / PyQt5，请在安装有 Qt 的 Python 环境中运行。", file=sys.stderr)
            sys.exit(1)

# Normalize Qt5 / Qt6 Enums
if hasattr(Qt, "WindowType"):
    FLAG_FRAMELESS = Qt.WindowType.FramelessWindowHint | Qt.WindowType.Window
    FLAG_FRAMELESS_DIALOG = Qt.WindowType.FramelessWindowHint | Qt.WindowType.Dialog
    WA_TRANSLUCENT = Qt.WidgetAttribute.WA_TranslucentBackground
    WA_STYLED_BG = Qt.WidgetAttribute.WA_StyledBackground
    KEY_ESC = Qt.Key.Key_Escape
    KEY_RETURN = Qt.Key.Key_Return
    KEY_ENTER = Qt.Key.Key_Enter
    KEY_SPACE = Qt.Key.Key_Space
    KEY_F2 = Qt.Key.Key_F2
    KEY_A = Qt.Key.Key_A
    KEY_F = Qt.Key.Key_F
    MOD_CTRL = Qt.KeyboardModifier.ControlModifier
    CONTEXT_CUSTOM = Qt.ContextMenuPolicy.CustomContextMenu
    SCROLL_PER_PIXEL = QAbstractItemView.ScrollMode.ScrollPerPixel
    SCROLLBAR_OFF = Qt.ScrollBarPolicy.ScrollBarAlwaysOff
    CURSOR_POINTER = Qt.CursorShape.PointingHandCursor
    CURSOR_SIZEALL = Qt.CursorShape.SizeAllCursor
    CURSOR_HOR = Qt.CursorShape.SizeHorCursor
    CURSOR_VER = Qt.CursorShape.SizeVerCursor
    CURSOR_FDIAG = Qt.CursorShape.SizeFDiagCursor
    CURSOR_BDIAG = Qt.CursorShape.SizeBDiagCursor
    MOUSE_LEFT = Qt.MouseButton.LeftButton
    ORIENT_HORIZONTAL = Qt.Orientation.Horizontal
    ALIGN_CENTER = Qt.AlignmentFlag.AlignCenter
    ALIGN_LEFT_VCENTER = Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter
    USER_ROLE = Qt.ItemDataRole.UserRole
    KEEP_ASPECT = Qt.AspectRatioMode.KeepAspectRatio
    SMOOTH_TRANSFORM = Qt.TransformationMode.SmoothTransformation
    GLOBAL_TRANSPARENT = Qt.GlobalColor.transparent
    PEN_NONE = Qt.PenStyle.NoPen
    ANTIALIASING = QPainter.RenderHint.Antialiasing
    IMG_ARGB32 = QImage.Format.Format_ARGB32
    IO_WRITE_ONLY = QIODevice.OpenModeFlag.WriteOnly
    NO_FRAME = QFrame.Shape.NoFrame
    EV_MOVE = QtCore.QEvent.Type.MouseMove
    EV_PRESS = QtCore.QEvent.Type.MouseButtonPress
    EV_RELEASE = QtCore.QEvent.Type.MouseButtonRelease
    CHECK_CHECKED = Qt.CheckState.Checked
    CHECK_UNCHECKED = Qt.CheckState.Unchecked
    ITEM_USER_CHECKABLE = Qt.ItemFlag.ItemIsUserCheckable
    ITEM_ENABLED = Qt.ItemFlag.ItemIsEnabled
    ITEM_SELECTABLE = Qt.ItemFlag.ItemIsSelectable
    HDR_STRETCH = QHeaderView.ResizeMode.Stretch
    HDR_FIXED = QHeaderView.ResizeMode.Fixed
    HDR_RESIZE_TO_CONTENTS = QHeaderView.ResizeMode.ResizeToContents
    HDR_INTERACTIVE = QHeaderView.ResizeMode.Interactive
else:
    FLAG_FRAMELESS = Qt.FramelessWindowHint | Qt.Window
    FLAG_FRAMELESS_DIALOG = Qt.FramelessWindowHint | Qt.Dialog
    WA_TRANSLUCENT = Qt.WA_TranslucentBackground
    WA_STYLED_BG = Qt.WA_StyledBackground
    KEY_ESC = Qt.Key_Escape
    KEY_RETURN = Qt.Key_Return
    KEY_ENTER = Qt.Key_Enter
    KEY_SPACE = Qt.Key_Space
    KEY_F2 = Qt.Key_F2
    KEY_A = Qt.Key_A
    KEY_F = Qt.Key_F
    MOD_CTRL = Qt.ControlModifier
    CONTEXT_CUSTOM = Qt.CustomContextMenu
    SCROLL_PER_PIXEL = QAbstractItemView.ScrollPerPixel
    SCROLLBAR_OFF = Qt.ScrollBarAlwaysOff
    CURSOR_POINTER = Qt.PointingHandCursor
    CURSOR_SIZEALL = Qt.SizeAllCursor
    CURSOR_HOR = Qt.SizeHorCursor
    CURSOR_VER = Qt.SizeVerCursor
    CURSOR_FDIAG = Qt.SizeFDiagCursor
    CURSOR_BDIAG = Qt.SizeBDiagCursor
    MOUSE_LEFT = Qt.LeftButton
    ORIENT_HORIZONTAL = Qt.Horizontal
    ALIGN_CENTER = Qt.AlignCenter
    ALIGN_LEFT_VCENTER = Qt.AlignLeft | Qt.AlignVCenter
    USER_ROLE = Qt.UserRole
    KEEP_ASPECT = Qt.KeepAspectRatio
    SMOOTH_TRANSFORM = Qt.SmoothTransformation
    GLOBAL_TRANSPARENT = Qt.transparent
    PEN_NONE = Qt.NoPen
    ANTIALIASING = QPainter.Antialiasing
    IMG_ARGB32 = QImage.Format_ARGB32
    IO_WRITE_ONLY = QIODevice.WriteOnly
    NO_FRAME = QFrame.NoFrame
    EV_MOVE = QtCore.QEvent.MouseMove
    EV_PRESS = QtCore.QEvent.MouseButtonPress
    EV_RELEASE = QtCore.QEvent.MouseButtonRelease
    CHECK_CHECKED = Qt.Checked
    CHECK_UNCHECKED = Qt.Unchecked
    ITEM_USER_CHECKABLE = Qt.ItemIsUserCheckable
    ITEM_ENABLED = Qt.ItemIsEnabled
    ITEM_SELECTABLE = Qt.ItemIsSelectable
    HDR_STRETCH = QHeaderView.Stretch
    HDR_FIXED = QHeaderView.Fixed
    HDR_RESIZE_TO_CONTENTS = QHeaderView.ResizeToContents
    HDR_INTERACTIVE = QHeaderView.Interactive


def make_ui_font(pt_size: float, bold: bool = False) -> QFont:
    f = QFont()
    f.setFamilies(["Consolas", "Microsoft YaHei UI"])
    f.setPointSizeF(pt_size)
    if bold:
        f.setBold(True)
    return f


def exec_menu(menu: QMenu, global_pos):
    fn = getattr(menu, "exec", None) or menu.exec_
    return fn(global_pos)


def exec_dialog(dialog: QDialog) -> int:
    fn = getattr(dialog, "exec", None) or dialog.exec_
    return int(fn())


def exec_app(app: QApplication) -> int:
    fn = getattr(app, "exec", None) or app.exec_
    return int(fn())


def event_global_pos(event):
    if hasattr(event, "globalPosition"):
        return event.globalPosition().toPoint()
    return event.globalPos()