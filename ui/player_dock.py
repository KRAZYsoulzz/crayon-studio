import os
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QSlider, QLineEdit, QPlainTextEdit, QCheckBox, QTabWidget,
    QFrame, QStackedWidget, QSizePolicy, QApplication
)
from PySide6.QtCore import Qt, QRect, QRectF, QUrl, Signal
from PySide6.QtGui import (
    QPainter, QColor, QFont, QPen, QLinearGradient, QPixmap, QPainterPath, QCursor
)
from PySide6.QtMultimedia import QMediaPlayer, QAudioOutput
from PySide6.QtMultimediaWidgets import QVideoWidget
from ui.glass_widgets import GlassCard


class LiveStoryboardCanvas(QWidget):
    """
    Real-time 9:16 vertical phone preview canvas framed inside a rounded iPhone-style bezel.
    Renders generated scene keyframes with smooth 2.5D Ken Burns motion and kinetic captions.
    """
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMinimumSize(200, 355)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self.words: list[dict] = []
        self.scenes: list[dict] = []
        self.project_dir: str = ""
        self.current_time: float = 0.0
        self.duration: float = 45.0
        self.visual_style: str = "3D_Pixar"
        self._pixmap_cache: dict[str, QPixmap] = {}

    def set_project_data(
        self,
        words: list[dict],
        scenes: list[dict],
        project_dir: str,
        visual_style: str = "3D_Pixar",
        duration: float = 45.0,
    ):
        self.words = words or []
        self.scenes = scenes or []
        self.project_dir = project_dir or ""
        self.visual_style = visual_style
        if self.words:
            self.duration = max(float(self.words[-1].get("end", duration)), 1.0)
        elif self.scenes:
            self.duration = max(
                float(self.scenes[-1].get("end_time", self.scenes[-1].get("end", duration))),
                1.0,
            )
        else:
            self.duration = max(duration, 1.0)
        self._pixmap_cache.clear()
        self.update()

    def set_time(self, t: float):
        self.current_time = max(0.0, t)
        self.update()

    def _get_active_scene(self) -> tuple[int, dict]:
        if not self.scenes:
            return 0, {}
        for idx, s in enumerate(self.scenes):
            start_t = float(s.get("start_time", s.get("start", 0.0)))
            end_t = float(s.get("end_time", s.get("end", start_t + 5.0)))
            if start_t <= self.current_time <= end_t:
                return idx, s
        return len(self.scenes) - 1, self.scenes[-1]

    def _get_scene_pixmap(self, idx: int, scene: dict) -> QPixmap | None:
        img_path = scene.get("image_path", "")
        if not img_path and self.project_dir:
            for candidate in (
                os.path.join(self.project_dir, "storyboard", f"scene_{idx + 1:02d}.png"),
                os.path.join(self.project_dir, f"scene_{idx + 1:02d}.png"),
            ):
                if os.path.exists(candidate):
                    img_path = candidate
                    break
        if not img_path or not os.path.exists(img_path):
            return None
        mtime_key = f"{img_path}:{int(os.path.getmtime(img_path))}"
        if mtime_key not in self._pixmap_cache:
            pix = QPixmap(img_path)
            if not pix.isNull():
                self._pixmap_cache[mtime_key] = pix
        return self._pixmap_cache.get(mtime_key)

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)

        w, h = self.width(), self.height()
        target_w = min(w - 8, int((h - 8) * 9 / 16))
        target_h = int(target_w * 16 / 9)
        x_off = (w - target_w) // 2
        y_off = (h - target_h) // 2
        frame_rect = QRect(x_off, y_off, target_w, target_h)
        bezel_path = QPainterPath()
        bezel_path.addRoundedRect(QRectF(frame_rect), 22, 22)

        painter.save()
        painter.setClipPath(bezel_path)

        idx, active_scene = self._get_active_scene()
        pix = self._get_scene_pixmap(idx, active_scene)

        if pix and not pix.isNull():
            s_start = float(active_scene.get("start_time", active_scene.get("start", 0.0)))
            s_end = max(float(active_scene.get("end_time", active_scene.get("end", s_start + 5.0))), s_start + 0.1)
            local_prog = max(0.0, min(1.0, (self.current_time - s_start) / (s_end - s_start)))
            zoom = 1.0 + 0.06 * local_prog

            scaled_w = int(target_w * zoom)
            scaled_h = int(target_h * zoom)
            scaled_pix = pix.scaled(
                scaled_w,
                scaled_h,
                Qt.AspectRatioMode.KeepAspectRatioByExpanding,
                Qt.TransformationMode.SmoothTransformation,
            )
            px = x_off - (scaled_pix.width() - target_w) // 2
            py = y_off - (scaled_pix.height() - target_h) // 2
            painter.drawPixmap(px, py, scaled_pix)
        else:
            grad = QLinearGradient(x_off, y_off, x_off, y_off + target_h)
            grad.setColorAt(0.0, QColor("#181C28"))
            grad.setColorAt(0.5, QColor("#1E2436"))
            grad.setColorAt(1.0, QColor("#101218"))
            painter.fillRect(frame_rect, grad)

            painter.setPen(QColor("#AEAEB2"))
            painter.setFont(QFont("Segoe UI", 9, QFont.Weight.DemiBold))
            prompt_preview = (
                active_scene.get("action_desc")
                or active_scene.get("prompt")
                or "Your 9:16 video preview will appear here as you build your script and scenes."
            )
            if len(prompt_preview) > 135:
                prompt_preview = prompt_preview[:132] + "..."
            painter.drawText(
                QRect(x_off + 22, y_off + int(target_h * 0.26), target_w - 44, int(target_h * 0.36)),
                Qt.AlignmentFlag.AlignCenter | Qt.TextFlag.TextWordWrap,
                f"Scene {idx + 1} Preview\n\n{prompt_preview}",
            )

        # Dynamic Island-style Top Pill
        island_w = min(target_w - 32, 180)
        island_rect = QRectF(x_off + (target_w - island_w) / 2.0, y_off + 10, island_w, 24)
        island_path = QPainterPath()
        island_path.addRoundedRect(island_rect, 12, 12)
        painter.fillPath(island_path, QColor(12, 13, 18, 210))
        painter.setPen(QColor("#F5F5F7"))
        painter.setFont(QFont("Segoe UI", 8, QFont.Weight.DemiBold))
        painter.drawText(
            island_rect,
            Qt.AlignmentFlag.AlignCenter,
            f"Scene {idx + 1} of {max(len(self.scenes), 1)}  •  {self.current_time:04.1f}s",
        )

        # Kinetic 4-Word Subtitle Block (Bottom-Center)
        if self.words:
            active_w_idx = -1
            for i, w_info in enumerate(self.words):
                if float(w_info.get("start", 0.0)) <= self.current_time <= float(w_info.get("end", 0.0)) + 0.15:
                    active_w_idx = i
                    break
            if active_w_idx >= 0:
                chunk_start = (active_w_idx // 4) * 4
                chunk = self.words[chunk_start : chunk_start + 4]
                cap_rect = QRect(
                    x_off + 14,
                    y_off + int(target_h * 0.68),
                    target_w - 28,
                    int(target_h * 0.17),
                )
                cap_path = QPainterPath()
                cap_path.addRoundedRect(QRectF(cap_rect), 10, 10)
                painter.fillPath(cap_path, QColor(0, 0, 0, 155))
                font = QFont("Segoe UI", max(11, int(target_w * 0.050)), QFont.Weight.Black)
                painter.setFont(font)

                lines = [chunk[:2], chunk[2:4]]
                for line_idx, line_words in enumerate(lines):
                    if not line_words:
                        continue
                    line_y = cap_rect.top() + 6 + line_idx * (cap_rect.height() // 2)
                    line_text = " ".join(str(w_item.get("word", "")).upper() for w_item in line_words)
                    has_active = any(
                        (chunk_start + line_idx * 2 + j) == active_w_idx for j in range(len(line_words))
                    )
                    painter.setPen(QColor("#000000"))
                    painter.drawText(
                        QRect(cap_rect.left() + 2, line_y + 2, cap_rect.width(), cap_rect.height() // 2),
                        Qt.AlignmentFlag.AlignCenter,
                        line_text,
                    )
                    painter.setPen(QColor("#FFD60A") if has_active else QColor("#FFFFFF"))
                    painter.drawText(
                        QRect(cap_rect.left(), line_y, cap_rect.width(), cap_rect.height() // 2),
                        Qt.AlignmentFlag.AlignCenter,
                        line_text,
                    )

        painter.restore()
        # Sleek outer titanium-style phone bezel ring
        painter.setPen(QPen(QColor(255, 255, 255, 42), 1.6))
        painter.drawPath(bezel_path)


class PlayerInspectorDock(GlassCard):
    """
    Persistent Right 9:16 Phone Preview & Export Dock:
    - Sleek iPhone-bezel 9:16 monitor (`LiveStoryboardCanvas` + `QVideoWidget`)
    - Clean Quick Visual Tweak input & 4-snapshot quality strip
    - One-click Save Video (.MP4) & Title/Hashtag assistant
    """
    visual_revision_requested = Signal(str)
    autofill_metadata_requested = Signal()
    save_calendar_requested = Signal()
    export_mp4_requested = Signal()
    dispatch_webhook_requested = Signal()
    metadata_changed = Signal()

    reset_preview_requested = Signal()

    def __init__(self, parent=None):
        super().__init__(radius=18, elevated=True, parent=parent)
        self.setMinimumWidth(280)
        self.setMaximumWidth(390)
        self.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Expanding)
        self.current_video_path: str = ""
        self._build_ui()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(14, 14, 14, 14)
        layout.setSpacing(10)

        # Header + View Mode Switch + Reset Preview
        header = QHBoxLayout()
        lbl_hdr = QLabel("Phone Preview (9:16)")
        lbl_hdr.setStyleSheet("color: #F5F5F7; font-weight: 700; font-size: 13px; background: transparent;")
        header.addWidget(lbl_hdr)
        header.addStretch()

        self.btn_mode_canvas = QPushButton("🖼️ Scenes")
        self.btn_mode_canvas.setProperty("class", "chip")
        self.btn_mode_canvas.clicked.connect(lambda: self.preview_stack.setCurrentIndex(0))
        header.addWidget(self.btn_mode_canvas)

        self.btn_mode_video = QPushButton("🎬 Final MP4")
        self.btn_mode_video.setProperty("class", "chip")
        self.btn_mode_video.clicked.connect(lambda: self.preview_stack.setCurrentIndex(1))
        header.addWidget(self.btn_mode_video)

        self.btn_reset_preview = QPushButton("🗑️")
        self.btn_reset_preview.setProperty("class", "chip")
        self.btn_reset_preview.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        self.btn_reset_preview.setToolTip("Reset preview canvas & clear loaded video")
        self.btn_reset_preview.clicked.connect(self.clear_preview)
        header.addWidget(self.btn_reset_preview)
        layout.addLayout(header)

        # 9:16 Preview Stack
        self.preview_stack = QStackedWidget()
        self.live_canvas = LiveStoryboardCanvas()
        self.preview_stack.addWidget(self.live_canvas)

        self.video_widget = QVideoWidget()
        self.preview_stack.addWidget(self.video_widget)
        layout.addWidget(self.preview_stack, stretch=3)

        # Media Player
        self.media_player = QMediaPlayer()
        self.audio_output = QAudioOutput()
        self.media_player.setAudioOutput(self.audio_output)
        self.media_player.setVideoOutput(self.video_widget)
        self.media_player.positionChanged.connect(self._on_position_changed)
        self.media_player.durationChanged.connect(self._on_duration_changed)

        # Minimal Transport Bar
        transport = QHBoxLayout()
        self.btn_play = QPushButton("▶ Play")
        self.btn_play.setFixedWidth(74)
        self.btn_play.clicked.connect(self.toggle_playback)
        transport.addWidget(self.btn_play)

        self.slider_seek = QSlider(Qt.Orientation.Horizontal)
        self.slider_seek.setRange(0, 45000)
        self.slider_seek.sliderMoved.connect(self._on_slider_moved)
        transport.addWidget(self.slider_seek, stretch=1)

        self.lbl_time = QLabel("00:00 / 00:45")
        self.lbl_time.setStyleSheet("color: #98989D; font-size: 11px; background: transparent;")
        transport.addWidget(self.lbl_time)
        layout.addLayout(transport)

        # Clean Quick Visual Tweak & Quality Check Card
        critic_card = GlassCard(radius=12)
        critic_layout = QVBoxLayout(critic_card)
        critic_layout.setContentsMargins(10, 8, 10, 8)
        critic_layout.setSpacing(6)

        critic_hdr = QHBoxLayout()
        lbl_critic_title = QLabel("Quick Visual Tweak & Quality Check")
        lbl_critic_title.setStyleSheet("color: #F5F5F7; font-weight: 600; font-size: 12px; background: transparent;")
        critic_hdr.addWidget(lbl_critic_title)
        critic_hdr.addStretch()
        self.lbl_critic_status = QLabel("Standby")
        self.lbl_critic_status.setStyleSheet("color: #98989D; font-size: 11px; background: transparent;")
        critic_hdr.addWidget(self.lbl_critic_status)
        critic_layout.addLayout(critic_hdr)

        thumbs_row = QHBoxLayout()
        thumbs_row.setSpacing(6)
        self.critic_thumbs: list[QLabel] = []
        for tag in ["Opening", "Cutaway", "Action", "Loop"]:
            lbl = QLabel(tag)
            lbl.setFixedSize(72, 88)
            lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
            lbl.setStyleSheet(
                "background-color: #14161E; border: 1px solid rgba(255,255,255,0.10); border-radius: 8px; color: #98989D; font-size: 10px;"
            )
            thumbs_row.addWidget(lbl)
            self.critic_thumbs.append(lbl)
        critic_layout.addLayout(thumbs_row)

        rev_row = QHBoxLayout()
        self.input_visual_revision = QLineEdit()
        self.input_visual_revision.setPlaceholderText("Want to change a scene? (e.g., 'Scene 1: zoom closer')...")
        self.input_visual_revision.returnPressed.connect(self._emit_visual_revision)
        rev_row.addWidget(self.input_visual_revision, stretch=1)

        self.btn_apply_visual_revision = QPushButton("Update")
        self.btn_apply_visual_revision.setProperty("class", "primary")
        self.btn_apply_visual_revision.clicked.connect(self._emit_visual_revision)
        rev_row.addWidget(self.btn_apply_visual_revision)
        critic_layout.addLayout(rev_row)
        layout.addWidget(critic_card)

        # Bottom Sub-Tabs: Save & Captions | Quality Checklist
        self.sub_tabs = QTabWidget()

        # Tab 1: Save Video & Social Captions (Primary for everyday users)
        meta_tab = QWidget()
        meta_layout = QVBoxLayout(meta_tab)
        meta_layout.setContentsMargins(10, 8, 10, 8)
        meta_layout.setSpacing(6)

        self.meta_title = QLineEdit()
        self.meta_title.setPlaceholderText("Video Title (click 'Auto-Fill' to generate)...")
        self.meta_title.textChanged.connect(lambda _: self.metadata_changed.emit())
        meta_layout.addWidget(self.meta_title)

        self.meta_description = QPlainTextEdit()
        self.meta_description.setPlaceholderText("Short video caption / description...")
        self.meta_description.setFixedHeight(44)
        self.meta_description.textChanged.connect(self.metadata_changed.emit)
        meta_layout.addWidget(self.meta_description)

        self.meta_hashtags = QLineEdit()
        self.meta_hashtags.setPlaceholderText("#shorts #howthingswork #science #fyp")
        self.meta_hashtags.textChanged.connect(lambda _: self.metadata_changed.emit())
        meta_layout.addWidget(self.meta_hashtags)

        btn_row1 = QHBoxLayout()
        self.btn_autofill_meta = QPushButton("✨ Auto-Fill Captions")
        self.btn_autofill_meta.setProperty("class", "chip")
        self.btn_autofill_meta.clicked.connect(self.autofill_metadata_requested.emit)
        btn_row1.addWidget(self.btn_autofill_meta)

        self.btn_copy_meta = QPushButton("📋 Copy Info")
        self.btn_copy_meta.setProperty("class", "chip")
        self.btn_copy_meta.clicked.connect(self._copy_meta_to_clipboard)
        btn_row1.addWidget(self.btn_copy_meta)

        self.btn_save_calendar = QPushButton("📅 Calendar")
        self.btn_save_calendar.setProperty("class", "chip")
        self.btn_save_calendar.clicked.connect(self.save_calendar_requested.emit)
        btn_row1.addWidget(self.btn_save_calendar)
        meta_layout.addLayout(btn_row1)

        btn_row2 = QHBoxLayout()
        self.btn_export_mp4 = QPushButton("💾 Save Video (.MP4)")
        self.btn_export_mp4.setProperty("class", "success")
        self.btn_export_mp4.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        self.btn_export_mp4.clicked.connect(self.export_mp4_requested.emit)
        btn_row2.addWidget(self.btn_export_mp4, stretch=2)

        self.btn_dispatch = QPushButton("🚀 Publish")
        self.btn_dispatch.clicked.connect(self.dispatch_webhook_requested.emit)
        btn_row2.addWidget(self.btn_dispatch, stretch=1)
        meta_layout.addLayout(btn_row2)

        self.sub_tabs.addTab(meta_tab, "💾 Save && Captions")

        # Tab 2: Viral Quality Checklist
        ret_tab = QWidget()
        ret_layout = QVBoxLayout(ret_tab)
        ret_layout.setContentsMargins(10, 8, 10, 8)
        ret_layout.setSpacing(4)

        score_row = QHBoxLayout()
        score_row.addWidget(QLabel("Quality Score:"))
        score_row.addStretch()
        self.lbl_retention_score = QLabel("100% Ready")
        self.lbl_retention_score.setStyleSheet("color: #30D158; font-weight: 700;")
        score_row.addWidget(self.lbl_retention_score)
        ret_layout.addLayout(score_row)

        self.chk_ret_hook = QCheckBox("Strong Opening Hook (First 3 Seconds)")
        self.chk_ret_loop = QCheckBox("Smooth Loop Ending into Opening Line")
        self.chk_ret_pacing = QCheckBox("Clear Voiceover + Word-Synced Captions")
        self.chk_ret_visual = QCheckBox("All 4 Scene Keyframes Verified")
        self.chk_ret_bridge = QCheckBox("Focused Story Flow")
        for chk in (
            self.chk_ret_hook,
            self.chk_ret_loop,
            self.chk_ret_pacing,
            self.chk_ret_visual,
            self.chk_ret_bridge,
        ):
            chk.setChecked(True)
            chk.stateChanged.connect(self.update_retention_score)
            ret_layout.addWidget(chk)

        self.sub_tabs.addTab(ret_tab, "✓ Quality Check")
        layout.addWidget(self.sub_tabs, stretch=2)

    def _copy_meta_to_clipboard(self):
        bundle = f"{self.meta_title.text()}\n\n{self.meta_description.toPlainText()}\n\n{self.meta_hashtags.text()}".strip()
        QApplication.clipboard().setText(bundle)

    def _emit_visual_revision(self):
        text = self.input_visual_revision.text().strip()
        if text:
            self.visual_revision_requested.emit(text)

    def update_retention_score(self):
        checks = [
            self.chk_ret_hook.isChecked(),
            self.chk_ret_loop.isChecked(),
            self.chk_ret_pacing.isChecked(),
            self.chk_ret_visual.isChecked(),
            self.chk_ret_bridge.isChecked(),
        ]
        score = int(sum(1 for c in checks if c) * 20)
        color = "#30D158" if score >= 80 else "#FF9F0A"
        self.lbl_retention_score.setText(f"{score}% Ready")
        self.lbl_retention_score.setStyleSheet(f"color: {color}; font-weight: 700;")

    def load_video(self, video_path: str):
        if video_path and os.path.exists(video_path):
            self.current_video_path = video_path
            self.media_player.setSource(QUrl.fromLocalFile(video_path))
            self.preview_stack.setCurrentIndex(1)

    def load_critic_report(self, report: dict):
        if not report:
            return
        frames = report.get("snapshots") or report.get("frames", [])
        for i, lbl in enumerate(self.critic_thumbs):
            if i < len(frames) and os.path.exists(frames[i]):
                pix = QPixmap(frames[i])
                if not pix.isNull():
                    lbl.setPixmap(
                        pix.scaled(
                            lbl.size(),
                            Qt.AspectRatioMode.KeepAspectRatioByExpanding,
                            Qt.TransformationMode.SmoothTransformation,
                        )
                    )
        passed = report.get("passed", False)
        summary = report.get("notes") or report.get("summary", "Verified")
        self.lbl_critic_status.setText("✓ Verified Ready" if passed else summary[:26])
        self.lbl_critic_status.setToolTip(summary)
        self.lbl_critic_status.setStyleSheet(
            f"color: {'#30D158' if passed else '#FF453A'}; font-weight: 600; font-size: 11px; background: transparent;"
        )

    def toggle_playback(self):
        if self.preview_stack.currentIndex() == 1 and self.current_video_path:
            if self.media_player.playbackState() == QMediaPlayer.PlaybackState.PlayingState:
                self.media_player.pause()
                self.btn_play.setText("▶ Play")
            else:
                self.media_player.play()
                self.btn_play.setText("⏸ Pause")
        else:
            next_val = (self.slider_seek.value() + 1500) % max(self.slider_seek.maximum(), 1000)
            self.slider_seek.setValue(next_val)
            self._on_slider_moved(next_val)

    def _on_position_changed(self, pos_ms: int):
        self.slider_seek.blockSignals(True)
        self.slider_seek.setValue(pos_ms)
        self.slider_seek.blockSignals(False)
        self.live_canvas.set_time(pos_ms / 1000.0)
        dur_s = max(1, self.media_player.duration() // 1000)
        cur_s = pos_ms // 1000
        self.lbl_time.setText(f"{cur_s // 60:02d}:{cur_s % 60:02d} / {dur_s // 60:02d}:{dur_s % 60:02d}")

    def _on_duration_changed(self, dur_ms: int):
        if dur_ms > 0:
            self.slider_seek.setRange(0, dur_ms)

    def _on_slider_moved(self, pos_ms: int):
        self.live_canvas.set_time(pos_ms / 1000.0)
        if self.current_video_path:
            self.media_player.setPosition(pos_ms)
        dur_s = max(1, self.slider_seek.maximum() // 1000)
        cur_s = pos_ms // 1000
        self.lbl_time.setText(f"{cur_s // 60:02d}:{cur_s % 60:02d} / {dur_s // 60:02d}:{dur_s % 60:02d}")

    def clear_preview(self):
        try:
            if self.media_player.playbackState() == QMediaPlayer.PlaybackState.PlayingState:
                self.media_player.stop()
        except Exception:
            pass
        self.current_video_path = ""
        self.btn_play.setText("▶ Play")
        self.slider_seek.setValue(0)
        self.lbl_time.setText("00:00 / 00:00")
        self.live_canvas.set_project_data([], [], "")
        self.preview_stack.setCurrentIndex(0)
        self.lbl_critic_status.setText("Standby")
        for thumb in self.critic_thumbs:
            thumb.setText("Empty")
            thumb.setPixmap(QPixmap())
        self.reset_preview_requested.emit()
