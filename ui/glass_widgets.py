"""
CRAYON STUDIO — Reusable Apple Glassmorphic & Guided Workflow Widgets
Provides:
- `GlassCard`: Custom QPainter frosted glass container with top-edge specular highlight
- `SelectableStyleCard`: Tactile selection card for Visual Styles and Quality/Cost Render Modes
- `StepIndicatorBar`: Interactive 4-Step "Mom-Proof" Guided Progress Header with smart "Next Step ->" CTA
- `LiveUsagePill`: Real-time API Health & Token/Cost Telemetry Pill with interactive billing popover
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional
from PySide6.QtWidgets import (
    QFrame, QWidget, QHBoxLayout, QVBoxLayout, QLabel, QPushButton,
    QDialog, QGraphicsDropShadowEffect, QSizePolicy
)
from PySide6.QtCore import Qt, Signal, QRectF, QUrl
from PySide6.QtGui import (
    QPainter, QColor, QPen, QLinearGradient, QPainterPath, QDesktopServices, QCursor
)


class GlassCard(QFrame):
    """Translucent frosted glass surface with 16px squircle corners and a 1px top specular highlight."""

    def __init__(self, radius: int = 16, elevated: bool = False, parent: Optional[QWidget] = None):
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

        # Refined middle-ground slate surface gradient
        grad = QLinearGradient(rect.topLeft(), rect.bottomLeft())
        if self.elevated:
            grad.setColorAt(0.0, QColor(50, 56, 70, 240))
            grad.setColorAt(1.0, QColor(42, 48, 60, 235))
        else:
            grad.setColorAt(0.0, QColor(44, 49, 62, 230))
            grad.setColorAt(1.0, QColor(36, 41, 52, 225))

        painter.fillPath(path, grad)

        # Outer border
        painter.setPen(QPen(QColor(255, 255, 255, 26), 1.0))
        painter.drawPath(path)

        # Top specular edge highlight
        painter.setPen(QPen(QColor(255, 255, 255, 48), 1.0))
        painter.drawLine(
            int(rect.left() + self.radius),
            int(rect.top()),
            int(rect.right() - self.radius),
            int(rect.top()),
        )


class SelectableStyleCard(QFrame):
    """Tactile Apple-style clickable selection card with title, badge, and plain-English subtitle."""

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
        self.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        self.setMinimumHeight(74)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(14, 10, 14, 10)
        layout.setSpacing(4)

        top_row = QHBoxLayout()
        top_row.setSpacing(6)
        self.lbl_title = QLabel(icon_and_title)
        self.lbl_title.setStyleSheet("font-weight: 700; font-size: 13px; color: #F5F5F7; background: transparent;")
        top_row.addWidget(self.lbl_title)
        top_row.addStretch()

        self.lbl_badge = QLabel(badge_text)
        self.lbl_badge.setVisible(bool(badge_text))
        self._style_badge()
        top_row.addWidget(self.lbl_badge)
        layout.addLayout(top_row)

        self.lbl_desc = QLabel(description)
        self.lbl_desc.setWordWrap(True)
        self.lbl_desc.setStyleSheet("color: #98989D; font-size: 11.5px; background: transparent;")
        layout.addWidget(self.lbl_desc)

    def _style_badge(self):
        if self._selected:
            self.lbl_badge.setStyleSheet(
                "background-color: rgba(10, 132, 255, 0.28); color: #64D2FF; border-radius: 8px; padding: 2px 8px; font-size: 10.5px; font-weight: 600;"
            )
        else:
            self.lbl_badge.setStyleSheet(
                "background-color: rgba(255, 255, 255, 0.08); color: #98989D; border-radius: 8px; padding: 2px 8px; font-size: 10.5px; font-weight: 600;"
            )

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
            self.clicked.emit(self.key)
        super().mousePressEvent(event)

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        rect = QRectF(self.rect()).adjusted(1.0, 1.0, -1.0, -1.0)
        path = QPainterPath()
        path.addRoundedRect(rect, 12, 12)

        if self._selected:
            painter.fillPath(path, QColor(10, 132, 255, 38))
            painter.setPen(QPen(QColor("#0A84FF"), 1.6))
        else:
            painter.fillPath(path, QColor(36, 40, 52, 155))
            painter.setPen(QPen(QColor(255, 255, 255, 24), 1.0))

        painter.drawPath(path)


class StepIndicatorBar(GlassCard):
    """
    Guided 4-Step Progress Bar at the top of the Studio:
    Always tells a first-time user what step they are on, what input is needed,
    and provides a clear 1-click "Next Step ->" button.
    """
    step_clicked = Signal(int)
    next_action_triggered = Signal(int)

    STEP_TITLES = [
        "1. Pick Topic && Look",
        "2. Write Your Script",
        "3. Voice && Scenes",
        "4. Create Video",
    ]

    STEP_GUIDANCE = {
        0: ("Step 1 of 4: Pick an idea below (or click a suggestion chip), then click 'Write My Script →'", "✨ Write My Script →"),
        1: ("Step 2 of 4: Review your script below. Click any polish chip to tweak it, or continue to Voice & Scenes.", "🎙️ Build Voice && Scenes →"),
        2: ("Step 3 of 4: Your voiceover and visual scenes are ready! Review the cards below or create your final video.", "🎬 Create Final Video →"),
        3: ("Step 4 of 4: Your 9:16 video is ready in the phone preview on the right! Save the MP4 or copy your captions.", "💾 Save Video (.MP4)"),
    }

    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(radius=14, elevated=True, parent=parent)
        self.current_step: int = 0
        self.step_buttons: List[QPushButton] = []
        self._build_ui()
        self.set_step(0)

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 12, 16, 12)
        layout.setSpacing(8)

        # Top Row: 4 Step Pills + Primary Next-Step CTA
        pills_row = QHBoxLayout()
        pills_row.setSpacing(8)

        for idx, title in enumerate(self.STEP_TITLES):
            btn = QPushButton(title)
            btn.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
            btn.clicked.connect(lambda _checked=False, i=idx: self.step_clicked.emit(i))
            pills_row.addWidget(btn)
            self.step_buttons.append(btn)

        pills_row.addStretch()

        self.btn_next_cta = QPushButton("✨ Write My Script →")
        self.btn_next_cta.setProperty("class", "primary")
        self.btn_next_cta.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        self.btn_next_cta.clicked.connect(lambda: self.next_action_triggered.emit(self.current_step))
        pills_row.addWidget(self.btn_next_cta)

        layout.addLayout(pills_row)

        # Bottom Row: Plain-English Guidance Banner
        self.lbl_guidance = QLabel("")
        self.lbl_guidance.setStyleSheet("color: #D1D1D6; font-size: 12.5px; font-weight: 500; background: transparent;")
        layout.addWidget(self.lbl_guidance)

    def set_step(self, step_index: int, custom_guidance: str = "", custom_cta: str = ""):
        self.current_step = max(0, min(3, step_index))
        for i, btn in enumerate(self.step_buttons):
            if i == self.current_step:
                btn.setStyleSheet(
                    "background-color: #0A84FF; color: #FFFFFF; border: 1px solid #409CFF; border-radius: 12px; padding: 5px 14px; font-weight: 700; font-size: 12px;"
                )
            elif i < self.current_step:
                btn.setStyleSheet(
                    "background-color: rgba(48, 209, 88, 0.16); color: #30D158; border: 1px solid rgba(48, 209, 88, 0.4); border-radius: 12px; padding: 5px 14px; font-weight: 600; font-size: 12px;"
                )
            else:
                btn.setStyleSheet(
                    "background-color: rgba(255, 255, 255, 0.05); color: #98989D; border: 1px solid rgba(255, 255, 255, 0.09); border-radius: 12px; padding: 5px 14px; font-weight: 500; font-size: 12px;"
                )

        default_guide, default_cta = self.STEP_GUIDANCE.get(self.current_step, ("", "Next Step →"))
        self.lbl_guidance.setText(custom_guidance or default_guide)
        self.btn_next_cta.setText(custom_cta or default_cta)


class LiveUsagePill(QFrame):
    """
    Top-Bar Glass Telemetry Pill displaying:
    - Live Gemini API Connection / Credit Health Dot (`🟢 Connected` vs `🟠 Free Mode (HTTP 402)`)
    - Session & All-Time Token/Image/Video Spend
    - 1-Click Popover Dialog to test the API key or open Google AI Studio Billing
    """
    open_settings_requested = Signal()

    def __init__(self, usage_tracker_instance: Any, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.tracker = usage_tracker_instance
        self.setProperty("class", "subcard")
        self._build_ui()
        self.tracker.add_listener(self.refresh_from_snapshot)
        self.refresh_from_snapshot(self.tracker.get_snapshot())

    def _build_ui(self):
        layout = QHBoxLayout(self)
        layout.setContentsMargins(12, 5, 10, 5)
        layout.setSpacing(10)

        self.lbl_dot = QLabel("●")
        self.lbl_dot.setStyleSheet("color: #30D158; font-size: 13px; background: transparent;")
        layout.addWidget(self.lbl_dot)

        self.lbl_status = QLabel("Checking API...")
        self.lbl_status.setStyleSheet("color: #F5F5F7; font-weight: 600; font-size: 12px; background: transparent;")
        layout.addWidget(self.lbl_status)

        self.lbl_metrics = QLabel("Session: $0.00")
        self.lbl_metrics.setStyleSheet("color: #98989D; font-size: 11.5px; background: transparent;")
        layout.addWidget(self.lbl_metrics)

        self.btn_details = QPushButton("Usage && Credits ▾")
        self.btn_details.setProperty("class", "chip")
        self.btn_details.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        self.btn_details.clicked.connect(self._show_telemetry_dialog)
        layout.addWidget(self.btn_details)

    def refresh_from_snapshot(self, snap: Dict[str, Any]):
        status = snap.get("api_status", "Unknown")
        if status == "Active":
            self.lbl_dot.setStyleSheet("color: #30D158; font-size: 13px; background: transparent;")
            self.lbl_status.setText("Gemini Connected")
        elif status == "Depleted_402":
            self.lbl_dot.setStyleSheet("color: #FF9F0A; font-size: 13px; background: transparent;")
            self.lbl_status.setText("Credits Depleted (Free Mode Active)")
        elif status == "Invalid_Key":
            self.lbl_dot.setStyleSheet("color: #FF453A; font-size: 13px; background: transparent;")
            self.lbl_status.setText("Invalid API Key (Free Mode)")
        else:
            self.lbl_dot.setStyleSheet("color: #98989D; font-size: 13px; background: transparent;")
            self.lbl_status.setText("Built-In Free Mode")

        sess_cost = float(snap.get("session_cost_usd", 0.0))
        total_cost = float(snap.get("all_time_cost_usd", 0.0))
        sess_imgs = int(snap.get("session_images", 0))
        self.lbl_metrics.setText(f"Session: ${sess_cost:.2f} ({sess_imgs} imgs)  •  All-Time: ${total_cost:.2f}")
        self.setToolTip(snap.get("api_status_detail", ""))

    def _show_telemetry_dialog(self):
        snap = self.tracker.get_snapshot()
        dlg = QDialog(self)
        dlg.setWindowTitle("Live API Credits & Usage Telemetry")
        dlg.setMinimumWidth(440)
        dlg.setStyleSheet(self.window().styleSheet())

        v = QVBoxLayout(dlg)
        v.setContentsMargins(20, 18, 20, 18)
        v.setSpacing(12)

        title = QLabel("Gemini API Health & Usage Ledger")
        title.setStyleSheet("font-size: 16px; font-weight: 700; color: #F5F5F7;")
        v.addWidget(title)

        status_lbl = QLabel(f"Status: {snap.get('api_status_detail')}")
        status_lbl.setWordWrap(True)
        status_lbl.setStyleSheet("color: #64D2FF; font-weight: 600; font-size: 13px;")
        v.addWidget(status_lbl)

        info_box = GlassCard(radius=12)
        ib_layout = QVBoxLayout(info_box)
        ib_layout.setContentsMargins(14, 12, 14, 12)
        ib_layout.setSpacing(6)
        ib_layout.addWidget(QLabel(
            f"• Current Session Tokens: {snap.get('session_tokens', 0):,}\n"
            f"• Current Session Keyframes: {snap.get('session_images', 0)}\n"
            f"• Current Session Omni Video: {snap.get('session_video_seconds', 0.0):.1f}s\n"
            f"• Current Session Estimated Cost: ${snap.get('session_cost_usd', 0.0):.4f}\n\n"
            f"• All-Time Logged Tokens: {snap.get('all_time_tokens', 0):,}\n"
            f"• All-Time Keyframes Generated: {snap.get('all_time_images', 0)}\n"
            f"• All-Time Omni Video Generated: {snap.get('all_time_video_seconds', 0.0):.1f}s\n"
            f"• All-Time Estimated Spend: ${snap.get('all_time_cost_usd', 0.0):.4f}"
        ))
        v.addWidget(info_box)

        note = QLabel(
            "Note: When AI Studio prepayment credits reach $0.00 (HTTP 402), CrayonStudio automatically "
            "switches to its built-in factual writer and 3D procedural cutaway renderer at $0.00 cost so your workflow never breaks."
        )
        note.setWordWrap(True)
        note.setStyleSheet("color: #98989D; font-size: 11.5px;")
        v.addWidget(note)

        btn_row = QHBoxLayout()
        btn_probe = QPushButton("🔄 Test API Key Now")
        btn_probe.clicked.connect(lambda: (self.tracker.probe_api_health(), dlg.accept()))
        btn_row.addWidget(btn_probe)

        btn_billing = QPushButton("💳 Open AI Studio Billing")
        btn_billing.setProperty("class", "primary")
        btn_billing.clicked.connect(lambda: QDesktopServices.openUrl(QUrl("https://ai.studio/projects")))
        btn_row.addWidget(btn_billing)

        btn_settings = QPushButton("⚙️ Change API Key")
        btn_settings.clicked.connect(lambda: (dlg.accept(), self.open_settings_requested.emit()))
        btn_row.addWidget(btn_settings)

        v.addLayout(btn_row)
        dlg.exec()
