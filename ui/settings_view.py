from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QLineEdit, QComboBox, QFileDialog
)
from PySide6.QtCore import Signal
from ui.glass_widgets import GlassCard


class SettingsView(QWidget):
    """
    Studio Configuration & API Settings View:
    - Gemini API Key (powering gemini-3.8-flash, gemini-nano-banana-2.1, gemini-omni-1.1-flash)
    - Keyframe Model selector (gemini-nano-banana-2.1 vs gemini-3.1-flash-lite-image for ultra-fast drafts)
    - Default Render Mode & Omni Resolution (720p upscaled to 1080p Lanczos vs 1080p native)
    - Edge-TTS Voice & Pacing Speed
    - FFmpeg Binary Path
    """
    save_settings_requested = Signal(dict)

    def __init__(self, config: dict | None = None, parent=None):
        super().__init__(parent)
        self.config = dict(config or {})
        self._build_ui()
        self.load_config(self.config)

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 18, 20, 18)
        layout.setSpacing(14)

        card = GlassCard()
        c_layout = QVBoxLayout(card)
        c_layout.setContentsMargins(22, 20, 22, 20)
        c_layout.setSpacing(14)

        lbl_hdr = QLabel("⚙️ Studio & AI Connection Settings")
        lbl_hdr.setStyleSheet("color: #F5F5F7; font-weight: 700; font-size: 16px;")
        c_layout.addWidget(lbl_hdr)

        lbl_sub = QLabel(
            "Connect your Google AI Studio key for cloud generation, or leave as-is to use CrayonStudio's "
            "free built-in factual writer and 3D diagram renderer."
        )
        lbl_sub.setWordWrap(True)
        lbl_sub.setStyleSheet("color: #98989D; font-size: 12px;")
        c_layout.addWidget(lbl_sub)

        c_layout.addWidget(QLabel("Gemini API Key (Google AI Studio):"))
        self.input_api_key = QLineEdit()
        self.input_api_key.setEchoMode(QLineEdit.EchoMode.Password)
        self.input_api_key.setPlaceholderText("AIzaSy...")
        c_layout.addWidget(self.input_api_key)

        c_layout.addWidget(QLabel("Scene Artwork Model (9:16 Keyframes):"))
        self.combo_image_model = QComboBox()
        self.combo_image_model.addItem("Nano Banana 2.1 (Recommended High-Detail Artwork)", "gemini-nano-banana-2.1")
        self.combo_image_model.addItem("Gemini 3.1 Flash-Lite Image (Ultra-Fast Drafts)", "gemini-3.1-flash-lite-image")
        c_layout.addWidget(self.combo_image_model)

        c_layout.addWidget(QLabel("AI Video Resolution (Upscaled to 1080x1920 HD):"))
        self.combo_omni_res = QComboBox()
        self.combo_omni_res.addItem("720p -> 1080p Smart Upscale (Saves ~45% Credits)", "720p")
        self.combo_omni_res.addItem("1080p Native", "1080p")
        c_layout.addWidget(self.combo_omni_res)

        row_voice = QHBoxLayout()
        col_v = QVBoxLayout()
        col_v.addWidget(QLabel("Narrator Voice:"))
        self.combo_voice = QComboBox()
        self.combo_voice.addItems([
            "en-US-AndrewNeural",
            "en-US-BrianNeural",
            "en-US-AvaNeural",
            "en-US-ChristopherNeural",
            "en-US-EmmaNeural",
            "en-US-GuyNeural",
        ])
        col_v.addWidget(self.combo_voice)
        row_voice.addLayout(col_v, stretch=2)

        col_spd = QVBoxLayout()
        col_spd.addWidget(QLabel("Speaking Speed:"))
        self.input_voice_speed = QLineEdit("0.96")
        col_spd.addWidget(self.input_voice_speed)
        row_voice.addLayout(col_spd, stretch=1)
        c_layout.addLayout(row_voice)

        c_layout.addWidget(QLabel("FFmpeg Video Encoder Path:"))
        ff_row = QHBoxLayout()
        self.input_ffmpeg = QLineEdit()
        ff_row.addWidget(self.input_ffmpeg, stretch=1)
        btn_browse_ff = QPushButton("Browse...")
        btn_browse_ff.setProperty("class", "chip")
        btn_browse_ff.clicked.connect(self._browse_ffmpeg)
        ff_row.addWidget(btn_browse_ff)
        c_layout.addLayout(ff_row)

        btn_row = QHBoxLayout()
        btn_row.addStretch()
        self.lbl_saved = QLabel("")
        self.lbl_saved.setStyleSheet("color: #30D158; font-size: 12px; font-weight: 600;")
        btn_row.addWidget(self.lbl_saved)

        self.btn_save = QPushButton("💾 Save Settings")
        self.btn_save.setProperty("class", "primary")
        self.btn_save.clicked.connect(self._emit_save)
        btn_row.addWidget(self.btn_save)
        c_layout.addLayout(btn_row)

        layout.addWidget(card)
        layout.addStretch()

    def _browse_ffmpeg(self):
        path, _ = QFileDialog.getOpenFileName(self, "Select FFmpeg Executable", "", "Executables (*.exe *);;All Files (*)")
        if path:
            self.input_ffmpeg.setText(path)

    def load_config(self, cfg: dict):
        self.config = dict(cfg or {})
        self.input_api_key.setText(str(self.config.get("gemini_api_key", "")))

        img_m = self.config.get("image_model", "gemini-nano-banana-2.1")
        idx = self.combo_image_model.findData(img_m)
        if idx >= 0:
            self.combo_image_model.setCurrentIndex(idx)

        res = self.config.get("omni_resolution", "720p")
        r_idx = self.combo_omni_res.findData(res)
        if r_idx >= 0:
            self.combo_omni_res.setCurrentIndex(r_idx)

        voice = self.config.get("tts_voice", self.config.get("default_voice", "en-US-AndrewMultilingualNeural"))
        v_idx = self.combo_voice.findText(voice)
        if v_idx >= 0:
            self.combo_voice.setCurrentIndex(v_idx)

        self.input_voice_speed.setText(str(self.config.get("tts_speed", self.config.get("speech_speed", "0.96"))))
        self.input_ffmpeg.setText(str(self.config.get("ffmpeg_path", "ffmpeg")))

    def _emit_save(self):
        updated = dict(self.config)
        updated["gemini_api_key"] = self.input_api_key.text().strip()
        updated["image_model"] = self.combo_image_model.currentData()
        updated["omni_model"] = "gemini-omni-1.1-flash"
        updated["text_model"] = "gemini-3.8-flash"
        updated["omni_resolution"] = self.combo_omni_res.currentData()
        updated["tts_voice"] = self.combo_voice.currentText()
        try:
            updated["tts_speed"] = float(self.input_voice_speed.text().strip() or 1.05)
        except ValueError:
            updated["tts_speed"] = 1.05
        updated["ffmpeg_path"] = self.input_ffmpeg.text().strip() or "ffmpeg"
        self.lbl_saved.setText("✓ Settings saved")
        self.save_settings_requested.emit(updated)
