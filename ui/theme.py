"""
CRAYON STUDIO — Apple macOS Sequoia / visionOS Glassmorphic Theme
Designed with sentence-case typography, translucent layered surfaces, specular borders,
and Apple Human Interface system colors.
"""

from __future__ import annotations

STUDIO_DARK_QSS = """
/* Global Surface & Apple Typography */
QMainWindow, QWidget {
    background-color: #111216;
    color: #F5F5F7;
    font-family: 'SF Pro Display', 'Segoe UI Variable Display', 'Segoe UI', -apple-system, BlinkMacSystemFont, sans-serif;
    font-size: 13px;
}

/* ScrollAreas & Minimalist ScrollBars */
QScrollArea {
    border: none;
    background: transparent;
}
QScrollBar:vertical {
    border: none;
    background: transparent;
    width: 8px;
    margin: 2px;
}
QScrollBar::handle:vertical {
    background: rgba(255, 255, 255, 0.18);
    min-height: 32px;
    border-radius: 4px;
}
QScrollBar::handle:vertical:hover {
    background: rgba(255, 255, 255, 0.30);
}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
    height: 0px;
}
QScrollBar:horizontal {
    border: none;
    background: transparent;
    height: 8px;
    margin: 2px;
}
QScrollBar::handle:horizontal {
    background: rgba(255, 255, 255, 0.18);
    min-width: 32px;
    border-radius: 4px;
}

/* Left macOS Sidebar Rail */
QFrame#navRail {
    background-color: #15171E;
    border-right: 1px solid rgba(255, 255, 255, 0.08);
}
QPushButton.navBtn {
    background-color: transparent;
    color: #98989D;
    border: 1px solid transparent;
    border-radius: 10px;
    padding: 10px 14px;
    text-align: left;
    font-weight: 600;
    font-size: 13px;
}
QPushButton.navBtn:hover {
    background-color: rgba(255, 255, 255, 0.05);
    color: #F5F5F7;
}
QPushButton.navBtn[active="true"] {
    background-color: rgba(10, 132, 255, 0.18);
    color: #F5F5F7;
    border: 1px solid rgba(10, 132, 255, 0.45);
}

/* Top Glass Header Bar */
QFrame#topHeader {
    background-color: #15171E;
    border-bottom: 1px solid rgba(255, 255, 255, 0.08);
}

/* Translucent Glass Cards & Panels */
QFrame.card {
    background-color: rgba(30, 33, 43, 0.78);
    border: 1px solid rgba(255, 255, 255, 0.11);
    border-radius: 16px;
}
QFrame.subcard {
    background-color: rgba(38, 42, 54, 0.65);
    border: 1px solid rgba(255, 255, 255, 0.09);
    border-radius: 12px;
}

/* Buttons — Apple Pill & Squircle Controls */
QPushButton {
    background-color: rgba(255, 255, 255, 0.08);
    color: #F5F5F7;
    border: 1px solid rgba(255, 255, 255, 0.14);
    border-radius: 10px;
    padding: 8px 16px;
    font-weight: 600;
    font-size: 13px;
}
QPushButton:hover {
    background-color: rgba(255, 255, 255, 0.13);
    border: 1px solid rgba(255, 255, 255, 0.22);
}
QPushButton:pressed {
    background-color: rgba(255, 255, 255, 0.05);
}
QPushButton:disabled {
    background-color: rgba(255, 255, 255, 0.03);
    color: #636366;
    border-color: rgba(255, 255, 255, 0.05);
}

/* Apple System Blue Primary CTA (#0A84FF) */
QPushButton.primary {
    background-color: #0A84FF;
    color: #FFFFFF;
    border: 1px solid rgba(255, 255, 255, 0.22);
    border-radius: 10px;
    padding: 9px 18px;
    font-weight: 600;
}
QPushButton.primary:hover {
    background-color: #409CFF;
}
QPushButton.primary:pressed {
    background-color: #0071E3;
}
QPushButton.primary:disabled {
    background-color: rgba(10, 132, 255, 0.25);
    color: rgba(255, 255, 255, 0.45);
}

/* Apple System Green CTA (#30D158) */
QPushButton.success {
    background-color: #248A3D;
    color: #FFFFFF;
    border: 1px solid rgba(48, 209, 88, 0.45);
    border-radius: 11px;
    padding: 10px 20px;
    font-weight: 700;
    font-size: 13px;
}
QPushButton.success:hover {
    background-color: #30D158;
    color: #09120B;
}

/* Soft Suggestion & Quick-Polish Pill Chips */
QPushButton.chip {
    background-color: rgba(255, 255, 255, 0.06);
    color: #D1D1D6;
    border: 1px solid rgba(255, 255, 255, 0.12);
    border-radius: 14px;
    padding: 5px 13px;
    font-size: 12px;
    font-weight: 500;
}
QPushButton.chip:hover {
    background-color: rgba(10, 132, 255, 0.20);
    border-color: rgba(10, 132, 255, 0.55);
    color: #FFFFFF;
}

/* Text Inputs, Editors & Dropdowns */
QLineEdit, QPlainTextEdit, QTextEdit, QSpinBox, QDoubleSpinBox, QComboBox, QDateEdit {
    background-color: rgba(14, 16, 22, 0.75);
    color: #F5F5F7;
    border: 1px solid rgba(255, 255, 255, 0.12);
    border-radius: 10px;
    padding: 8px 12px;
    selection-background-color: #0A84FF;
    font-size: 13px;
}
QLineEdit:focus, QPlainTextEdit:focus, QTextEdit:focus, QSpinBox:focus, QComboBox:focus {
    border: 1px solid #0A84FF;
    background-color: rgba(18, 21, 29, 0.92);
}
QComboBox::drop-down {
    border: none;
    width: 24px;
}
QComboBox QAbstractItemView {
    background-color: #1C1E26;
    border: 1px solid rgba(255, 255, 255, 0.15);
    color: #F5F5F7;
    selection-background-color: #0A84FF;
    border-radius: 8px;
}

/* Tables & Lists */
QTableWidget, QListWidget {
    background-color: rgba(16, 18, 24, 0.65);
    alternate-background-color: rgba(255, 255, 255, 0.03);
    border: 1px solid rgba(255, 255, 255, 0.09);
    border-radius: 12px;
    gridline-color: rgba(255, 255, 255, 0.06);
    color: #F5F5F7;
    selection-background-color: rgba(10, 132, 255, 0.28);
    selection-color: #FFFFFF;
    padding: 4px;
}
QHeaderView::section {
    background-color: rgba(28, 31, 40, 0.9);
    color: #98989D;
    padding: 8px 12px;
    border: none;
    border-bottom: 1px solid rgba(255, 255, 255, 0.09);
    font-weight: 600;
    font-size: 12px;
}

/* Progress Bar */
QProgressBar {
    background-color: rgba(255, 255, 255, 0.08);
    border: none;
    border-radius: 6px;
    height: 10px;
    text-align: center;
    color: transparent;
}
QProgressBar::chunk {
    background-color: #0A84FF;
    border-radius: 6px;
}

/* Sliders */
QSlider::groove:horizontal {
    height: 5px;
    background: rgba(255, 255, 255, 0.14);
    border-radius: 2px;
}
QSlider::sub-page:horizontal {
    background: #0A84FF;
    border-radius: 2px;
}
QSlider::handle:horizontal {
    background: #FFFFFF;
    width: 14px;
    margin-top: -5px;
    margin-bottom: -5px;
    border-radius: 7px;
}

/* Tabs */
QTabWidget::pane {
    border: 1px solid rgba(255, 255, 255, 0.09);
    border-radius: 12px;
    background-color: rgba(24, 27, 36, 0.65);
}
QTabBar::tab {
    background: transparent;
    color: #98989D;
    padding: 7px 14px;
    border-radius: 8px;
    font-weight: 600;
    margin-right: 4px;
}
QTabBar::tab:selected {
    background: rgba(255, 255, 255, 0.10);
    color: #F5F5F7;
}
"""
