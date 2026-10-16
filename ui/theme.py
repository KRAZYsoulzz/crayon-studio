"""
CRAYON STUDIO — Apple Human Interface Guidelines (HIG) macOS-Native Theme Tokens
Centralized design tokens and QSS stylesheet implementing hardware-level polish:
- Deep Obsidian (#090a0c) Canvas
- Translucent Glass Sidebar & Top Chrome: rgba(18, 20, 24, 0.65) with 1px border
- Elevated Charcoal (#13161b) Cards & Containers
- Floating Slate (#1a1e24) Popovers & Dialogs
- Strict Radii: 6px inputs/buttons/badges, 8px cards/menus/players, 12px major dialogs
- Dual-layer micro-bevel borders with 1px specular top highlight
- Zero generic AI tropes (purged emoji titles, purple gradients, glow shadows)
- Monospace tabular data density for metrics and timecodes
- Tactile active depression: transform / pressed depth
"""

from __future__ import annotations

# =============================================================================
# DESIGN TOKENS (Python Constants)
# =============================================================================
CANVAS_BG = "#090a0c"
SIDEBAR_BG = "rgba(18, 20, 24, 0.85)"
TOPBAR_BG = "rgba(18, 20, 24, 0.75)"
CARD_BG = "#13161b"
CARD_ELEVATED_BG = "#171a21"
SURFACE_FLOATING = "#1a1e24"
INPUT_BG = "#0d0f13"
INPUT_FOCUS_BG = "#13161c"

BORDER_SUBTLE = "rgba(255, 255, 255, 0.07)"
BORDER_CARD = "rgba(255, 255, 255, 0.08)"
BORDER_HIGHLIGHT = "rgba(255, 255, 255, 0.14)"

TEXT_PRIMARY = "#f5f5f7"
TEXT_SECONDARY = "#a1a1a6"
TEXT_MUTED = "rgba(255, 255, 255, 0.45)"
TEXT_MONO = "#c7c7cc"

ACCENT_BLUE = "#0071e3"
ACCENT_BLUE_HOVER = "#0077ed"
ACCENT_BLUE_PRESSED = "#005bb5"
ACCENT_AMBER = "#f59e0b"
ACCENT_GREEN = "#30d158"
ACCENT_RED = "#ff453a"

RADIUS_SM = 6
RADIUS_MD = 8
RADIUS_LG = 12

FONT_STACK = (
    '-apple-system, BlinkMacSystemFont, "SF Pro Text", "SF Pro Display", '
    '"Segoe UI Variable Text", "Segoe UI", "Inter", sans-serif'
)
FONT_MONO = 'ui-monospace, "SF Mono", "Cascadia Code", "Consolas", monospace'


# =============================================================================
# GLOBAL APPLICATION QSS
# =============================================================================
STUDIO_DARK_QSS = f"""
/* Global Reset & Typography */
QMainWindow {{
    background-color: {CANVAS_BG};
    color: {TEXT_PRIMARY};
    font-family: {FONT_STACK};
    font-size: 13px;
}}

QWidget {{
    color: {TEXT_PRIMARY};
    font-family: {FONT_STACK};
    font-size: 13px;
    selection-background-color: {ACCENT_BLUE};
    selection-color: #ffffff;
}}

/* Custom Integrated macOS Titlebar */
QFrame#macTitlebar {{
    background-color: {TOPBAR_BG};
    border-bottom: 1px solid {BORDER_SUBTLE};
}}

/* Section Eyebrow Headers */
QLabel.eyebrow {{
    color: {TEXT_MUTED};
    font-size: 10px;
    font-weight: 600;
    text-transform: uppercase;
    letter-spacing: 1.2px;
    background: transparent;
}}

/* Monospace Figures & Metadata */
QLabel.mono, QLabel[class~="mono"] {{
    font-family: {FONT_MONO};
    font-size: 11px;
    color: {TEXT_MONO};
    font-variant-numeric: tabular-nums;
}}

/* Kbd Shortcut Badge */
QLabel.kbdBadge {{
    background-color: rgba(255, 255, 255, 0.05);
    color: {TEXT_MUTED};
    border: 1px solid rgba(255, 255, 255, 0.12);
    border-bottom-color: rgba(255, 255, 255, 0.18);
    border-radius: 4px;
    padding: 1px 5px;
    font-family: {FONT_MONO};
    font-size: 10px;
    font-weight: 600;
}}

/* Left macOS Sidebar Rail */
QFrame#navRail {{
    background-color: {SIDEBAR_BG};
    border-right: 1px solid {BORDER_SUBTLE};
}}

QPushButton.navBtn {{
    background-color: transparent;
    color: {TEXT_SECONDARY};
    border: 1px solid transparent;
    border-radius: {RADIUS_SM}px;
    padding: 7px 12px;
    font-weight: 500;
    font-size: 13px;
    text-align: left;
}}

QPushButton.navBtn:hover {{
    background-color: rgba(255, 255, 255, 0.06);
    color: {TEXT_PRIMARY};
}}

QPushButton.navBtn:checked,
QPushButton.navBtn[active="true"] {{
    background-color: rgba(255, 255, 255, 0.10);
    color: {TEXT_PRIMARY};
    border: 1px solid {BORDER_HIGHLIGHT};
    font-weight: 600;
}}

QPushButton.navBtn:pressed {{
    background-color: rgba(255, 255, 255, 0.04);
    padding-top: 8px;
    padding-bottom: 6px;
}}

/* Top Glass Header Bar */
QFrame#topHeader, QFrame#topBar {{
    background-color: {TOPBAR_BG};
    border-bottom: 1px solid {BORDER_SUBTLE};
}}

/* Cards & Surfaces (8px radii, subtle borders) */
QFrame.card {{
    background-color: {CARD_BG};
    border: 1px solid {BORDER_CARD};
    border-radius: {RADIUS_MD}px;
}}

QFrame.subcard {{
    background-color: {CARD_ELEVATED_BG};
    border: 1px solid {BORDER_CARD};
    border-radius: {RADIUS_MD}px;
}}

/* Hardware Bevel Buttons */
QPushButton {{
    background-color: #1a1e24;
    color: {TEXT_PRIMARY};
    border: 1px solid {BORDER_CARD};
    border-top: 1px solid {BORDER_HIGHLIGHT};
    border-radius: {RADIUS_SM}px;
    padding: 6px 14px;
    font-weight: 500;
    font-size: 12.5px;
}}

QPushButton:hover {{
    background-color: #222730;
    border: 1px solid rgba(255, 255, 255, 0.16);
    border-top: 1px solid rgba(255, 255, 255, 0.24);
    color: #ffffff;
}}

QPushButton:pressed {{
    background-color: #121519;
    border: 1px solid rgba(255, 255, 255, 0.06);
    padding-top: 7px;
    padding-bottom: 5px;
}}

QPushButton:disabled {{
    background-color: rgba(255, 255, 255, 0.03);
    color: rgba(255, 255, 255, 0.25);
    border: 1px solid rgba(255, 255, 255, 0.04);
}}

/* Apple Electric Blue Primary CTA */
QPushButton.primary {{
    background-color: {ACCENT_BLUE};
    color: #ffffff;
    border: 1px solid rgba(255, 255, 255, 0.22);
    border-top: 1px solid rgba(255, 255, 255, 0.40);
    border-radius: {RADIUS_SM}px;
    padding: 7px 16px;
    font-weight: 600;
}}

QPushButton.primary:hover {{
    background-color: {ACCENT_BLUE_HOVER};
    border: 1px solid rgba(255, 255, 255, 0.30);
}}

QPushButton.primary:pressed {{
    background-color: {ACCENT_BLUE_PRESSED};
    padding-top: 8px;
    padding-bottom: 6px;
}}

QPushButton.primary:disabled {{
    background-color: rgba(0, 113, 227, 0.25);
    color: rgba(255, 255, 255, 0.40);
    border: 1px solid rgba(255, 255, 255, 0.06);
}}

/* Apple Green Secondary / Success Action */
QPushButton.success {{
    background-color: {ACCENT_GREEN};
    color: #051608;
    border: 1px solid rgba(255, 255, 255, 0.25);
    border-top: 1px solid rgba(255, 255, 255, 0.45);
    border-radius: {RADIUS_SM}px;
    padding: 7px 16px;
    font-weight: 600;
}}

QPushButton.success:hover {{
    background-color: #38dc62;
    color: #000000;
}}

QPushButton.success:pressed {{
    background-color: #24a845;
    padding-top: 8px;
    padding-bottom: 6px;
}}

/* Restrained Hardware Chips (6px radius) */
QPushButton.chip {{
    background-color: #161920;
    color: {TEXT_SECONDARY};
    border: 1px solid {BORDER_CARD};
    border-radius: {RADIUS_SM}px;
    padding: 4px 10px;
    font-size: 11.5px;
    font-weight: 500;
}}

QPushButton.chip:hover {{
    background-color: #1e222b;
    border-color: rgba(255, 255, 255, 0.18);
    color: {TEXT_PRIMARY};
}}

QPushButton.chip:pressed {{
    background-color: #0f1115;
    padding-top: 5px;
    padding-bottom: 3px;
}}

/* Form Inputs & LineEdits (6px radius, micro-bevel) */
QLineEdit, QPlainTextEdit, QTextEdit, QSpinBox, QDoubleSpinBox, QComboBox, QDateEdit {{
    background-color: {INPUT_BG};
    color: {TEXT_PRIMARY};
    border: 1px solid {BORDER_CARD};
    border-bottom: 1px solid rgba(255, 255, 255, 0.05);
    border-radius: {RADIUS_SM}px;
    padding: 6px 10px;
    font-size: 12.5px;
}}

QLineEdit:focus, QPlainTextEdit:focus, QTextEdit:focus, QSpinBox:focus, QComboBox:focus, QDateEdit:focus {{
    border: 1px solid {ACCENT_BLUE};
    background-color: {INPUT_FOCUS_BG};
}}

QComboBox::drop-down {{
    border: none;
    width: 22px;
}}

QComboBox::down-arrow {{
    image: none;
    border-left: 4px solid transparent;
    border-right: 4px solid transparent;
    border-top: 5px solid {TEXT_MUTED};
    width: 0;
    height: 0;
    margin-right: 8px;
}}

QComboBox QAbstractItemView {{
    background-color: {SURFACE_FLOATING};
    border: 1px solid {BORDER_HIGHLIGHT};
    color: {TEXT_PRIMARY};
    selection-background-color: {ACCENT_BLUE};
    border-radius: {RADIUS_MD}px;
    padding: 4px;
}}

/* Tab Widget (Native macOS Segmented Tab Style) */
QTabWidget::pane {{
    border: 1px solid {BORDER_CARD};
    border-radius: {RADIUS_MD}px;
    background-color: {CARD_BG};
    top: -1px;
}}

QTabBar::tab {{
    background-color: transparent;
    color: {TEXT_SECONDARY};
    border: none;
    padding: 6px 14px;
    font-size: 12px;
    font-weight: 500;
    border-bottom: 2px solid transparent;
}}

QTabBar::tab:selected {{
    color: {TEXT_PRIMARY};
    font-weight: 600;
    border-bottom: 2px solid {ACCENT_BLUE};
}}

QTabBar::tab:hover:!selected {{
    color: {TEXT_PRIMARY};
    background-color: rgba(255, 255, 255, 0.04);
}}

/* Tables & Lists */
QTableWidget, QListWidget {{
    background-color: {CARD_BG};
    alternate-background-color: rgba(255, 255, 255, 0.02);
    border: 1px solid {BORDER_CARD};
    border-radius: {RADIUS_MD}px;
    gridline-color: rgba(255, 255, 255, 0.05);
    color: {TEXT_PRIMARY};
}}

QHeaderView::section {{
    background-color: #171a21;
    color: {TEXT_MUTED};
    border: none;
    border-bottom: 1px solid {BORDER_CARD};
    padding: 6px 10px;
    font-size: 11px;
    font-weight: 600;
    text-transform: uppercase;
    letter-spacing: 0.8px;
}}

/* Native Progress Bar */
QProgressBar {{
    background-color: #121419;
    border: 1px solid {BORDER_CARD};
    border-radius: 4px;
    height: 6px;
    text-align: center;
    color: transparent;
}}

QProgressBar::chunk {{
    background-color: {ACCENT_BLUE};
    border-radius: 3px;
}}

/* Sliders */
QSlider::groove:horizontal {{
    height: 4px;
    background: #1e2229;
    border-radius: 2px;
}}

QSlider::sub-page:horizontal {{
    background: {ACCENT_BLUE};
    border-radius: 2px;
}}

QSlider::handle:horizontal {{
    background: #ffffff;
    width: 14px;
    height: 14px;
    margin-top: -5px;
    margin-bottom: -5px;
    border-radius: 7px;
    border: 1px solid rgba(0, 0, 0, 0.3);
}}

/* ScrollBars */
QScrollArea {{
    border: none;
    background: transparent;
}}

QScrollBar:vertical {{
    border: none;
    background: transparent;
    width: 8px;
    margin: 2px;
}}

QScrollBar::handle:vertical {{
    background: rgba(255, 255, 255, 0.16);
    min-height: 28px;
    border-radius: 4px;
}}

QScrollBar::handle:vertical:hover {{
    background: rgba(255, 255, 255, 0.28);
}}

QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{
    height: 0px;
}}

QScrollBar:horizontal {{
    border: none;
    background: transparent;
    height: 8px;
    margin: 2px;
}}

QScrollBar::handle:horizontal {{
    background: rgba(255, 255, 255, 0.16);
    min-width: 28px;
    border-radius: 4px;
}}

/* Splitters */
QSplitter::handle {{
    background-color: {BORDER_SUBTLE};
}}

QSplitter::handle:hover {{
    background-color: {ACCENT_BLUE};
}}
"""