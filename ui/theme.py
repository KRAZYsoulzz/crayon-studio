"""
CRAYON STUDIO — Refined Middle-Ground Slate / Titanium Theme
A clean, modern workspace theme: not pitch-black, not stark white.
Features warm charcoal/slate surfaces, crisp contrast, and tactile Apple accents.
"""

from __future__ import annotations

STUDIO_DARK_QSS = """
/* Global Slate Surface & Typography */
QMainWindow, QWidget {
    background-color: #1E2129;
    color: #ECEFF4;
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
    background: rgba(255, 255, 255, 0.22);
    min-height: 32px;
    border-radius: 4px;
}
QScrollBar::handle:vertical:hover {
    background: rgba(255, 255, 255, 0.38);
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
    background: rgba(255, 255, 255, 0.22);
    min-width: 32px;
    border-radius: 4px;
}

/* Left Sidebar Rail */
QFrame#navRail {
    background-color: #262A34;
    border-right: 1px solid rgba(255, 255, 255, 0.10);
}
QPushButton.navBtn {
    background-color: transparent;
    color: #B0B5C1;
    border: 1px solid transparent;
    border-radius: 10px;
    padding: 10px 14px;
    font-weight: 600;
    font-size: 13px;
    text-align: left;
}
QPushButton.navBtn:hover {
    background-color: rgba(255, 255, 255, 0.08);
    color: #FFFFFF;
}
QPushButton.navBtn:checked,
QPushButton.navBtn[active="true"] {
    background-color: rgba(10, 132, 255, 0.22);
    color: #FFFFFF;
    border: 1px solid rgba(10, 132, 255, 0.50);
}

/* Top Glass Header Bar */
QFrame#topHeader, QFrame#topBar {
    background-color: #262A34;
    border-bottom: 1px solid rgba(255, 255, 255, 0.10);
}

/* Translucent Cards & Panels */
QFrame.card {
    background-color: #2B303C;
    border: 1px solid rgba(255, 255, 255, 0.12);
    border-radius: 16px;
}
QFrame.subcard {
    background-color: #323846;
    border: 1px solid rgba(255, 255, 255, 0.10);
    border-radius: 12px;
}

/* Buttons */
QPushButton {
    background-color: #343B49;
    color: #ECEFF4;
    border: 1px solid rgba(255, 255, 255, 0.16);
    border-radius: 10px;
    padding: 8px 16px;
    font-weight: 600;
    font-size: 13px;
}
QPushButton:hover {
    background-color: #3F4757;
    border: 1px solid rgba(255, 255, 255, 0.26);
    color: #FFFFFF;
}
QPushButton:pressed {
    background-color: #2B303C;
}
QPushButton:disabled {
    background-color: rgba(255, 255, 255, 0.05);
    color: #7A8191;
    border-color: rgba(255, 255, 255, 0.06);
}

/* Apple System Blue Primary */
QPushButton.primary {
    background-color: #0A84FF;
    color: #FFFFFF;
    border: 1px solid rgba(255, 255, 255, 0.28);
    border-radius: 10px;
    padding: 9px 18px;
    font-weight: 600;
}
QPushButton.primary:hover {
    background-color: #3399FF;
}
QPushButton.primary:pressed {
    background-color: #0071E3;
}
QPushButton.primary:disabled {
    background-color: rgba(10, 132, 255, 0.30);
    color: rgba(255, 255, 255, 0.50);
}

/* Apple System Green CTA */
QPushButton.success {
    background-color: #2DB84D;
    color: #FFFFFF;
    border: 1px solid rgba(48, 209, 88, 0.45);
    border-radius: 11px;
    padding: 10px 20px;
    font-weight: 700;
    font-size: 13px;
}
QPushButton.success:hover {
    background-color: #34C759;
    color: #09120B;
}

/* Suggestion & Quick-Polish Pill Chips */
QPushButton.chip {
    background-color: #2F3543;
    color: #D8DEE9;
    border: 1px solid rgba(255, 255, 255, 0.15);
    border-radius: 14px;
    padding: 5px 13px;
    font-size: 12px;
    font-weight: 500;
}
QPushButton.chip:hover {
    background-color: rgba(10, 132, 255, 0.25);
    border-color: rgba(10, 132, 255, 0.60);
    color: #FFFFFF;
}

/* Text Inputs, Editors & Dropdowns */
QLineEdit, QPlainTextEdit, QTextEdit, QSpinBox, QDoubleSpinBox, QComboBox, QDateEdit {
    background-color: #232731;
    color: #ECEFF4;
    border: 1px solid rgba(255, 255, 255, 0.15);
    border-radius: 10px;
    padding: 8px 12px;
    selection-background-color: #0A84FF;
    font-size: 13px;
}
QLineEdit:focus, QPlainTextEdit:focus, QTextEdit:focus, QSpinBox:focus, QComboBox:focus {
    border: 1px solid #0A84FF;
    background-color: #262B36;
}
QComboBox::drop-down {
    border: none;
    width: 24px;
}
QComboBox QAbstractItemView {
    background-color: #262B36;
    border: 1px solid rgba(255, 255, 255, 0.18);
    color: #ECEFF4;
    selection-background-color: #0A84FF;
    border-radius: 8px;
}

/* Tables & Lists */
QTableWidget, QListWidget {
    background-color: #232731;
    alternate-background-color: rgba(255, 255, 255, 0.03);
    border: 1px solid rgba(255, 255, 255, 0.12);
    border-radius: 12px;
    gridline-color: rgba(255, 255, 255, 0.08);
    color: #ECEFF4;
}
QHeaderView::section {
    background-color: #2A2F3B;
    color: #B0B5C1;
    border: none;
    border-bottom: 1px solid rgba(255, 255, 255, 0.10);
    padding: 8px 10px;
    font-weight: 600;
}

/* Progress Bars */
QProgressBar {
    background-color: #232731;
    border: 1px solid rgba(255, 255, 255, 0.10);
    border-radius: 7px;
    height: 12px;
    text-align: center;
    color: transparent;
}
QProgressBar::chunk {
    background-color: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #0A84FF, stop:1 #30D158);
    border-radius: 6px;
}

/* Sliders */
QSlider::groove:horizontal {
    height: 5px;
    background: #343B49;
    border-radius: 2px;
}
QSlider::sub-page:horizontal {
    background: #0A84FF;
    border-radius: 2px;
}
QSlider::handle:horizontal {
    background: #FFFFFF;
    width: 15px;
    margin-top: -5px;
    margin-bottom: -5px;
    border-radius: 7px;
    border: 1px solid rgba(0, 0, 0, 0.20);
}
"""