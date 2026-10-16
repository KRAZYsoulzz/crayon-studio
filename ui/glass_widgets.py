"""
CRAYON STUDIO — Apple HIG Reusable Native Components
Implements:
- `GlassCard`: Layered charcoal surface with 8px radius and dual-layer micro-bevel border
- `SelectableStyleCard`: Hardware-styled option card with 8px radius and active depression
- `StepIndicatorBar`: Segmented 4-step progress header with keyboard shortcut hints
- `LiveUsagePill`: Monospace tabular telemetry pill and 12px floating slate ledger popover
- `MacTitleBar`: Custom integrated macOS titlebar with native traffic light controls & drag zone
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional
from PySide6.QtWidgets import (
    QFrame, QWidget, QHBoxLayout, QVBoxLayout, QLabel, QPushButton,
    QDialog, QGraphicsDropShadowEffect, QSizePolicy
)
from PySide6.QtCore import Qt, Signal, QRectF, QUrl, QPoint
from PySide6.QtGui import (
    QPainter, QColor, QPen, QLinearGradient, QPainterPath, QDesktopServices, QCursor, QFont
)
from ui.theme import (
    CARD_BG, CARD_ELEVATED_BG, SURFACE_FLOATING, BORDER_CARD, BORDER_HIGHLIGHT,
    BORDER_SUBTLE, TEXT_PRIMARY, TEXT_SECONDARY, TEXT_MUTED, TEXT_MONO,
    ACCENT_BLUE, ACCENT_GREEN, ACCENT_AMBER, ACCENT_RED,
    RADIUS_SM, RADIUS_MD, RADIUS_LG, FONT_MONO
)


class MacTitleBar(QFrame):
    """Integrated macOS titlebar with traffic light buttons (Close, Minimize, Maximize)

    and a dedicated drag region for frameless window movement.
    """

    close_clicked = Signal()
    minimize_clicked = Signal()
    maximize_clicked = Signal()

    def __init__(self, title: str = "CrayonStudio", parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.setObjectName("macTitlebar")
        self.setFixedHeight(38)
        self._drag_pos = QPoint()
        self._build_ui(title)

    def _build_ui(self, title: str):
        layout = QHBoxLayout(self)
        layout.setContentsMargins(12, 0, 16, 0)
        layout.setSpacing(8)

        # Traffic Lights Container
        traffic_box = QHBoxLayout()
        traffic_box.setSpacing(8)

        self.btn_close = QPushButton()
        self.btn_close.setFixedSize(12, 12)
        self.btn_close.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        self.btn_close.setToolTip("Close (⌘W / Alt+F4)")
        self.btn_close.setStyleSheet("""
            QPushButton {
                background-color: #ff5f56;
                border: 1px solid rgba(0, 0, 0, 0.25);
                border-radius: 6px;
                padding: 0px;
            }
            QPushButton:hover {
                background-color: #ff3b30;
            }
            QPushButton:pressed {
                background-color: #d72818;
            }
        """)
        self.btn_close.clicked.connect(self.close_clicked.emit)
        traffic_box.addWidget(self.btn_close)

        self.btn_min = QPushButton()
        self.btn_min.setFixedSize(12, 12)
        self.btn_min.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        self.btn_min.setToolTip("Minimize (⌘M)")
        self.btn_min.setStyleSheet("""
            QPushButton {
                background-color: #ffbd2e;
                border: 1px solid rgba(0, 0, 0, 0.25);
                border-radius: 6px;
                padding: 0px;
            }
            QPushButton:hover {
                background-color: #ff9f0a;
            }
            QPushButton:pressed {
                background-color: #d67f00;
            }
        """)
        self.btn_min.clicked.connect(self.minimize_clicked.emit)
        traffic_box.addWidget(self.btn_min)

        self.btn_max = QPushButton()
        self.btn_max.setFixedSize(12, 12)
        self.btn_max.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        self.btn_max.setToolTip("Zoom / Maximize")
        self.btn_max.setStyleSheet("""
            QPushButton {
                background-color: #27c93f;
                border: 1px solid rgba(0, 0, 0, 0.25);
                border-radius: 6px;
                padding: 0px;
            }
            QPushButton:hover {
                background-color: #30d158;
            }
            QPushButton:pressed {
                background-color: #1a9e38;
            }
        """)
        self.btn_max.clicked.connect(self.maximize_clicked.emit)
        traffic_box.addWidget(self.btn_max)

        layout.addLayout(traffic_box)
        layout.addSpacing(12)

        # Centered Window Title
        self.lbl_title = QLabel(title)
        self.lbl_title.setStyleSheet(f"""
            color: {TEXT_SECONDARY};
            font-size: 12px;
            font-weight: 550;
            letter-spacing: -0.01em;
            background: transparent;
        """)
        layout.addWidget(self.lbl_title)
        layout.addStretch()

        # Keyboard Shortcut Reference Pill in Titlebar
        self.lbl_hint = QLabel("Press  Esc  to cancel  •  ⌘↵ to generate")
        self.lbl_hint.setStyleSheet(f"""
            color: {TEXT_MUTED};
            font-size: 11px;
            font-family: {FONT_MONO};
            background: transparent;
        """)
        layout.addWidget(self.lbl_hint)

    def set_title(self, title: str):
        self.lbl_title.setText(title)

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self._drag_pos = event.globalPosition().toPoint() - self.window().frameGeometry().topLeft()
            event.accept()

    def mouseMoveEvent(self, event):
        if event.buttons() == Qt.MouseButton.LeftButton and not self._drag_pos.isNull():
            if not self.window().isMaximized():
                self.window().move(event.globalPosition().toPoint() - self._drag_pos)
                event.accept()

    def mouseDoubleClickEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self.maximize_clicked.emit()
            event.accept()


class GlassCard(QFrame):
    """Elevated Charcoal (#13161b) container with strict 8px corners,

    dual-layer micro-bevel border, and top specular highlight.
    """

    def __init__(self, radius: int = RADIUS_MD, elevated: bool = False, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.radius = radius
        self.elevated = elevated
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, False)

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        rect = QRectF(self.rect()).adjusted(0.5, 0.5, -0.5, -0.5)
        path = QPainterPath()
        path.addRoundedRect(rect, self.radius, self.radius)

        # Dual-Layer Fill: Elevated Charcoal surface
        bg_color = QColor(23, 26, 33, 255) if self.elevated else QColor(19, 22, 27, 255)
        painter.fillPath(path, bg_color)

        # Base 1px micro-bevel border
        painter.setPen(QPen(QColor(255, 255, 255, 18), 1.0))
        painter.drawPath(path)

        # Top specular highlight line (hardware bevel)
        painter.setPen(QPen(QColor(255, 255, 255, 34), 1.0))
        painter.drawLine(
            int(rect.left() + self.radius),
            int(rect.top()),
            int(rect.right() - self.radius),
            int(rect.top()),
        )


class SelectableStyleCard(QFrame):
    """Hardware-styled selection card with 8px radius, optical kerning,

    micro-bevel borders, and active click depression.
    """

    clicked = Signal(str)

    def __init__(
        self,
        key: str,
        icon_and_title: str,
        description: str,
        badge_text: str = "",
        selected: bool = False,
        parent: Optional[QWidget] = None,
    ):
        super().__init__(parent)
        self.key = key
        self._selected = selected
        self._pressed = False
        self.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        self.setMinimumHeight(68)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 9, 12, 9)
        layout.setSpacing(3)

        top_row = QHBoxLayout()
        top_row.setSpacing(6)
        self.lbl_title = QLabel(icon_and_title)
        self.lbl_title.setStyleSheet(f"""
            font-weight: 550;
            font-size: 12.5px;
            letter-spacing: -0.02em;
            color: {TEXT_PRIMARY};
            background: transparent;
        """)
        top_row.addWidget(self.lbl_title)
        top_row.addStretch()

        self.lbl_badge = QLabel(badge_text)
        self.lbl_badge.setVisible(bool(badge_text))
        self._style_badge()
        top_row.addWidget(self.lbl_badge)
        layout.addLayout(top_row)

        self.lbl_desc = QLabel(description)
        self.lbl_desc.setWordWrap(True)
        self.lbl_desc.setStyleSheet(f"color: {TEXT_SECONDARY}; font-size: 11px; background: transparent;")
        layout.addWidget(self.lbl_desc)

    def _style_badge(self):
        if self._selected:
            self.lbl_badge.setStyleSheet(f"""
                background-color: rgba(0, 113, 227, 0.20);
                color: #64d2ff;
                border: 1px solid rgba(0, 113, 227, 0.50);
                border-radius: {RADIUS_SM}px;
                padding: 1px 6px;
                font-size: 10px;
                font-weight: 600;
                font-family: {FONT_MONO};
            """)
        else:
            self.lbl_badge.setStyleSheet(f"""
                background-color: rgba(255, 255, 255, 0.05);
                color: {TEXT_MUTED};
                border: 1px solid rgba(255, 255, 255, 0.08);
                border-radius: {RADIUS_SM}px;
                padding: 1px 6px;
                font-size: 10px;
                font-weight: 500;
                font-family: {FONT_MONO};
            """)

    def set_badge(self, text: str):
        self.lbl_badge.setText(text)
        self.lbl_badge.setVisible(bool(text))
        self._style_badge()

    def set_selected(self, selected: bool):
        if self._selected != selected:
            self._selected = selected
            self._style_badge()
            self.update()

    def is_selected(self) -> bool:
        return self._selected

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self._pressed = True
            self.update()
        super().mousePressEvent(event)

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton and self._pressed:
            self._pressed = False
            self.update()
            self.clicked.emit(self.key)
        super().mouseReleaseEvent(event)

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        # Micro tactile depression on active click
        inset = 1.5 if self._pressed else 1.0
        rect = QRectF(self.rect()).adjusted(inset, inset, -inset, -inset)
        path = QPainterPath()
        path.addRoundedRect(rect, RADIUS_MD, RADIUS_MD)

        if self._selected:
            painter.fillPath(path, QColor(0, 113, 227, 28))
            painter.setPen(QPen(QColor(ACCENT_BLUE), 1.5))
        else:
            painter.fillPath(path, QColor(22, 26, 33, 230))
            painter.setPen(QPen(QColor(255, 255, 255, 18), 1.0))

        painter.drawPath(path)

        # Top specular edge
        if not self._selected:
            painter.setPen(QPen(QColor(255, 255, 255, 30), 1.0))
            painter.drawLine(
                int(rect.left() + RADIUS_MD),
                int(rect.top()),
                int(rect.right() - RADIUS_MD),
                int(rect.top()),
            )


class StepIndicatorBar(GlassCard):
    """Disciplined Segmented 4-Step Progress Header with keyboard shortcut badges (⌘↵)."""

    step_clicked = Signal(int)
    next_action_triggered = Signal(int)

    STEP_TITLES = [
        "1. Topic & Style",
        "2. Script & Polish",
        "3. Voice & Scenes",
        "4. Video Output",
    ]

    STEP_GUIDANCE = {
        0: ("Select an educational topic or enter a custom premise below, then generate your script.", "Generate Script ⌘↵"),
        1: ("Review and refine your script pacing. Target 61–70s for Creator Rewards monetization.", "Build Voice & Scenes ⌘↵"),
        2: ("Preview scene choreography cards and timing. Confirm visuals before compiling video.", "Compile Video ⌘↵"),
        3: ("Final 9:16 vertical video compiled. Review player on right and export high-bitrate MP4.", "Export Video (.MP4)"),
    }

    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(radius=RADIUS_MD, elevated=True, parent=parent)
        self.current_step: int = 0
        self.step_buttons: List[QPushButton] = []
        self._build_ui()
        self.set_step(0)

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(14, 10, 14, 10)
        layout.setSpacing(6)

        # Top Row: 4 Segment Buttons + Next CTA
        pills_row = QHBoxLayout()
        pills_row.setSpacing(6)

        for idx, title in enumerate(self.STEP_TITLES):
            btn = QPushButton(title)
            btn.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
            btn.clicked.connect(lambda _checked=False, i=idx: self.step_clicked.emit(i))
            pills_row.addWidget(btn)
            self.step_buttons.append(btn)

        pills_row.addStretch()

        self.btn_next_cta = QPushButton("Generate Script")
        self.btn_next_cta.setProperty("class", "primary")
        self.btn_next_cta.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        self.btn_next_cta.clicked.connect(lambda: self.next_action_triggered.emit(self.current_step))
        pills_row.addWidget(self.btn_next_cta)

        layout.addLayout(pills_row)

        # Bottom Row: Eyebrow-style guidance note
        self.lbl_guidance = QLabel("")
        self.lbl_guidance.setStyleSheet(f"""
            color: {TEXT_SECONDARY};
            font-size: 11.5px;
            font-weight: 450;
            background: transparent;
        """)
        layout.addWidget(self.lbl_guidance)

    def set_step(self, step_index: int, custom_guidance: str = "", custom_cta: str = ""):
        self.current_step = max(0, min(3, step_index))
        for i, btn in enumerate(self.step_buttons):
            if i == self.current_step:
                btn.setStyleSheet(f"""
                    background-color: {ACCENT_BLUE};
                    color: #ffffff;
                    border: 1px solid rgba(255, 255, 255, 0.3);
                    border-radius: {RADIUS_SM}px;
                    padding: 5px 12px;
                    font-weight: 600;
                    font-size: 11.5px;
                """)
            elif i < self.current_step:
                btn.setStyleSheet(f"""
                    background-color: rgba(48, 209, 88, 0.14);
                    color: {ACCENT_GREEN};
                    border: 1px solid rgba(48, 209, 88, 0.35);
                    border-radius: {RADIUS_SM}px;
                    padding: 5px 12px;
                    font-weight: 550;
                    font-size: 11.5px;
                """)
            else:
                btn.setStyleSheet(f"""
                    background-color: rgba(255, 255, 255, 0.04);
                    color: {TEXT_MUTED};
                    border: 1px solid rgba(255, 255, 255, 0.07);
                    border-radius: {RADIUS_SM}px;
                    padding: 5px 12px;
                    font-weight: 450;
                    font-size: 11.5px;
                """)

        default_guide, default_cta = self.STEP_GUIDANCE.get(self.current_step, ("", "Next Step"))
        self.lbl_guidance.setText(custom_guidance or default_guide)
        self.btn_next_cta.setText(custom_cta or default_cta)


class LiveUsagePill(QFrame):
    """Hardware Telemetry Pill with tabular monospace metrics and 12px floating popover ledger."""

    open_settings_requested = Signal()

    def __init__(self, usage_tracker_instance: Any, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.tracker = usage_tracker_instance
        self.setObjectName("usagePill")
        self.setStyleSheet(f"""
            QFrame#usagePill {{
                background-color: {CARD_BG};
                border: 1px solid {BORDER_CARD};
                border-radius: {RADIUS_SM}px;
            }}
        """)
        self._build_ui()
        self.tracker.add_listener(self.refresh_from_snapshot)
        self.refresh_from_snapshot(self.tracker.get_snapshot())

    def _build_ui(self):
        layout = QHBoxLayout(self)
        layout.setContentsMargins(10, 4, 10, 4)
        layout.setSpacing(8)

        self.lbl_dot = QLabel("●")
        self.lbl_dot.setStyleSheet(f"color: {ACCENT_GREEN}; font-size: 10px; background: transparent;")
        layout.addWidget(self.lbl_dot)

        self.lbl_status = QLabel("Checking API...")
        self.lbl_status.setStyleSheet(f"color: {TEXT_PRIMARY}; font-weight: 550; font-size: 11.5px; background: transparent;")
        layout.addWidget(self.lbl_status)

        self.lbl_metrics = QLabel("Session: $0.00")
        self.lbl_metrics.setStyleSheet(f"""
            color: {TEXT_MONO};
            font-family: {FONT_MONO};
            font-size: 11px;
            font-variant-numeric: tabular-nums;
            background: transparent;
        """)
        layout.addWidget(self.lbl_metrics)

        self.btn_details = QPushButton("Ledger ▾")
        self.btn_details.setProperty("class", "chip")
        self.btn_details.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        self.btn_details.clicked.connect(self._show_telemetry_dialog)
        layout.addWidget(self.btn_details)

    def refresh_from_snapshot(self, snap: Dict[str, Any]):
        status = snap.get("api_status", "Unknown")
        if status == "Active":
            self.lbl_dot.setStyleSheet(f"color: {ACCENT_GREEN}; font-size: 10px; background: transparent;")
            self.lbl_status.setText("Cloud Active")
        elif status == "Depleted_402":
            self.lbl_dot.setStyleSheet(f"color: {ACCENT_AMBER}; font-size: 10px; background: transparent;")
            self.lbl_status.setText("Free Tier / Offline")
        elif status == "Invalid_Key":
            self.lbl_dot.setStyleSheet(f"color: {ACCENT_RED}; font-size: 10px; background: transparent;")
            self.lbl_status.setText("Invalid Key")
        else:
            self.lbl_dot.setStyleSheet(f"color: {TEXT_MUTED}; font-size: 10px; background: transparent;")
            self.lbl_status.setText("Local Standby")

        sess_cost = float(snap.get("session_cost_usd", 0.0))
        total_cost = float(snap.get("all_time_cost_usd", 0.0))
        sess_imgs = int(snap.get("session_images", 0))
        self.lbl_metrics.setText(f"${sess_cost:.2f} ({sess_imgs} frames) | Total: ${total_cost:.2f}")
        self.setToolTip(snap.get("api_status_detail", ""))

    def _show_telemetry_dialog(self):
        snap = self.tracker.get_snapshot()
        dlg = QDialog(self)
        dlg.setWindowTitle("API Telemetry Ledger")
        dlg.setMinimumWidth(460)
        dlg.setStyleSheet(f"""
            QDialog {{
                background-color: {SURFACE_FLOATING};
                border: 1px solid {BORDER_HIGHLIGHT};
                border-radius: {RADIUS_LG}px;
            }}
        """)

        v = QVBoxLayout(dlg)
        v.setContentsMargins(22, 20, 22, 20)
        v.setSpacing(12)

        eyebrow = QLabel("SYSTEM LEDGER & TELEMETRY")
        eyebrow.setProperty("class", "eyebrow")
        eyebrow.setStyleSheet(f"color: {TEXT_MUTED}; font-size: 10px; font-weight: 600; letter-spacing: 1.2px;")
        v.addWidget(eyebrow)

        title = QLabel("Hardware Resource & Spend Accounting")
        title.setStyleSheet(f"font-size: 15px; font-weight: 600; color: {TEXT_PRIMARY}; letter-spacing: -0.02em;")
        v.addWidget(title)

        status_lbl = QLabel(f"Endpoint Status: {snap.get('api_status_detail')}")
        status_lbl.setWordWrap(True)
        status_lbl.setStyleSheet(f"color: #64d2ff; font-weight: 500; font-size: 12px; font-family: {FONT_MONO};")
        v.addWidget(status_lbl)

        info_box = QFrame()
        info_box.setStyleSheet(f"""
            QFrame {{
                background-color: {CARD_BG};
                border: 1px solid {BORDER_CARD};
                border-radius: {RADIUS_MD}px;
                padding: 12px;
            }}
            QLabel {{
                font-family: {FONT_MONO};
                font-size: 11.5px;
                font-variant-numeric: tabular-nums;
                color: {TEXT_SECONDARY};
                background: transparent;
            }}
        """)
        ib_layout = QVBoxLayout(info_box)
        ib_layout.setContentsMargins(12, 10, 12, 10)
        ib_layout.setSpacing(4)
        ib_layout.addWidget(QLabel(
            f"Session In/Out Tokens:      {snap.get('session_tokens', 0):>10,}\n"
            f"Session 9:16 Keyframes:    {snap.get('session_images', 0):>10}\n"
            f"Session Video Rendered:    {snap.get('session_video_seconds', 0.0):>9.1f}s\n"
            f"Session Billed Spend:      ${snap.get('session_cost_usd', 0.0):>9.4f}\n\n"
            f"All-Time Logged Tokens:    {snap.get('all_time_tokens', 0):>10,}\n"
            f"All-Time Keyframe Frames:  {snap.get('all_time_images', 0):>10}\n"
            f"All-Time Video Generated:  {snap.get('all_time_video_seconds', 0.0):>9.1f}s\n"
            f"All-Time Account Spend:    ${snap.get('all_time_cost_usd', 0.0):>9.4f}"
        ))
        v.addWidget(info_box)

        note = QLabel(
            "When cloud billing reaches its limits, the engine gracefully reverts to local procedural "
            "rendering so project composition continues uninterrupted."
        )
        note.setWordWrap(True)
        note.setStyleSheet(f"color: {TEXT_MUTED}; font-size: 11px;")
        v.addWidget(note)

        btn_row = QHBoxLayout()
        btn_probe = QPushButton("Test Connection")
        btn_probe.clicked.connect(lambda: (self.tracker.probe_api_health(), dlg.accept()))
        btn_row.addWidget(btn_probe)

        btn_billing = QPushButton("AI Studio Console")
        btn_billing.setProperty("class", "primary")
        btn_billing.clicked.connect(lambda: QDesktopServices.openUrl(QUrl("https://ai.studio/projects")))
        btn_row.addWidget(btn_billing)

        btn_settings = QPushButton("Configure Key")
        btn_settings.clicked.connect(lambda: (dlg.accept(), self.open_settings_requested.emit()))
        btn_row.addWidget(btn_settings)

        v.addLayout(btn_row)
        dlg.exec()
