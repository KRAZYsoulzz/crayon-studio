"""
CRAYON STUDIO — Apple Pro Graphite/Slate Theme Tokens
Middle-of-the-road tone: neutral graphite slate (not pitch black, not bright light).
Refined, premium desktop aesthetic inspired by Apple Pro creative tools (Final Cut Pro, Logic Pro, Xcode)
and modern high-end software (Linear, Screen Studio, Raycast).
"""

from __future__ import annotations

# =============================================================================
# DESIGN TOKENS (Middle-Tone Graphite Slate Palette)
# =============================================================================
# Canvas & Chromes (Neutral Charcoal/Graphite)
CANVAS_BG = "#1f2229"         # Clean middle-dark slate canvas (~13.5% lightness)
SIDEBAR_BG = "#181a20"        # Grounded sidebar graphite
TOPBAR_BG = "#191b21"         # Cohesive top window bar
SURFACE_FLOATING = "#353a48"  # Modals, popovers, dropdown lists

# Surfaces & Containers (Elevated Slate - clearly distinct from canvas)
CARD_BG = "#282b35"           # Primary cards & panels (~18% lightness)
CARD_ELEVATED_BG = "#303440"  # Elevated cards, active items (~22% lightness)
CARD_HOVER_BG = "#343846"     # Subtle card hover

# Inset Fields (Editors, Inputs)
INPUT_BG = "#181a20"          # Crisp recessed input background
INPUT_FOCUS_BG = "#1b1e27"    # Focused input background
INPUT_BORDER = "#373b47"      # Input border

# Micro-Bevels & Dual-Layer Borders
BORDER_SUBTLE = "rgba(255, 255, 255, 0.08)"
BORDER_CARD = "rgba(255, 255, 255, 0.10)"
BORDER_HIGHLIGHT = "rgba(255, 255, 255, 0.18)"

# Typography (High Legibility, No Murkiness)
TEXT_PRIMARY = "#f9fafb"      # Crisp off-white (headings, titles, active text)
TEXT_SECONDARY = "#9ca3af"    # Neutral silver gray (body, labels)
TEXT_MUTED = "#6e7686"        # Subtle slate gray (eyebrows, placeholders)
TEXT_MONO = "#d1d5db"         # Tabular numbers, timecodes, metrics

# Functional Accents (Restrained Apple Palette)
ACCENT_BLUE = "#0071e3"       # Apple Electric Blue (Primary CTA, focus rings)
ACCENT_BLUE_HOVER = "#0a84ff"
ACCENT_BLUE_PRESSED = "#005bb5"
ACCENT_AMBER = "#f59e0b"      # Warm amber (warnings, credits)
ACCENT_GREEN = "#30d158"      # Apple green (success, readiness)
ACCENT_RED = "#ff453a"        # Apple red (destructive, errors)

# Radii System (Apple HIG Disciplined Standards)
RADIUS_SM = 6                 # Inputs, badges, chips, small buttons
RADIUS_MD = 8                 # Cards, panels, dropdowns
RADIUS_LG = 12                # Modals, floating popovers

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
    letter-spacing: 1.1px;
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
    background-color: rgba(255, 255, 255, 0.06);
    color: {TEXT_MUTED};
    border: 1px solid rgba(255, 255, 255, 0.12);
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
    padding: 8px 12px;
    font-weight: 500;
    font-size: 13px;
    text-align: left;
}}

QPushButton.navBtn:hover {{
    background-color: rgba(255, 255, 255, 0.05);
    color: {TEXT_PRIMARY};
}}

QPushButton.navBtn:checked,
QPushButton.navBtn[active="true"] {{
    background-color: {CARD_BG};
    color: {TEXT_PRIMARY};
    border: 1px solid {BORDER_CARD};
    font-weight: 600;
}}

QPushButton.navBtn:pressed {{
    background-color: rgba(255, 255, 255, 0.03);
}}

/* Top Header Bar */
QFrame#topHeader, QFrame#topBar {{
    background-color: {TOPBAR_BG};
    border-bottom: 1px solid {BORDER_SUBTLE};
}}

/* Cards & Surfaces (8px radii, subtle micro-bevel borders) */
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

/* Pro Desktop Buttons */
QPushButton {{
    background-color: {CARD_ELEVATED_BG};
    color: {TEXT_PRIMARY};
    border: 1px solid {BORDER_CARD};
    border-radius: {RADIUS_SM}px;
    padding: 6px 14px;
    font-weight: 500;
    font-size: 12.5px;
}}

QPushButton:hover {{
    background-color: {CARD_HOVER_BG};
    border: 1px solid {BORDER_HIGHLIGHT};
    color: #ffffff;
}}

QPushButton:pressed {{
    background-color: {INPUT_BG};
    border: 1px solid {BORDER_SUBTLE};
}}

QPushButton:disabled {{
    background-color: rgba(255, 255, 255, 0.02);
    color: rgba(255, 255, 255, 0.25);
    border: 1px solid rgba(255, 255, 255, 0.04);
}}

/* Apple Electric Blue Primary CTA */
QPushButton.primary {{
    background-color: {ACCENT_BLUE};
    color: #ffffff;
    border: 1px solid rgba(255, 255, 255, 0.20);
    border-radius: {RADIUS_SM}px;
    padding: 7px 16px;
    font-weight: 600;
}}

QPushButton.primary:hover {{
    background-color: {ACCENT_BLUE_HOVER};
    border: 1px solid rgba(255, 255, 255, 0.35);
}}

QPushButton.primary:pressed {{
    background-color: {ACCENT_BLUE_PRESSED};
}}

QPushButton.primary:disabled {{
    background-color: rgba(0, 113, 227, 0.20);
    color: rgba(255, 255, 255, 0.40);
    border: 1px solid rgba(255, 255, 255, 0.05);
}}

/* Success Button */
QPushButton.success {{
    background-color: {ACCENT_GREEN};
    color: #04210a;
    border: 1px solid rgba(255, 255, 255, 0.25);
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
}}

/* Hardware Chips (6px radius) */
QPushButton.chip {{
    background-color: {CARD_BG};
    color: {TEXT_SECONDARY};
    border: 1px solid {BORDER_CARD};
    border-radius: {RADIUS_SM}px;
    padding: 4px 10px;
    font-size: 11.5px;
    font-weight: 500;
}}

QPushButton.chip:hover {{
    background-color: {CARD_ELEVATED_BG};
    border-color: {BORDER_HIGHLIGHT};
    color: {TEXT_PRIMARY};
}}

QPushButton.chip:pressed {{
    background-color: {INPUT_BG};
}}

/* Form Inputs & LineEdits */
QLineEdit, QPlainTextEdit, QTextEdit, QSpinBox, QDoubleSpinBox, QComboBox, QDateEdit {{
    background-color: {INPUT_BG};
    color: {TEXT_PRIMARY};
    border: 1px solid {INPUT_BORDER};
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
    selection-color: #ffffff;
    border-radius: {RADIUS_MD}px;
    padding: 4px;
}}

/* Tab Widget (Clean macOS Segmented Tab Style) */
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
    padding: 7px 14px;
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
    background-color: rgba(255, 255, 255, 0.03);
}}

/* Tables & Lists */
QTableWidget, QListWidget {{
    background-color: {CARD_BG};
    alternate-background-color: rgba(255, 255, 255, 0.02);
    border: 1px solid {BORDER_CARD};
    border-radius: {RADIUS_MD}px;
    gridline-color: rgba(255, 255, 255, 0.04);
    color: {TEXT_PRIMARY};
}}

QHeaderView::section {{
    background-color: {SIDEBAR_BG};
    color: {TEXT_MUTED};
    border: none;
    border-bottom: 1px solid {BORDER_CARD};
    padding: 6px 10px;
    font-size: 11px;
    font-weight: 600;
    text-transform: uppercase;
    letter-spacing: 0.8px;
}}

/* Progress Bar */
QProgressBar {{
    background-color: {INPUT_BG};
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
    background: {CARD_ELEVATED_BG};
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
    width: 7px;
    margin: 2px;
}}

QScrollBar::handle:vertical {{
    background: rgba(255, 255, 255, 0.14);
    min-height: 24px;
    border-radius: 3px;
}}

QScrollBar::handle:vertical:hover {{
    background: rgba(255, 255, 255, 0.24);
}}

QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{
    height: 0px;
}}

QScrollBar:horizontal {{
    border: none;
    background: transparent;
    height: 7px;
    margin: 2px;
}}

QScrollBar::handle:horizontal {{
    background: rgba(255, 255, 255, 0.14);
    min-width: 24px;
    border-radius: 3px;
}}

/* Splitters */
QSplitter::handle {{
    background-color: {BORDER_SUBTLE};
}}

QSplitter::handle:hover {{
    background-color: {ACCENT_BLUE};
}}
"""