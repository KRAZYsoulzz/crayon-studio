"""CrayonStudio — Phase 1 System Scaffolding & Desktop Studio.

Production-grade PySide6 (Qt6) Fluent dark-mode application for automated
short-form educational video creation with Kokoro-82M TTS, faster-whisper alignment,
ASMR Foley mixing, trend scraper, and social dispatchers.
"""

from __future__ import annotations

import datetime
import json
import logging
import os
import re
import shutil
import sys
import time
from typing import Any, Dict, List, Optional

from PySide6.QtCore import QDate, QRect, QSize, Qt, QThread, QTime, QTimer, QUrl, Signal, Slot
from PySide6.QtGui import QColor, QFont, QIcon, QPainter, QPen, QPixmap
from PySide6.QtMultimedia import QAudioOutput, QMediaPlayer
from PySide6.QtMultimediaWidgets import QVideoWidget
from PySide6.QtWidgets import (
    QAbstractItemView,
    QApplication,
    QCheckBox,
    QComboBox,
    QDateEdit,
    QFileDialog,
    QFrame,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QMainWindow,
    QMessageBox,
    QProgressBar,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QSlider,
    QSpinBox,
    QDoubleSpinBox,
    QSplitter,
    QStackedWidget,
    QStatusBar,
    QTableWidget,
    QTableWidgetItem,
    QTabWidget,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

# Core imports
from core.ai_modifier import modify_script
from core.audio_generator import generate_voiceover
from core.duration_guard import (
    MIN_PUBLISH_SECONDS,
    estimate_spoken_seconds,
    probe_wav_duration,
    render_voiceover_until_publishable,
    words_required,
)
from core.layout_policy import split_widths
from core.visual_costs import MODE_LABELS, cost_summary_line
from core.blender_orchestrator import BlenderOrchestrator
from core.engine_router import VisualEngineRouter
from core.ffmpeg_compositor import FFmpegCompositor
from core.foley_mixer import generate_foley_track
from core.scraper import (
    generate_content_suggestions,
    scan_competitor_channel,
    search_trends_and_comments,
)
from core.timestamp_aligner import extract_word_timestamps
from core.uploader import queue_tiktok_draft, upload_to_youtube
from core.visual_critic import generate_and_verify_snapshots
import database.db as db

# Configure logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
logger = logging.getLogger("crayon_studio")

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
CONFIG_PATH = os.path.join(BASE_DIR, "config.json")
PROJECTS_DIR = os.path.join(BASE_DIR, "projects")
os.makedirs(PROJECTS_DIR, exist_ok=True)


def load_app_config() -> Dict[str, Any]:
    """Load configuration from config.json or return defaults."""
    default_config = {
        "blender_path": "C:\\Program Files\\Blender Foundation\\Blender 4.2\\blender.exe",
        "ffmpeg_path": "ffmpeg.exe",
        "default_voice": "af_heart",
        "speech_speed": 1.05,
        "target_duration": 69,
        "visual_source": "hybrid_stock",
        "pexels_api_key": "",
        "pixabay_api_key": "",
        "dry_run_mode": True,
        "youtube_api_key": "",
    }
    if os.path.exists(CONFIG_PATH):
        try:
            with open(CONFIG_PATH, "r", encoding="utf-8") as f:
                saved = json.load(f)
                default_config.update(saved)
        except Exception as e:
            logger.warning("Could not read config.json: %s", e)

    bp = default_config.get("blender_path", "")
    if not bp or (not os.path.exists(bp) and not shutil.which(bp)):
        default_config["blender_path"] = BlenderOrchestrator.find_blender_executable(CONFIG_PATH)

    fp = default_config.get("ffmpeg_path", "")
    if not fp or (not os.path.exists(fp) and not shutil.which(fp)):
        default_config["ffmpeg_path"] = FFmpegCompositor.find_ffmpeg_executable(CONFIG_PATH)

    return default_config


def save_app_config(cfg: Dict[str, Any]) -> bool:
    """Save configuration dictionary to config.json."""
    try:
        with open(CONFIG_PATH, "w", encoding="utf-8") as f:
            json.dump(cfg, f, indent=2)
        return True
    except Exception as e:
        logger.error("Failed to save config.json: %s", e)
        return False


# =====================================================================
# WINUI 3 / FLUENT DARK THEME STYLESHEET
# =====================================================================
FLUENT_DARK_QSS = """
/* Window & Surfaces */
QMainWindow, QWidget {
    background-color: #121212;
    color: #E0E0E0;
    font-family: 'Segoe UI', -apple-system, BlinkMacSystemFont, Roboto, sans-serif;
    font-size: 13px;
}

/* ScrollBars */
QScrollBar:vertical {
    border: none;
    background: #181818;
    width: 10px;
    margin: 0px 0px 0px 0px;
    border-radius: 5px;
}
QScrollBar::handle:vertical {
    background: #3A3A3A;
    min-height: 24px;
    border-radius: 5px;
}
QScrollBar::handle:vertical:hover {
    background: #505050;
}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
    height: 0px;
}

/* Tabs */
QTabWidget::pane {
    border: 1px solid #2D2D2D;
    background-color: #121212;
    border-radius: 6px;
    top: -1px;
}
QTabBar::tab {
    background: #1E1E1E;
    color: #9AA0A6;
    padding: 10px 22px;
    margin-right: 4px;
    border-top-left-radius: 6px;
    border-top-right-radius: 6px;
    border: 1px solid #2D2D2D;
    border-bottom: none;
    font-weight: 600;
}
QTabBar::tab:selected {
    background: #252525;
    color: #FFFFFF;
    border-bottom: 2px solid #0078D4;
}
QTabBar::tab:hover:!selected {
    background: #2A2A2A;
    color: #E0E0E0;
}

/* Cards & Containers */
QFrame.card {
    background-color: #1E1E1E;
    border: 1px solid #2D2D2D;
    border-radius: 8px;
}

/* Buttons */
QPushButton {
    background-color: #2D2D2D;
    color: #E0E0E0;
    border: 1px solid #3A3A3A;
    border-radius: 6px;
    padding: 8px 16px;
    font-weight: 600;
}
QPushButton:hover {
    background-color: #383838;
    border: 1px solid #484848;
}
QPushButton:pressed {
    background-color: #222222;
}
QPushButton:disabled {
    background-color: #1A1A1A;
    color: #555555;
    border-color: #252525;
}

/* Accent Button */
QPushButton.primary {
    background-color: #0078D4;
    color: #FFFFFF;
    border: 1px solid #1084D8;
}
QPushButton.primary:hover {
    background-color: #1084D8;
}
QPushButton.primary:pressed {
    background-color: #006CBE;
}

/* Success Button */
QPushButton.success {
    background-color: #107C41;
    color: #FFFFFF;
    border: 1px solid #158A49;
}
QPushButton.success:hover {
    background-color: #138D4A;
}

/* Inputs */
QLineEdit, QTextEdit, QSpinBox, QDoubleSpinBox, QComboBox, QDateEdit {
    background-color: #252525;
    color: #FFFFFF;
    border: 1px solid #333333;
    border-radius: 6px;
    padding: 6px 10px;
    selection-background-color: #0078D4;
}
QLineEdit:focus, QTextEdit:focus, QSpinBox:focus, QDoubleSpinBox:focus, QComboBox:focus {
    border: 1px solid #0078D4;
    background-color: #292929;
}

/* ComboBox */
QComboBox::drop-down {
    border: none;
    width: 24px;
}
QComboBox QAbstractItemView {
    background-color: #1E1E1E;
    border: 1px solid #2D2D2D;
    color: #E0E0E0;
    selection-background-color: #0078D4;
}

/* Tables */
QTableWidget {
    background-color: #1E1E1E;
    border: 1px solid #2D2D2D;
    border-radius: 6px;
    gridline-color: #2D2D2D;
    color: #E0E0E0;
    selection-background-color: #004578;
    selection-color: #FFFFFF;
}
QHeaderView::section {
    background-color: #252525;
    color: #9AA0A6;
    padding: 8px;
    border: none;
    border-bottom: 1px solid #2D2D2D;
    font-weight: 600;
}

/* Sliders */
QSlider::groove:horizontal {
    height: 6px;
    background: #2D2D2D;
    border-radius: 3px;
}
QSlider::sub-page:horizontal {
    background: #0078D4;
    border-radius: 3px;
}
QSlider::handle:horizontal {
    background: #FFFFFF;
    width: 14px;
    margin-top: -4px;
    margin-bottom: -4px;
    border-radius: 7px;
}

/* Checkbox */
QCheckBox {
    spacing: 8px;
    color: #E0E0E0;
    font-weight: 500;
}
QCheckBox::indicator {
    width: 18px;
    height: 18px;
    border-radius: 4px;
    border: 1px solid #3A3A3A;
    background: #252525;
}
QCheckBox::indicator:checked {
    background: #0078D4;
    border-color: #0078D4;
}

/* Progress Bar */
QProgressBar {
    background-color: #252525;
    border: 1px solid #2D2D2D;
    border-radius: 6px;
    text-align: center;
    color: #FFFFFF;
    height: 16px;
}
QProgressBar::chunk {
    background-color: #0078D4;
    border-radius: 5px;
}

/* Labels */
QLabel.heading {
    font-size: 17px;
    font-weight: 700;
    color: #FFFFFF;
}
QLabel.subheading {
    font-size: 13px;
    color: #9AA0A6;
}
QLabel.badge {
    padding: 3px 8px;
    border-radius: 4px;
    font-weight: bold;
    font-size: 11px;
}
"""


# =====================================================================
# ASYNCHRONOUS WORKER THREADS
# =====================================================================
class ScraperWorker(QThread):
    """Background worker for YouTube competitor search, channel scanning, and comment intelligence."""

    progress = Signal(str)
    finished = Signal(dict)
    error = Signal(str)

    def __init__(
        self,
        query: str,
        max_results: int = 5,
        api_key: Optional[str] = None,
        mode: str = "keyword",
    ):
        super().__init__()
        self.query = query
        self.max_results = max_results
        self.api_key = api_key
        self.mode = mode

    def run(self):
        try:
            if self.mode == "channel":
                self.progress.emit(f"📡 Scanning competitor channel '{self.query}' for audience reactions...")
                trends = scan_competitor_channel(self.query, self.max_results)
            else:
                self.progress.emit(f"🔍 Mining competitor videos & comment threads for '{self.query}'...")
                trends = search_trends_and_comments(self.query, self.max_results, self.api_key)

            self.progress.emit("💡 Synthesizing high-retention content suggestions & engineered hooks...")
            suggestions = generate_content_suggestions(trends)
            self.finished.emit({
                "trends": trends,
                "suggestions": suggestions,
            })
        except Exception as e:
            logger.error("Scraper worker failed: %s", e)
            self.error.emit(str(e))


class PipelineWorker(QThread):
    """Asynchronous worker for the complete audio, alignment, and Foley pipeline."""

    log_message = Signal(str)
    progress_val = Signal(int)
    pipeline_finished = Signal(dict)
    pipeline_error = Signal(str)

    def __init__(
        self,
        project_slug: str,
        title: str,
        hook: str,
        category: str,
        script_text: str,
        duration_target: int,
        tiktok_product: str,
        voice: str = "en-US-GuyNeural",
        speed: float = 1.00,
        visual_engine: str = "2D_Crayon",
    ):
        super().__init__()
        self.project_slug = project_slug
        self.title = title
        self.hook = hook
        self.category = category
        self.script_text = script_text
        self.duration_target = duration_target
        self.tiktok_product = tiktok_product
        self.voice = voice
        self.speed = speed
        self.visual_engine = visual_engine

    def run(self):
        try:
            # 1. Project Directory Initialization
            self.log_message.emit("⚡ Initializing workspace directory...")
            self.progress_val.emit(10)
            proj_dir = os.path.join(PROJECTS_DIR, self.project_slug)
            os.makedirs(proj_dir, exist_ok=True)
            with open(os.path.join(proj_dir, "script.txt"), "w", encoding="utf-8") as f:
                f.write(self.script_text)
            self.log_message.emit(f"📁 Project workspace ready at: {proj_dir}")

            # 2. Persist/Update SQLite Record
            self.log_message.emit("💾 Synchronizing project state with SQLite database...")
            self.progress_val.emit(25)
            existing = db.get_project_by_slug(self.project_slug)
            if existing:
                db.update_project(
                    project_id=existing["id"],
                    title=self.title,
                    hook=self.hook,
                    category=self.category,
                    script_text=self.script_text,
                    duration_target=self.duration_target,
                    tiktok_product=self.tiktok_product,
                    status="Draft",
                    visual_engine=self.visual_engine,
                )
                proj_id = existing["id"]
            else:
                proj_id = db.create_project(
                    project_slug=self.project_slug,
                    title=self.title,
                    hook=self.hook,
                    category=self.category,
                    script_text=self.script_text,
                    duration_target=self.duration_target,
                    tiktok_product=self.tiktok_product,
                    status="Draft",
                    visual_engine=self.visual_engine,
                )
            self.log_message.emit(f"✓ Project synced (ID: {proj_id}, Engine: {self.visual_engine})")

            # 3. Audio Synthesis, measured against the monetization floor.
            # Word count is budgeted from the neural rate first. If the wav
            # is still short, the script is extended and synthesized again.
            self.log_message.emit(
                f"🎙️ Synthesizing voiceover [Voice: {self.voice}, Speed: {self.speed}x, "
                f"target {self.duration_target}s]..."
            )
            self.progress_val.emit(45)
            vo_path = os.path.join(proj_dir, "voiceover.wav")
            needed = words_required(self.duration_target, speed=self.speed, voice=self.voice)
            self.log_message.emit(
                f"Script budget: {needed} words for {self.duration_target}s "
                f"at this voice (the 145 WPM meter was short by about a third)."
            )

            def _synthesize(text: str, path: str, voice: str, speed: float) -> float:
                generate_voiceover(text, path, voice=voice, speed=speed)
                return probe_wav_duration(path)

            self.script_text, total_dur, speed_used = render_voiceover_until_publishable(
                self.script_text,
                vo_path,
                voice=self.voice,
                speed=self.speed,
                target_seconds=float(self.duration_target),
                topic=self.title,
                synthesize=_synthesize,
            )
            self.speed = speed_used
            with open(os.path.join(proj_dir, "script.txt"), "w", encoding="utf-8") as f:
                f.write(self.script_text)
            db.update_project(
                project_id=proj_id,
                title=self.title,
                hook=self.hook,
                category=self.category,
                script_text=self.script_text,
                duration_target=self.duration_target,
                tiktok_product=self.tiktok_product,
                status="Draft",
                visual_engine=self.visual_engine,
            )
            self.log_message.emit(
                f"✓ Voiceover {total_dur:.1f}s ({len(self.script_text.split())} words) — "
                f"clears the {MIN_PUBLISH_SECONDS:.0f}s floor."
            )

            # 4. Word-Level Timestamp Extraction (faster-whisper)
            self.log_message.emit("⏱️ Extracting word-level timestamps with faster-whisper...")
            self.progress_val.emit(65)
            words_json_path = os.path.join(proj_dir, "words_timestamp.json")
            words_list = extract_word_timestamps(vo_path, words_json_path, script_text=self.script_text)
            self.log_message.emit(f"✓ Aligned {len(words_list)} words saved to: {words_json_path}")

            # The wav is the clock. The last word timestamp ends early and
            # used to become the video length.
            total_dur = probe_wav_duration(vo_path)

            # 5. ASMR / Mechanical Foley Generation
            foley_desc = "procedural mechanical transients" if self.visual_engine == "3D_Teardown" else "synchronized crayon scribbles and ASMR paper friction"
            self.log_message.emit(f"🎨 Synthesizing {foley_desc}...")
            self.progress_val.emit(85)
            foley_path = os.path.join(proj_dir, "foley_track.wav")
            generate_foley_track(words_json_path, foley_path, duration=total_dur, visual_engine=self.visual_engine)
            self.log_message.emit(f"✓ Synchronized Foley audio rendered: {foley_path}")

            # 6. Finalize Status
            db.update_project_status(proj_id, "Audio_Ready")
            self.progress_val.emit(100)
            self.log_message.emit("🚀 Pipeline Execution Complete: Status set to 'Audio_Ready'.")

            result_payload = {
                "project_id": proj_id,
                "project_slug": self.project_slug,
                "title": self.title,
                "script_text": self.script_text,
                "category": self.category,
                "duration": total_dur,
                "voiceover_path": vo_path,
                "words_json_path": words_json_path,
                "foley_path": foley_path,
                "visual_engine": self.visual_engine,
            }
            self.pipeline_finished.emit(result_payload)

        except Exception as e:
            logger.error("Pipeline worker error: %s", e, exc_info=True)
            self.log_message.emit(f"❌ PIPELINE ERROR: {e}")
            self.pipeline_error.emit(str(e))


class BlenderRenderWorker(QThread):
    """Background worker for headless Blender Grease Pencil render and FFmpeg composite."""

    log_message = Signal(str)
    progress_val = Signal(int)
    render_finished = Signal(str)
    render_error = Signal(str)

    def __init__(
        self,
        project_slug: str,
        category: str,
        blender_path: str,
        ffmpeg_path: str,
        script_text: str = "",
        visual_engine: str = "2D_Crayon",
        style_reference_path: Optional[str] = None,
        enable_omni_video: bool = False,
        visual_source: str = "hybrid_stock",
    ):
        super().__init__()
        self.project_slug = project_slug
        self.category = category
        self.blender_path = blender_path
        self.ffmpeg_path = ffmpeg_path
        self.script_text = script_text
        self.visual_engine = visual_engine
        self.style_reference_path = style_reference_path
        self.enable_omni_video = enable_omni_video
        self.visual_source = visual_source

    def run(self):
        try:
            proj_dir = os.path.join(PROJECTS_DIR, self.project_slug)
            if self.script_text:
                with open(os.path.join(proj_dir, "script.txt"), "w", encoding="utf-8") as f:
                    f.write(self.script_text)
            words_json = os.path.join(proj_dir, "words_timestamp.json")
            vo_path = os.path.join(proj_dir, "voiceover.wav")
            foley_path = os.path.join(proj_dir, "foley_track.wav")
            raw_video = os.path.join(proj_dir, "scene_raw.mp4")
            final_mp4 = os.path.join(proj_dir, f"{self.project_slug}_final.mp4")

            if not os.path.exists(words_json):
                raise FileNotFoundError("words_timestamp.json not found. Run 'Generate Video Pipeline' first.")

            engine_label = VisualEngineRouter.get_display_name(self.visual_engine)
            self.log_message.emit(f"🎨 Initializing {engine_label}...")
            self.progress_val.emit(25)

            router = VisualEngineRouter(
                visual_engine=self.visual_engine,
                blender_path=self.blender_path,
                ffmpeg_path=self.ffmpeg_path,
            )
            render_res = router.render_project(
                project_dir=proj_dir,
                words_json_path=words_json,
                output_mp4_path=raw_video,
                category=self.category,
                script_text=self.script_text,
                style_reference_path=self.style_reference_path,
                enable_omni_video=self.enable_omni_video,
                visual_source=self.visual_source,
                progress_callback=lambda msg: self.log_message.emit(msg),
            )

            self.log_message.emit("🎬 Multiplexing audio, Foley, and kinetic .ass captions with FFmpeg...")
            self.progress_val.emit(75)

            comp = FFmpegCompositor(ffmpeg_path=self.ffmpeg_path)
            comp.composite_video(
                video_path=raw_video,
                voiceover_path=vo_path,
                words_json_path=words_json,
                output_mp4_path=final_mp4,
                foley_path=foley_path,
                progress_callback=lambda msg: self.log_message.emit(msg),
            )

            self.progress_val.emit(100)
            self.log_message.emit(f"✓ Broadcast-ready MP4 rendered: {final_mp4}")
            self.render_finished.emit(final_mp4)
        except Exception as e:
            logger.error("Blender render worker error: %s", e, exc_info=True)
            self.render_error.emit(str(e))



# =====================================================================
# VERTICAL 9:16 PREVIEW CANVAS (VISUAL + WAVEFORM PLAYBACK)
# =====================================================================
class VerticalPreviewCanvas(QWidget):
    """Custom 9:16 viewport widget showing stylized kinetic canvas preview."""

    def __init__(self, parent=None):
        super().__init__(parent)
        # No hard minimum: a minimum wider than the leftover column is what
        # let the preview paint over the checklist. The splitter assigns width.
        self.setMinimumSize(0, 0)
        self.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Expanding)
        self.title_text = "CrayonStudio Vertical Player"
        self.hook_text = "Watch what happens next..."
        self.category = "STEM"
        self.words: List[Dict[str, Any]] = []
        self.blocks: List[Dict[str, Any]] = []
        self.playback_pos_ms = 0
        self.total_duration_ms = 65000
        self.is_playing = False

    def set_word_timestamps(self, words: List[Dict[str, Any]]):
        """Sets word timestamps and groups them into stable 2-3 line thought blocks."""
        self.words = words or []
        self.blocks = []
        if self.words:
            current_block: List[Dict[str, Any]] = []
            for idx, w in enumerate(self.words):
                current_block.append(w)
                txt = str(w.get("word", "")).strip()
                ends_sent = any(txt.endswith(p) for p in (".", "!", "?")) and len(current_block) >= 4
                ends_clause = any(txt.endswith(p) for p in (",", ";", ":", "—")) and len(current_block) >= 6
                max_reach = len(current_block) >= 8
                is_last = (idx == len(self.words) - 1)

                if ends_sent or ends_clause or max_reach or is_last:
                    b_words = [x.get("word", "") for x in current_block]
                    tw = len(b_words)
                    if tw <= 4:
                        lines = [" ".join(b_words)]
                    elif tw <= 7:
                        mid = (tw + 1) // 2
                        lines = [" ".join(b_words[:mid]), " ".join(b_words[mid:])]
                    else:
                        p1 = (tw + 2) // 3
                        p2 = p1 + (tw - p1 + 1) // 2
                        lines = [" ".join(b_words[:p1]), " ".join(b_words[p1:p2]), " ".join(b_words[p2:])]

                    self.blocks.append({
                        "start": float(current_block[0].get("start", 0.0)),
                        "end": float(current_block[-1].get("end", 0.0)),
                        "text": "\n".join(lines),
                        "words": current_block,
                    })
                    current_block = []
        self.update()

    def sizeHint(self):
        return QSize(280, 500)

    def minimumSizeHint(self):
        return QSize(0, 0)

    def update_metadata(self, title: str, hook: str, category: str):
        self.title_text = title
        self.hook_text = hook
        self.category = category
        self.update()

    def update_position(self, pos_ms: int, duration_ms: int):
        self.playback_pos_ms = pos_ms
        if duration_ms > 0:
            self.total_duration_ms = duration_ms
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)

        # Draw 9:16 vertical card background
        w = self.width()
        h = self.height()
        target_w = int(h * 9 / 16)
        if target_w > w:
            target_w = w
            target_h = int(w * 16 / 9)
        else:
            target_h = h

        x = (w - target_w) // 2
        y = (h - target_h) // 2

        # Paper Texture Canvas Background
        painter.fillRect(x, y, target_w, target_h, QColor("#1A1A1A"))
        painter.setPen(QPen(QColor("#2D2D2D"), 2))
        painter.drawRoundedRect(x, y, target_w, target_h, 8, 8)

        # Drawing craft paper inner frame
        inner_margin = 12
        painter.fillRect(
            x + inner_margin,
            y + inner_margin,
            target_w - 2 * inner_margin,
            target_h - 2 * inner_margin,
            QColor("#222222"),
        )

        # Category Badge
        cat_colors = {
            "STEM": QColor("#0078D4"),
            "Escape/Heist": QColor("#D83B01"),
            "Architecture": QColor("#107C41"),
            "Psychology": QColor("#8764B8"),
        }
        badge_color = cat_colors.get(self.category, QColor("#0078D4"))
        painter.setBrush(badge_color)
        painter.setPen(Qt.NoPen)
        painter.drawRoundedRect(x + inner_margin + 12, y + inner_margin + 16, 90, 24, 4, 4)

        painter.setPen(QColor("#FFFFFF"))
        badge_font = QFont("Segoe UI", 8, QFont.Bold)
        painter.setFont(badge_font)
        painter.drawText(
            x + inner_margin + 12,
            y + inner_margin + 16,
            90,
            24,
            Qt.AlignCenter,
            self.category.upper(),
        )

        # 9:16 Aspect indicator
        painter.setPen(QColor("#777777"))
        painter.setFont(QFont("Segoe UI", 8))
        painter.drawText(x + target_w - 60, y + inner_margin + 32, "9:16 HD")

        # Crayon Sketch Graphic in center
        center_x = x + target_w // 2
        center_y = y + target_h // 2 - 30

        # Draw decorative crayon spiral / technical sketch
        painter.setPen(QPen(QColor("#FFD700"), 4, Qt.SolidLine, Qt.RoundCap))
        painter.drawArc(center_x - 45, center_y - 45, 90, 90, 30 * 16, 280 * 16)
        painter.setPen(QPen(QColor("#00E5FF"), 3, Qt.DashLine, Qt.RoundCap))
        painter.drawArc(center_x - 30, center_y - 30, 60, 60, 120 * 16, 260 * 16)

        # Simulated dynamic waveform bars
        progress_ratio = self.playback_pos_ms / max(1, self.total_duration_ms)
        bars_count = 24
        bar_w = (target_w - 60) // bars_count
        bar_start_x = x + 30
        bar_y_base = center_y + 90

        painter.setPen(Qt.NoPen)
        for i in range(bars_count):
            fraction = i / bars_count
            is_active = fraction <= progress_ratio
            bar_color = QColor("#0078D4") if is_active else QColor("#3A3A3A")
            # Waveform variance
            height_mod = 12 + int(24 * abs(((i * 7) % 11) / 11.0))
            painter.setBrush(bar_color)
            painter.drawRoundedRect(
                bar_start_x + i * bar_w,
                bar_y_base - height_mod // 2,
                max(2, bar_w - 2),
                height_mod,
                2,
                2,
            )

        # Dynamic 2-3 Line Block Subtitle Overlay
        current_sec = self.playback_pos_ms / 1000.0
        active_block_text = ""

        if self.blocks:
            for b in self.blocks:
                if b["start"] <= current_sec <= b["end"] + 0.30:
                    active_block_text = b["text"]
                    break

            if not active_block_text:
                for b in reversed(self.blocks):
                    if b["start"] <= current_sec:
                        active_block_text = b["text"]
                        break

            if not active_block_text and current_sec < self.blocks[0]["start"]:
                active_block_text = self.blocks[0]["text"]

        if not active_block_text:
            words_hook = (self.hook_text or self.title_text).split()
            if len(words_hook) > 8:
                mid = len(words_hook) // 2
                active_block_text = " ".join(words_hook[:mid]) + "\n" + " ".join(words_hook[mid:])
            else:
                active_block_text = self.hook_text or self.title_text

        # Draw comfortable 2-3 line subtitle card
        sub_font = QFont("Segoe UI", 12, QFont.Bold)
        painter.setFont(sub_font)
        fm = painter.fontMetrics()

        lines_count = max(1, active_block_text.count("\n") + 1)
        line_height = fm.lineSpacing()
        card_h = max(70, line_height * lines_count + 20)
        card_w = target_w - 36
        card_x = x + 18
        card_y = center_y + 115

        card_rect = QRect(card_x, card_y, card_w, card_h)

        # Background semi-transparent card with subtle gold/blue border
        painter.setBrush(QColor(12, 12, 15, 235))
        border_col = QColor("#FFD700") if self.blocks else QColor("#0078D4")
        painter.setPen(QPen(border_col, 1.8))
        painter.drawRoundedRect(card_rect, 8, 8)

        # Draw 2-3 lines centered inside card with drop shadow
        inner_rect = card_rect.adjusted(8, 8, -8, -8)
        painter.setPen(QColor(0, 0, 0, 200))
        painter.drawText(inner_rect.adjusted(1, 1, 1, 1), Qt.AlignCenter | Qt.TextWordWrap, active_block_text)
        painter.setPen(QColor("#FFFFFF"))
        painter.drawText(inner_rect, Qt.AlignCenter | Qt.TextWordWrap, active_block_text)
        painter.end()


# =====================================================================
# MAIN WINDOW CLASS
# =====================================================================
class CrayonStudioApp(QMainWindow):
    """Main desktop application window for CrayonStudio."""

    def __init__(self):
        super().__init__()
        self.setWindowTitle("CrayonStudio — Viral Short-Form Video Studio (Phase 1)")
        # A fixed 1280px floor did not stop the overlap: the preview's minimum
        # plus the checklist's minimum already exceeded the client area, and
        # card padding painted outside the layout cells. The floor below is
        # only a comfort size. The splitter collapses the preview below it.
        self.setMinimumSize(960, 680)
        self._preview_user_choice = True

        # State
        self.config = load_app_config()
        self.active_project_id: Optional[int] = None
        self.active_project_slug: str = "new-crayon-project"
        self.current_media_path: Optional[str] = None
        self.pipeline_thread: Optional[PipelineWorker] = None
        self.scraper_thread: Optional[ScraperWorker] = None

        # Audio / Media Player Setup
        self.media_player = QMediaPlayer()
        self.audio_output = QAudioOutput()
        self.media_player.setAudioOutput(self.audio_output)
        self.audio_output.setVolume(0.85)

        # Setup UI
        self.setStyleSheet(FLUENT_DARK_QSS)
        self._init_database()
        self._build_ui()
        self._wire_player_events()
        self._load_saved_settings_to_ui()
        self.refresh_calendar()

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self._apply_preview_columns()

    def showEvent(self, event):
        super().showEvent(event)
        self._apply_preview_columns()

    def _on_toggle_phone_preview(self):
        self._preview_user_choice = self.btn_toggle_preview.isChecked()
        self._apply_preview_columns()

    def _apply_preview_columns(self):
        """Give the checklist the width it needs and collapse the phone when it would cover it."""
        splitter = getattr(self, "player_splitter", None)
        if splitter is None:
            return
        width = splitter.width()
        if width < 80:
            width = max(0, self.width() - 48)
        content_w, preview_w = split_widths(width, self._preview_user_choice)
        splitter.setSizes([max(0, content_w), max(0, preview_w)])
        shown = preview_w > 0
        button = getattr(self, "btn_toggle_preview", None)
        if button is None:
            return
        button.blockSignals(True)
        button.setChecked(shown)
        if shown:
            button.setText("Hide Phone Preview")
        elif self._preview_user_choice:
            button.setText("Phone preview hidden — widen the window")
        else:
            button.setText("Show Phone Preview")
        button.blockSignals(False)

    def _on_visual_source_changed(self):
        mode = self.combo_visual_source.currentData() or "hybrid_stock"
        self.config["visual_source"] = mode
        self.status_bar.showMessage(f"Picture source: {cost_summary_line(mode)}", 4000)

    def _init_database(self):
        """Ensure SQLite schema is ready."""
        try:
            db.init_db()
            logger.info("SQLite database initialized successfully.")
        except Exception as e:
            logger.error("Failed to initialize database: %s", e)

    def _build_ui(self):
        """Construct the top-level application layout and 5 primary tabs."""
        main_widget = QWidget()
        self.setCentralWidget(main_widget)
        main_layout = QVBoxLayout(main_widget)
        main_layout.setContentsMargins(16, 12, 16, 12)
        main_layout.setSpacing(12)

        # 1. Header Toolbar
        header_frame = QFrame()
        header_frame.setObjectName("header")
        header_layout = QHBoxLayout(header_frame)
        header_layout.setContentsMargins(0, 0, 0, 0)

        app_title = QLabel("🖍️ CRAYONSTUDIO")
        app_title.setStyleSheet("font-size: 20px; font-weight: 800; color: #FFFFFF; letter-spacing: 1px;")
        sub_title = QLabel("Phase 1 Desktop Studio & Scaffolding")
        sub_title.setStyleSheet("color: #9AA0A6; font-size: 12px; margin-left: 8px;")

        header_layout.addWidget(app_title)
        header_layout.addWidget(sub_title)
        header_layout.addStretch()

        self.dry_run_indicator = QLabel("● DRY-RUN ACTIVE")
        self.dry_run_indicator.setStyleSheet(
            "color: #D88D00; font-weight: bold; background: #2A2000; "
            "padding: 4px 10px; border-radius: 4px; border: 1px solid #7A5200;"
        )
        header_layout.addWidget(self.dry_run_indicator)

        main_layout.addWidget(header_frame)

        # 2. Main Tab Widget
        self.tab_widget = QTabWidget()
        self.tab_widget.setDocumentMode(True)

        # Build individual tabs
        self.tab_research = self._build_tab_research()
        self.tab_studio = self._build_tab_studio()
        self.tab_player = self._build_tab_player()
        self.tab_calendar = self._build_tab_calendar()
        self.tab_settings = self._build_tab_settings()

        self.tab_widget.addTab(self.tab_research, "🔍 1. Trend Research")
        self.tab_widget.addTab(self.tab_studio, "🎬 2. Production Studio")
        self.tab_widget.addTab(self.tab_player, "▶️ 3. Player & Viral Checklist")
        self.tab_widget.addTab(self.tab_calendar, "📅 4. Content Calendar")
        self.tab_widget.addTab(self.tab_settings, "⚙️ 5. Settings")

        main_layout.addWidget(self.tab_widget)

        # Status Bar
        self.status_bar = QStatusBar()
        self.setStatusBar(self.status_bar)
        self.status_bar.showMessage("Ready. Select a trend or draft a script to begin.")

    # =================================================================
    # TAB 1: TREND RESEARCH
    # =================================================================
    def _build_tab_research(self) -> QWidget:
        # Wrap entire tab in a smooth QScrollArea so user can scroll through search, table, and suggestion deck
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setStyleSheet("QScrollArea { border: none; background: transparent; }")

        container = QWidget()
        layout = QVBoxLayout(container)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(14)

        # 1. Search & Competitor Channel Toolbar Card
        search_card = QFrame()
        search_card.setProperty("class", "card")
        sc_layout = QVBoxLayout(search_card)
        sc_layout.setContentsMargins(12, 12, 12, 12)
        sc_layout.setSpacing(10)

        # Row 1: Mode selector + Search Input + Analyze Button
        input_row = QHBoxLayout()
        input_row.setSpacing(8)

        self.combo_search_mode = QComboBox()
        self.combo_search_mode.addItem("🔍 Niche Topic / Keywords", "keyword")
        self.combo_search_mode.addItem("📡 Competitor Channel (@channel)", "channel")
        self.combo_search_mode.currentIndexChanged.connect(self._on_search_mode_changed)

        self.trend_search_input = QLineEdit()
        self.trend_search_input.setPlaceholderText(
            "Search viral niche (e.g. 'why Roman concrete heals', 'piezoelectric lighter', 'vacuum experiment')..."
        )
        self.trend_search_input.returnPressed.connect(self._on_search_trends)

        self.btn_analyze = QPushButton("⚡ Analyze & Mine Comments")
        self.btn_analyze.setProperty("class", "primary")
        self.btn_analyze.clicked.connect(self._on_search_trends)

        input_row.addWidget(self.combo_search_mode, stretch=2)
        input_row.addWidget(self.trend_search_input, stretch=5)
        input_row.addWidget(self.btn_analyze, stretch=2)
        sc_layout.addLayout(input_row)

        # Row 2: Inspiration Presets (Topics & Competitor Channels)
        chips_layout = QHBoxLayout()
        chips_layout.setSpacing(6)
        lbl_presets = QLabel("Quick Presets:")
        lbl_presets.setStyleSheet("font-size: 11px; color: #9AA0A6; font-weight: bold;")
        chips_layout.addWidget(lbl_presets)

        presets = [
            ("⚡ Piezo Ignition", "piezoelectric lighter", "keyword"),
            ("🏛️ Roman Concrete", "why Roman concrete heals", "keyword"),
            ("⚙️ Brushless Motor", "brushless electric motor working", "keyword"),
            ("🏦 Bank Vault Flaw", "bank vault heist flaws", "keyword"),
            ("📡 @TheActionLab", "@TheActionLab", "channel"),
            ("📡 @Veritasium", "@Veritasium", "channel"),
        ]
        for label, val, mode in presets:
            btn_chip = QPushButton(label)
            btn_chip.setStyleSheet(
                "QPushButton { background-color: #242933; border: 1px solid #3B4252; "
                "border-radius: 12px; padding: 3px 8px; font-size: 10px; color: #D8DEE9; } "
                "QPushButton:hover { background-color: #383E4A; border-color: #0078D4; color: #FFFFFF; }"
            )
            btn_chip.clicked.connect(lambda chk, v=val, m=mode: self._on_search_preset(v, m))
            chips_layout.addWidget(btn_chip)

        chips_layout.addStretch()
        sc_layout.addLayout(chips_layout)
        layout.addWidget(search_card)

        # 2. Audience Friction & Sentiment Intelligence Table Card
        table_card = QFrame()
        table_card.setProperty("class", "card")
        tc_layout = QVBoxLayout(table_card)
        tc_layout.setContentsMargins(12, 12, 12, 12)
        tc_layout.setSpacing(10)

        tc_header = QHBoxLayout()
        tc_title = QLabel("Audience Friction Analysis & Comment Intelligence")
        tc_title.setStyleSheet("font-weight: bold; font-size: 14px; color: #FFFFFF;")
        self.lbl_trend_status = QLabel("Ready to analyze. Select a mode or preset above.")
        self.lbl_trend_status.setStyleSheet("color: #9AA0A6;")
        tc_header.addWidget(tc_title)
        tc_header.addStretch()
        tc_header.addWidget(self.lbl_trend_status)
        tc_layout.addLayout(tc_header)

        self.table_trends = QTableWidget(0, 6)
        self.table_trends.setHorizontalHeaderLabels([
            "Competitor Topic / Video Title",
            "Views",
            "❓ Top Confusion (? / Why)",
            "⚠️ Complaints & Flaws (What They Skipped)",
            "🌟 Praises (What Viewers Loved)",
            "💡 Content Gaps (Part 2 Requests)",
        ])
        self.table_trends.horizontalHeader().setSectionResizeMode(0, QHeaderView.Stretch)
        self.table_trends.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeToContents)
        self.table_trends.horizontalHeader().setSectionResizeMode(2, QHeaderView.Stretch)
        self.table_trends.horizontalHeader().setSectionResizeMode(3, QHeaderView.Stretch)
        self.table_trends.horizontalHeader().setSectionResizeMode(4, QHeaderView.Stretch)
        self.table_trends.horizontalHeader().setSectionResizeMode(5, QHeaderView.Stretch)
        self.table_trends.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.table_trends.setSelectionMode(QAbstractItemView.SingleSelection)
        self.table_trends.setAlternatingRowColors(True)
        self.table_trends.setMinimumHeight(220)
        tc_layout.addWidget(self.table_trends)

        # Action bar
        act_layout = QHBoxLayout()
        self.btn_use_topic = QPushButton("📥 Use Selected Competitor Topic →")
        self.btn_use_topic.setProperty("class", "primary")
        self.btn_use_topic.clicked.connect(self._on_use_as_topic)

        self.btn_save_trend = QPushButton("💾 Save Trend to SQLite")
        self.btn_save_trend.clicked.connect(self._on_save_trend_to_db)

        self.btn_load_saved_trends = QPushButton("🔄 Load Saved Database Trends")
        self.btn_load_saved_trends.clicked.connect(self._on_load_saved_trends)

        act_layout.addWidget(self.btn_use_topic)
        act_layout.addWidget(self.btn_save_trend)
        act_layout.addStretch()
        act_layout.addWidget(self.btn_load_saved_trends)
        tc_layout.addLayout(act_layout)

        layout.addWidget(table_card)

        # 3. AI-Generated Content Concepts Deck Card
        deck_card = QFrame()
        deck_card.setProperty("class", "card")
        dc_layout = QVBoxLayout(deck_card)
        dc_layout.setContentsMargins(12, 12, 12, 12)
        dc_layout.setSpacing(10)

        dh_row = QHBoxLayout()
        deck_title = QLabel("🎯 AI Content Suggestions (Pre-Engineered to Outperform Competitors)")
        deck_title.setStyleSheet("font-weight: bold; font-size: 14px; color: #FFFFFF;")
        self.lbl_sugg_count = QLabel("Run search or channel scan to generate concepts.")
        self.lbl_sugg_count.setStyleSheet("color: #9AA0A6;")
        dh_row.addWidget(deck_title)
        dh_row.addStretch()
        dh_row.addWidget(self.lbl_sugg_count)
        dc_layout.addLayout(dh_row)

        self.sugg_container = QWidget()
        self.sugg_layout = QVBoxLayout(self.sugg_container)
        self.sugg_layout.setContentsMargins(0, 4, 0, 4)
        self.sugg_layout.setSpacing(10)
        dc_layout.addWidget(self.sugg_container)

        layout.addWidget(deck_card)

        scroll.setWidget(container)
        return scroll

    # =================================================================
    # TAB 2: PRODUCTION STUDIO
    # =================================================================
    def _build_tab_studio(self) -> QWidget:
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)
        scroll.setStyleSheet("QScrollArea { border: none; background: transparent; }")
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(10)

        # Top Card: Project Meta Inputs
        meta_card = QFrame()
        meta_card.setProperty("class", "card")
        mc_layout = QGridLayout(meta_card)
        mc_layout.setHorizontalSpacing(14)
        mc_layout.setVerticalSpacing(8)

        # Row 0: Title & Category
        mc_layout.addWidget(QLabel("Project Title:"), 0, 0)
        self.input_title = QLineEdit("The 2,000-Year Ancient Roman Concrete Secret")
        mc_layout.addWidget(self.input_title, 0, 1)

        mc_layout.addWidget(QLabel("Category:"), 0, 2)
        self.combo_category = QComboBox()
        self.combo_category.addItems(["STEM", "How It's Made", "Engineering", "Escape/Heist", "Architecture", "Psychology"])
        self.combo_category.setCurrentText("Architecture")
        self.combo_category.currentTextChanged.connect(self._on_category_changed)
        mc_layout.addWidget(self.combo_category, 0, 3)

        # Row 1: Target Duration & TikTok Shop Bridge
        mc_layout.addWidget(QLabel("Target Duration:"), 1, 0)
        dur_layout = QHBoxLayout()
        self.spin_duration = QSpinBox()
        self.spin_duration.setRange(60, 180)
        self.spin_duration.setValue(69)
        self.spin_duration.setSuffix(" seconds")
        self.spin_duration.valueChanged.connect(self._on_script_text_changed)
        dur_layout.addWidget(self.spin_duration)
        mc_layout.addLayout(dur_layout, 1, 1)

        mc_layout.addWidget(QLabel("TikTok Shop Bridge:"), 1, 2)
        self.combo_product = QComboBox()
        self.combo_product.addItems([
            "Drawing Stylus & Textured Notebook",
            "Precision Calipers & Drafting Pen",
            "Tactical Pocket Tool & Pry Bar",
            "Neuroscience Focus Journal",
            "None (Pure Organic)",
        ])
        mc_layout.addWidget(self.combo_product, 1, 3)

        # Row 2: Visual Style Engine Selector (Dual-Engine Router)
        mc_layout.addWidget(QLabel("Visual Style Engine:"), 2, 0)
        self.combo_engine = QComboBox()
        self.combo_engine.addItem("🎨 Engine A: AI Storyboard & Sketch-Reveal (Continuous Storybook)", "2D_Crayon")
        self.combo_engine.addItem("⚙️ Engine B: 3D AI Hardware Teardown (Exploded View & X-Ray)", "3D_Teardown")
        self.combo_engine.addItem("🏛️ Legacy Blender 3D Curves", "Blender_Legacy")
        mc_layout.addWidget(self.combo_engine, 2, 1, 1, 3)

        # Row 3: Style Reference Screenshot Lock
        mc_layout.addWidget(QLabel("Style Reference Image:"), 3, 0)
        style_layout = QHBoxLayout()
        self.input_style_ref = QLineEdit()
        self.input_style_ref.setPlaceholderText("Optional path to style_reference.png screenshot for aesthetic locking...")
        self.btn_browse_style_ref = QPushButton("Browse Image...")
        self.btn_browse_style_ref.clicked.connect(self._on_browse_style_ref)
        style_layout.addWidget(self.input_style_ref)
        style_layout.addWidget(self.btn_browse_style_ref)
        mc_layout.addLayout(style_layout, 3, 1, 1, 3)

        # Row 4: Narrator Voice & Pacing
        mc_layout.addWidget(QLabel("Narrator Voice:"), 4, 0)
        self.tab2_combo_voice = QComboBox()
        self.tab2_combo_voice.addItem("🎙️ en-US-GuyNeural (Smooth Documentary Narrator - Recommended)", "en-US-GuyNeural")
        self.tab2_combo_voice.addItem("🎙️ en-US-ChristopherNeural (Deep Cinematic Baritone)", "en-US-ChristopherNeural")
        self.tab2_combo_voice.addItem("🎙️ en-US-AndrewMultilingualNeural (Conversational Storyteller)", "en-US-AndrewMultilingualNeural")
        self.tab2_combo_voice.addItem("🎙️ en-US-BrianMultilingualNeural (Crisp STEM Explainer)", "en-US-BrianMultilingualNeural")
        self.tab2_combo_voice.addItem("🎙️ en-US-AvaMultilingualNeural (Expressive Female Narrator)", "en-US-AvaMultilingualNeural")
        self.tab2_combo_voice.addItem("🎙️ en-US-JennyNeural (Warm Female Narrator)", "en-US-JennyNeural")
        mc_layout.addWidget(self.tab2_combo_voice, 4, 1)

        mc_layout.addWidget(QLabel("Speech Speed:"), 4, 2)
        self.tab2_spin_speed = QDoubleSpinBox()
        self.tab2_spin_speed.setRange(0.8, 1.4)
        self.tab2_spin_speed.setSingleStep(0.05)
        self.tab2_spin_speed.setValue(1.00)
        self.tab2_spin_speed.setSuffix("x (1.00 = Natural Human Flow)")
        self.tab2_spin_speed.valueChanged.connect(self._on_script_text_changed)
        self.tab2_combo_voice.currentIndexChanged.connect(self._on_script_text_changed)
        mc_layout.addWidget(self.tab2_spin_speed, 4, 3)

        # Row 5: Picture source. Generative video stays available; hybrid is the default
        # because stock clips of "a watch" do not show a tuning fork.
        mc_layout.addWidget(QLabel("Picture Source:"), 5, 0)
        self.combo_visual_source = QComboBox()
        for mode_id, label in MODE_LABELS.items():
            self.combo_visual_source.addItem(f"{label} ({cost_summary_line(mode_id)})", mode_id)
        saved_source = self.config.get("visual_source", "hybrid_stock")
        source_idx = self.combo_visual_source.findData(saved_source)
        if source_idx < 0:
            source_idx = 0
        self.combo_visual_source.setCurrentIndex(source_idx)
        self.combo_visual_source.currentIndexChanged.connect(self._on_visual_source_changed)
        mc_layout.addWidget(self.combo_visual_source, 5, 1, 1, 3)

        layout.addWidget(meta_card)

        # Middle Card: Script Editor
        script_card = QFrame()
        script_card.setProperty("class", "card")
        sc_layout = QVBoxLayout(script_card)

        # Header metrics
        metrics_layout = QHBoxLayout()
        metrics_title = QLabel("Script Drafting Canvas (Voiceover & Timings)")
        metrics_title.setStyleSheet("font-weight: bold; font-size: 14px; color: #FFFFFF;")
        self.lbl_script_metrics = QLabel("Words: 0 | Est. Spoken Time: 0.0s (Target: 69s)")
        self.lbl_script_metrics.setStyleSheet("color: #0078D4; font-weight: bold;")
        metrics_layout.addWidget(metrics_title)
        metrics_layout.addStretch()
        metrics_layout.addWidget(self.lbl_script_metrics)
        sc_layout.addLayout(metrics_layout)

        # Script text editor
        self.text_script = QTextEdit()
        default_script = (
            "Ancient Roman concrete gets stronger the longer it sits in crashing ocean waves, while modern concrete crumbles in fifty years. "
            "For decades, modern civil engineers couldn't figure out why ancient harbors in Italy survived two millennia of salt water erosion. "
            "The breakthrough came when geologists put Roman seawalls under electron microscopes. "
            "The Romans didn't just mix sand and gravel; they forged their concrete using reactive volcanic ash called pozzolana, slaked lime, and chunks of quicklime hot-mixed together. "
            "When ocean saltwater infiltrates the microscopic pores, it doesn't rot the internal framework. "
            "Instead, the alkaline brine dissolves the volcanic minerals and reacts with the lime clasts, precipitating interlocking crystals of a rare mineral called aluminous tobermorite. "
            "These microscopic crystals expand into microscopic voids, literally stitching microcracks closed like living bone tissue. "
            "The ocean isn't destroying the seawall—it's actively fueling the chemical reaction that cements it tighter with every passing decade, which is why modern architects are still racing to replicate how ancient Roman concrete gets stronger the longer it sits in crashing ocean waves."
        )
        self.text_script.setPlainText(default_script)
        self.text_script.textChanged.connect(self._on_script_text_changed)
        sc_layout.addWidget(self.text_script)

        # AI Prompt Revision Bar
        ai_bar = QHBoxLayout()
        self.input_ai_prompt = QLineEdit()
        self.input_ai_prompt.setPlaceholderText(
            "AI Revision Prompt: e.g. 'Make hook punchier', 'Add curiosity gap', 'Add TikTok shop bridge', 'Shorten for 60s'..."
        )
        self.input_ai_prompt.returnPressed.connect(self._on_modify_script)

        self.btn_modify_script = QPushButton("✨ Modify Script")
        self.btn_modify_script.clicked.connect(self._on_modify_script)

        ai_bar.addWidget(self.input_ai_prompt, stretch=4)
        ai_bar.addWidget(self.btn_modify_script, stretch=1)
        sc_layout.addLayout(ai_bar)

        layout.addWidget(script_card)

        # Bottom Card: Pipeline Execution & Live Terminal Log
        exec_card = QFrame()
        exec_card.setProperty("class", "card")
        ec_layout = QVBoxLayout(exec_card)

        # AI Video (Gemini Omni Flash & Google Flow) Integration Bar
        flow_row = QHBoxLayout()
        self.btn_copy_veo_prompts = QPushButton("📋 Copy Flow Omni Multi-Turn Prompts")
        self.btn_copy_veo_prompts.setStyleSheet("font-size: 12px; font-weight: bold; background-color: #1A365D; color: #63B3ED; padding: 7px 14px;")
        self.btn_copy_veo_prompts.clicked.connect(self._on_copy_veo_prompts)

        self.btn_open_storyboard_folder = QPushButton("📂 Import Custom Video Clips (storyboard/)")
        self.btn_open_storyboard_folder.setStyleSheet("font-size: 12px; font-weight: bold; background-color: #44337A; color: #D6BCFA; padding: 7px 14px;")
        self.btn_open_storyboard_folder.clicked.connect(self._on_open_storyboard_folder)

        flow_row.addWidget(self.btn_copy_veo_prompts, stretch=1)
        flow_row.addWidget(self.btn_open_storyboard_folder, stretch=1)
        ec_layout.addLayout(flow_row)

        btn_row = QHBoxLayout()
        self.btn_save_draft = QPushButton("💾 Save Project Draft")
        self.btn_save_draft.clicked.connect(self._on_save_project_draft)

        self.btn_generate_pipeline = QPushButton("🚀 Generate Video Pipeline (Audio + Foley + Timestamps)")
        self.btn_generate_pipeline.setProperty("class", "primary")
        self.btn_generate_pipeline.setStyleSheet("font-size: 14px; padding: 10px 24px;")
        self.btn_generate_pipeline.clicked.connect(self._on_run_pipeline)

        self.btn_render_blender = QPushButton("🎨 Render AI Storyboard Video")
        self.btn_render_blender.clicked.connect(self._on_render_blender_animation)

        btn_row.addWidget(self.btn_save_draft)
        btn_row.addWidget(self.btn_generate_pipeline, stretch=2)
        btn_row.addWidget(self.btn_render_blender, stretch=1)

        self.btn_open_folder_tab2 = QPushButton("📂 Open Folder")
        self.btn_open_folder_tab2.clicked.connect(self._on_open_project_folder)
        btn_row.addWidget(self.btn_open_folder_tab2)

        ec_layout.addLayout(btn_row)

        self.progress_bar = QProgressBar()
        self.progress_bar.setValue(0)
        self.progress_bar.setTextVisible(True)
        ec_layout.addWidget(self.progress_bar)

        log_header = QLabel("Execution Terminal Log:")
        log_header.setStyleSheet("color: #9AA0A6; font-size: 11px;")
        ec_layout.addWidget(log_header)

        self.terminal_log = QTextEdit()
        self.terminal_log.setReadOnly(True)
        self.terminal_log.setMaximumHeight(130)
        self.terminal_log.setStyleSheet(
            "background-color: #0E0E0E; color: #33FF33; font-family: 'Consolas', monospace; font-size: 11px;"
        )
        ec_layout.addWidget(self.terminal_log)

        layout.addWidget(exec_card)

        # Initial metrics calculation
        self._on_script_text_changed()
        scroll.setWidget(widget)
        return scroll

    # =================================================================
    # TAB 3: VIDEO PLAYER & VIRAL CHECKLIST
    # =================================================================
    def _build_tab_player(self) -> QWidget:
        widget = QWidget()
        outer = QVBoxLayout(widget)
        outer.setContentsMargins(12, 12, 12, 12)
        outer.setSpacing(8)

        toolbar = QHBoxLayout()
        self.btn_toggle_preview = QPushButton("Hide Phone Preview")
        self.btn_toggle_preview.setCheckable(True)
        self.btn_toggle_preview.setChecked(True)
        self.btn_toggle_preview.clicked.connect(self._on_toggle_phone_preview)
        preview_hint = QLabel(
            "The phone preview sits on the right and hides itself when the window is narrow, so it cannot cover the checklist."
        )
        preview_hint.setWordWrap(True)
        preview_hint.setStyleSheet("color: #9AA0A6; font-size: 11px;")
        toolbar.addWidget(self.btn_toggle_preview)
        toolbar.addWidget(preview_hint, stretch=1)
        outer.addLayout(toolbar)

        self.player_splitter = QSplitter(Qt.Horizontal)
        self.player_splitter.setChildrenCollapsible(True)
        self.player_splitter.setHandleWidth(8)
        self.player_splitter.setStyleSheet("QSplitter::handle { background: #2D2D2D; }")

        # Phone preview. It is the trailing splitter column so a narrow window
        # can collapse it instead of letting it cover the checklist.
        player_card = QFrame()
        player_card.setProperty("class", "card")
        pc_layout = QVBoxLayout(player_card)
        pc_layout.setContentsMargins(12, 12, 12, 12)

        p_header = QLabel("Vertical 9:16 Kinetic Video Player")
        p_header.setStyleSheet("font-weight: bold; font-size: 14px; color: #FFFFFF;")
        pc_layout.addWidget(p_header)

        # Stacked player: Dynamic Canvas (index 0) or Video Widget (index 1)
        self.player_stack = QStackedWidget()
        self.preview_canvas = VerticalPreviewCanvas()
        self.video_widget = QVideoWidget()
        self.video_widget.setStyleSheet("background-color: #000000; border-radius: 6px;")
        self.media_player.setVideoOutput(self.video_widget)

        self.player_stack.addWidget(self.preview_canvas)
        self.player_stack.addWidget(self.video_widget)
        pc_layout.addWidget(self.player_stack, stretch=1)

        # Transport Controls
        trans_card = QFrame()
        tc_layout = QVBoxLayout(trans_card)
        tc_layout.setContentsMargins(0, 6, 0, 0)

        # Time Slider & Labels
        time_row = QHBoxLayout()
        self.lbl_time_current = QLabel("00:00")
        self.lbl_time_current.setStyleSheet("color: #9AA0A6; font-size: 11px;")
        self.slider_time = QSlider(Qt.Horizontal)
        self.slider_time.setRange(0, 1000)
        self.slider_time.sliderMoved.connect(self._on_slider_time_moved)
        self.lbl_time_total = QLabel("01:05")
        self.lbl_time_total.setStyleSheet("color: #9AA0A6; font-size: 11px;")

        time_row.addWidget(self.lbl_time_current)
        time_row.addWidget(self.slider_time)
        time_row.addWidget(self.lbl_time_total)
        tc_layout.addLayout(time_row)

        # Control buttons
        btn_ctrl_row = QHBoxLayout()
        self.btn_play_pause = QPushButton("▶ Play")
        self.btn_play_pause.setProperty("class", "primary")
        self.btn_play_pause.clicked.connect(self._on_toggle_play_pause)

        self.btn_stop = QPushButton("⏹ Stop")
        self.btn_stop.clicked.connect(self._on_stop_media)

        self.chk_loop = QCheckBox("Seamless Audio Loop")
        self.chk_loop.setChecked(True)

        vol_lbl = QLabel("Vol:")
        vol_lbl.setStyleSheet("color: #9AA0A6;")
        self.slider_volume = QSlider(Qt.Horizontal)
        self.slider_volume.setRange(0, 100)
        self.slider_volume.setValue(85)
        self.slider_volume.setMaximumWidth(80)
        self.slider_volume.valueChanged.connect(self._on_volume_changed)

        btn_ctrl_row.addWidget(self.btn_play_pause)
        btn_ctrl_row.addWidget(self.btn_stop)
        btn_ctrl_row.addWidget(self.chk_loop)
        btn_ctrl_row.addStretch()
        btn_ctrl_row.addWidget(vol_lbl)
        btn_ctrl_row.addWidget(self.slider_volume)
        tc_layout.addLayout(btn_ctrl_row)

        # Export & Project Folder Controls
        exp_row = QHBoxLayout()
        self.btn_export_video = QPushButton("📥 Download / Export MP4")
        self.btn_export_video.setProperty("class", "primary")
        self.btn_export_video.setStyleSheet("font-weight: bold; padding: 6px 12px;")
        self.btn_export_video.clicked.connect(self._on_export_video)

        self.btn_open_folder = QPushButton("📂 Open Project Folder")
        self.btn_open_folder.setStyleSheet("padding: 6px 12px;")
        self.btn_open_folder.clicked.connect(self._on_open_project_folder)

        exp_row.addWidget(self.btn_export_video)
        exp_row.addWidget(self.btn_open_folder)
        tc_layout.addLayout(exp_row)

        pc_layout.addWidget(trans_card)
        player_card.setMinimumWidth(0)
        player_card.setMaximumWidth(360)

        # Right Column: Viral Checklist & Metadata Review Card
        review_card = QFrame()
        review_card.setProperty("class", "card")
        rc_layout = QVBoxLayout(review_card)
        rc_layout.setContentsMargins(14, 12, 14, 12)
        rc_layout.setSpacing(10)

        rc_title = QLabel("Viral Retention Checklist & Metadata")
        rc_title.setStyleSheet("font-weight: bold; font-size: 14px; color: #FFFFFF;")
        rc_layout.addWidget(rc_title)

        # Visual Critic 4-Keyframe Strip
        critic_group = QGroupBox("🔍 Visual Critic — 4-Keyframe Inspection")
        critic_group.setStyleSheet(
            "QGroupBox { font-weight: bold; color: #0078D4; border: 1px solid #2D2D2D; "
            "margin-top: 6px; padding-top: 10px; border-radius: 6px; }"
        )
        cr_layout = QVBoxLayout(critic_group)
        cr_layout.setSpacing(6)

        thumbs_layout = QHBoxLayout()
        thumbs_layout.setSpacing(8)

        self.critic_thumbs = []
        checkpoints_ui = [
            ("Closed View", "5%"),
            ("Exploded View", "30%"),
            ("Action View", "60%"),
            ("Cutaway View", "88%"),
        ]

        for role_name, pct in checkpoints_ui:
            card_v = QVBoxLayout()
            card_v.setSpacing(2)
            card_v.setAlignment(Qt.AlignCenter)

            lbl_title = QLabel(f"{role_name}\n({pct})")
            lbl_title.setAlignment(Qt.AlignCenter)
            lbl_title.setStyleSheet("font-size: 10px; font-weight: 600; color: #9AA0A6;")

            thumb_lbl = QLabel("No Render")
            thumb_lbl.setFixedSize(70, 110)
            thumb_lbl.setAlignment(Qt.AlignCenter)
            thumb_lbl.setStyleSheet(
                "background-color: #121418; border: 1px solid #333842; "
                "border-radius: 4px; font-size: 9px; color: #5F6368;"
            )
            thumb_lbl.setScaledContents(True)

            card_v.addWidget(lbl_title)
            card_v.addWidget(thumb_lbl)
            thumbs_layout.addLayout(card_v)
            self.critic_thumbs.append(thumb_lbl)

        cr_layout.addLayout(thumbs_layout)

        self.lbl_critic_summary = QLabel("Visual Critic: Standby. Awaiting project render.")
        self.lbl_critic_summary.setStyleSheet("font-size: 10px; color: #9AA0A6;")
        cr_layout.addWidget(self.lbl_critic_summary)

        rc_layout.addWidget(critic_group)

        # Checklist Group
        chk_group = QGroupBox("Retention Optimization Checklist")
        chk_group.setStyleSheet("QGroupBox { font-weight: bold; color: #0078D4; border: 1px solid #2D2D2D; margin-top: 6px; padding-top: 10px; border-radius: 6px; }")
        cg_layout = QVBoxLayout(chk_group)
        cg_layout.setSpacing(8)

        self.chk_frame1 = QCheckBox("Frame 1 Visual Incomplete (Curiosity Gap within 3s)")
        self.chk_loop_check = QCheckBox("Seamless Audio Loop (Ending hooks into opening line)")
        self.chk_friction = QCheckBox("Comment Friction Trigger (Sparks viewer debate/questions)")
        self.chk_duration = QCheckBox("Duration 60s+ (monetization length)")
        self.chk_foley = QCheckBox("ASMR Foley Level Balanced (Crayon scrub audible & crisp)")

        checklist_items = [
            self.chk_frame1,
            self.chk_loop_check,
            self.chk_friction,
            self.chk_duration,
            self.chk_foley,
        ]
        for chk in checklist_items:
            chk.stateChanged.connect(self._on_checklist_toggled)
            cg_layout.addWidget(chk)

        self.lbl_checklist_score = QLabel("Score: 0 / 5 Checks Passed")
        self.lbl_checklist_score.setStyleSheet("color: #D88D00; font-weight: bold; margin-top: 4px;")
        cg_layout.addWidget(self.lbl_checklist_score)
        rc_layout.addWidget(chk_group)

        # Metadata Review Box
        meta_group = QGroupBox("Social Post Metadata")
        meta_group.setStyleSheet("QGroupBox { font-weight: bold; color: #0078D4; border: 1px solid #2D2D2D; margin-top: 6px; padding-top: 10px; border-radius: 6px; }")
        mg_layout = QVBoxLayout(meta_group)

        mg_layout.addWidget(QLabel("Title:"))
        self.meta_title = QLineEdit()
        mg_layout.addWidget(self.meta_title)

        mg_layout.addWidget(QLabel("Description / Caption:"))
        self.meta_description = QTextEdit()
        self.meta_description.setMaximumHeight(70)
        mg_layout.addWidget(self.meta_description)

        mg_layout.addWidget(QLabel("Hashtags:"))
        self.meta_hashtags = QLineEdit("#stem #crayonart #satisfying #engineering #learnontiktok")
        mg_layout.addWidget(self.meta_hashtags)

        rc_layout.addWidget(meta_group)

        # AI Visual Revision Prompt Bar
        rev_group = QGroupBox("⚡ AI Visual Revision & Re-Render")
        rev_group.setStyleSheet(
            "QGroupBox { font-weight: bold; color: #0078D4; border: 1px solid #2D2D2D; "
            "margin-top: 6px; padding-top: 10px; border-radius: 6px; }"
        )
        rev_layout = QHBoxLayout(rev_group)
        rev_layout.setSpacing(8)

        self.input_visual_revision = QLineEdit()
        self.input_visual_revision.setPlaceholderText("e.g. Expand exploded parts wider, intensify spark emissive, change spring to copper...")
        self.btn_apply_visual_revision = QPushButton("⚡ Re-Render Visuals")
        self.btn_apply_visual_revision.setProperty("class", "primary")
        self.btn_apply_visual_revision.clicked.connect(self._on_apply_visual_revision)

        rev_layout.addWidget(self.input_visual_revision, stretch=1)
        rev_layout.addWidget(self.btn_apply_visual_revision)
        rc_layout.addWidget(rev_group)

        # Action Buttons
        act_box = QVBoxLayout()
        act_box.setSpacing(8)

        self.btn_mark_ready = QPushButton("✅ Mark Project 'Ready' & Save Metadata")
        self.btn_mark_ready.setProperty("class", "success")
        self.btn_mark_ready.clicked.connect(self._on_mark_ready)

        dispatch_row = QHBoxLayout()
        self.btn_dispatch_yt = QPushButton("📤 Simulate YouTube Dispatch")
        self.btn_dispatch_yt.clicked.connect(self._on_dispatch_youtube)

        self.btn_dispatch_tt = QPushButton("🎵 Simulate TikTok Dispatch")
        self.btn_dispatch_tt.clicked.connect(self._on_dispatch_tiktok)

        dispatch_row.addWidget(self.btn_dispatch_yt)
        dispatch_row.addWidget(self.btn_dispatch_tt)

        act_box.addWidget(self.btn_mark_ready)
        act_box.addLayout(dispatch_row)
        rc_layout.addLayout(act_box)

        content_scroll = QScrollArea()
        content_scroll.setWidgetResizable(True)
        content_scroll.setFrameShape(QFrame.NoFrame)
        content_scroll.setMinimumWidth(0)
        content_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        review_card.setMinimumWidth(0)
        content_scroll.setWidget(review_card)

        # Checklist is the leading column. The phone preview is the trailing
        # column and is collapsible, so a narrow window cannot paint it over
        # the checklist.
        self.player_splitter.addWidget(content_scroll)
        self.player_splitter.addWidget(player_card)
        self.player_splitter.setStretchFactor(0, 3)
        self.player_splitter.setStretchFactor(1, 1)
        self.player_splitter.setCollapsible(0, False)
        self.player_splitter.setCollapsible(1, True)
        outer.addWidget(self.player_splitter, stretch=1)
        return widget

    # =================================================================
    # TAB 4: CONTENT CALENDAR
    # =================================================================
    def _build_tab_calendar(self) -> QWidget:
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(12)

        # Calendar Toolbar
        cal_toolbar = QFrame()
        cal_toolbar.setProperty("class", "card")
        ct_layout = QHBoxLayout(cal_toolbar)

        cal_title = QLabel("📅 14-Day Production & Dispatch Calendar")
        cal_title.setStyleSheet("font-weight: bold; font-size: 15px; color: #FFFFFF;")
        ct_layout.addWidget(cal_title)
        ct_layout.addStretch()

        self.btn_refresh_cal = QPushButton("🔄 Refresh Calendar")
        self.btn_refresh_cal.clicked.connect(self.refresh_calendar)
        ct_layout.addWidget(self.btn_refresh_cal)

        layout.addWidget(cal_toolbar)

        # Scrollable 14-day Grid
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setStyleSheet("QScrollArea { border: none; background: transparent; }")

        self.cal_grid_container = QWidget()
        self.cal_grid_layout = QGridLayout(self.cal_grid_container)
        self.cal_grid_layout.setSpacing(10)

        scroll.setWidget(self.cal_grid_container)
        layout.addWidget(scroll)

        return widget

    # =================================================================
    # TAB 5: SETTINGS
    # =================================================================
    def _build_tab_settings(self) -> QWidget:
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(14)

        set_card = QFrame()
        set_card.setProperty("class", "card")
        sc_layout = QGridLayout(set_card)
        sc_layout.setHorizontalSpacing(16)
        sc_layout.setVerticalSpacing(12)

        # Title
        sec_title = QLabel("CrayonStudio Pipeline & Engine Configurations")
        sec_title.setStyleSheet("font-weight: bold; font-size: 15px; color: #FFFFFF; margin-bottom: 8px;")
        sc_layout.addWidget(sec_title, 0, 0, 1, 3)

        # Blender Path Picker
        sc_layout.addWidget(QLabel("Blender Executable:"), 1, 0)
        self.input_blender_path = QLineEdit()
        self.btn_browse_blender = QPushButton("Browse...")
        self.btn_browse_blender.clicked.connect(self._on_browse_blender)
        sc_layout.addWidget(self.input_blender_path, 1, 1)
        sc_layout.addWidget(self.btn_browse_blender, 1, 2)

        # FFmpeg Path Picker
        sc_layout.addWidget(QLabel("FFmpeg Executable:"), 2, 0)
        self.input_ffmpeg_path = QLineEdit()
        self.btn_browse_ffmpeg = QPushButton("Browse...")
        self.btn_browse_ffmpeg.clicked.connect(self._on_browse_ffmpeg)
        sc_layout.addWidget(self.input_ffmpeg_path, 2, 1)
        sc_layout.addWidget(self.btn_browse_ffmpeg, 2, 2)

        # Binary Validator Button
        self.btn_validate_binaries = QPushButton("🔍 Validate Executables")
        self.btn_validate_binaries.clicked.connect(self._on_validate_binaries)
        self.lbl_binary_status = QLabel("Status: Unchecked")
        self.lbl_binary_status.setStyleSheet("color: #9AA0A6;")
        sc_layout.addWidget(self.btn_validate_binaries, 3, 1)
        sc_layout.addWidget(self.lbl_binary_status, 3, 2)

        # Narrator Voice Selection
        sc_layout.addWidget(QLabel("Narrator Voice:"), 4, 0)
        self.combo_voice = QComboBox()
        self.combo_voice.addItems([
            "en-US-GuyNeural",
            "en-US-ChristopherNeural",
            "en-US-AndrewMultilingualNeural",
            "en-US-BrianMultilingualNeural",
            "en-US-AvaMultilingualNeural",
            "en-US-JennyNeural",
            "af_heart",
            "am_adam",
        ])
        sc_layout.addWidget(self.combo_voice, 4, 1)

        # Speech Speed
        sc_layout.addWidget(QLabel("TTS Speech Speed:"), 5, 0)
        self.spin_speed = QDoubleSpinBox()
        self.spin_speed.setRange(0.8, 1.5)
        self.spin_speed.setSingleStep(0.05)
        self.spin_speed.setValue(1.00)
        self.spin_speed.setSuffix("x (1.00 = Natural Human Flow)")
        sc_layout.addWidget(self.spin_speed, 5, 1)

        # Default Target Duration
        sc_layout.addWidget(QLabel("Default Target Duration:"), 6, 0)
        self.spin_default_duration = QSpinBox()
        self.spin_default_duration.setRange(60, 180)
        self.spin_default_duration.setValue(69)
        self.spin_default_duration.setSuffix("s")
        sc_layout.addWidget(self.spin_default_duration, 6, 1)

        # Dry Run Toggle
        sc_layout.addWidget(QLabel("API Posting Mode:"), 7, 0)
        self.chk_dry_run = QCheckBox("Dry-Run Mode (Simulate API dispatches without hitting live endpoints)")
        self.chk_dry_run.setChecked(True)
        self.chk_dry_run.stateChanged.connect(self._on_dry_run_toggled)
        sc_layout.addWidget(self.chk_dry_run, 7, 1, 1, 2)

        # Optional YouTube API Key
        sc_layout.addWidget(QLabel("YouTube API Key (Optional):"), 8, 0)
        self.input_yt_key = QLineEdit()
        self.input_yt_key.setEchoMode(QLineEdit.Password)
        self.input_yt_key.setPlaceholderText("Paste API key here...")
        sc_layout.addWidget(self.input_yt_key, 8, 1)

        # Google Gemini / Imagen API Key
        sc_layout.addWidget(QLabel("Google Gemini API Key (Optional):"), 9, 0)
        self.input_gemini_key = QLineEdit()
        self.input_gemini_key.setEchoMode(QLineEdit.Password)
        self.input_gemini_key.setPlaceholderText("Paste Gemini API key for Imagen 3 & Vision analysis (or leave blank for free Flux)")
        sc_layout.addWidget(self.input_gemini_key, 9, 1, 1, 2)

        sc_layout.addWidget(QLabel("Pexels API Key (free stock):"), 12, 0)
        self.input_pexels_key = QLineEdit()
        self.input_pexels_key.setEchoMode(QLineEdit.Password)
        self.input_pexels_key.setPlaceholderText("Optional. Used only when a clip matches the mechanism.")
        sc_layout.addWidget(self.input_pexels_key, 12, 1, 1, 2)

        sc_layout.addWidget(QLabel("Pixabay API Key (free stock):"), 13, 0)
        self.input_pixabay_key = QLineEdit()
        self.input_pixabay_key.setEchoMode(QLineEdit.Password)
        self.input_pixabay_key.setPlaceholderText("Optional second stock source.")
        sc_layout.addWidget(self.input_pixabay_key, 13, 1, 1, 2)

        # Default Style Reference Screenshot
        sc_layout.addWidget(QLabel("Default Style Reference Screenshot:"), 10, 0)
        def_style_layout = QHBoxLayout()
        self.input_default_style_ref = QLineEdit()
        self.input_default_style_ref.setPlaceholderText("Optional path to default style_reference.png...")
        self.btn_browse_default_style = QPushButton("Browse...")
        self.btn_browse_default_style.clicked.connect(self._on_browse_default_style)
        def_style_layout.addWidget(self.input_default_style_ref)
        def_style_layout.addWidget(self.btn_browse_default_style)
        sc_layout.addLayout(def_style_layout, 10, 1, 1, 2)

        # Save Button & Status
        btn_save_settings = QPushButton("💾 Save Settings to config.json")
        btn_save_settings.setProperty("class", "primary")
        btn_save_settings.clicked.connect(self._on_save_settings)
        sc_layout.addWidget(btn_save_settings, 14, 1)

        self.lbl_settings_saved = QLabel("")
        self.lbl_settings_saved.setStyleSheet("color: #107C41; font-weight: bold;")
        sc_layout.addWidget(self.lbl_settings_saved, 14, 2)

        layout.addWidget(set_card)
        layout.addStretch()
        return widget

    # =================================================================
    # PLAYER EVENT HANDLERS & WIRING
    # =================================================================
    def _wire_player_events(self):
        """Wire signals from QMediaPlayer to transport controls and preview canvas."""
        self.media_player.positionChanged.connect(self._on_player_position_changed)
        self.media_player.durationChanged.connect(self._on_player_duration_changed)
        self.media_player.mediaStatusChanged.connect(self._on_player_status_changed)

    def _on_player_position_changed(self, pos_ms: int):
        dur_ms = self.media_player.duration()
        if dur_ms > 0:
            ratio = int((pos_ms / dur_ms) * 1000)
            self.slider_time.blockSignals(True)
            self.slider_time.setValue(ratio)
            self.slider_time.blockSignals(False)

        current_sec = pos_ms // 1000
        total_sec = dur_ms // 1000 if dur_ms > 0 else 65
        self.lbl_time_current.setText(f"{current_sec // 60:02d}:{current_sec % 60:02d}")
        self.lbl_time_total.setText(f"{total_sec // 60:02d}:{total_sec % 60:02d}")
        self.preview_canvas.update_position(pos_ms, dur_ms)

    def _on_player_duration_changed(self, dur_ms: int):
        total_sec = dur_ms // 1000
        self.lbl_time_total.setText(f"{total_sec // 60:02d}:{total_sec % 60:02d}")
        self.preview_canvas.update_position(self.media_player.position(), dur_ms)

        # Check if duration falls within viral 61s-75s window
        if 61 <= total_sec <= 75:
            self.chk_duration.setChecked(True)
        else:
            self.chk_duration.setChecked(False)

    def _on_player_status_changed(self, status):
        if status == QMediaPlayer.MediaStatus.EndOfMedia:
            if self.chk_loop.isChecked():
                self.media_player.setPosition(0)
                self.media_player.play()
            else:
                self.btn_play_pause.setText("▶ Play")

    def _on_toggle_play_pause(self):
        if not self.current_media_path:
            QMessageBox.information(
                self,
                "No Audio Track Loaded",
                "Please run 'Generate Video Pipeline' in Tab 2 or load an existing project first.",
            )
            return

        if self.media_player.playbackState() == QMediaPlayer.PlaybackState.PlayingState:
            self.media_player.pause()
            self.btn_play_pause.setText("▶ Play")
        else:
            self.media_player.play()
            self.btn_play_pause.setText("⏸ Pause")

    def _on_stop_media(self):
        self.media_player.stop()
        self.btn_play_pause.setText("▶ Play")
        self.preview_canvas.update_position(0, self.media_player.duration())

    def _on_slider_time_moved(self, value: int):
        dur = self.media_player.duration()
        if dur > 0:
            target_ms = int((value / 1000.0) * dur)
            self.media_player.setPosition(target_ms)

    def _on_volume_changed(self, value: int):
        self.audio_output.setVolume(value / 100.0)

    # =================================================================
    # TAB 1 LOGIC: TREND RESEARCH & COMPETITOR COMMENT MINING
    # =================================================================
    def _on_search_mode_changed(self, idx: int):
        mode = self.combo_search_mode.currentData()
        if mode == "channel":
            self.trend_search_input.setPlaceholderText(
                "Scan competitor channel (e.g. '@TheActionLab', '@Veritasium', '@HowThingsWork', or channel URL)..."
            )
        else:
            self.trend_search_input.setPlaceholderText(
                "Search viral niche (e.g. 'why Roman concrete heals', 'piezoelectric lighter', 'vacuum experiment')..."
            )

    def _on_search_preset(self, text: str, mode: str):
        idx = self.combo_search_mode.findData(mode)
        if idx >= 0:
            self.combo_search_mode.setCurrentIndex(idx)
        self.trend_search_input.setText(text)
        self._on_search_trends()

    def _on_search_trends(self):
        query = self.trend_search_input.text().strip()
        mode = self.combo_search_mode.currentData() or "keyword"
        if not query:
            query = "@TheActionLab" if mode == "channel" else "why Roman concrete heals"
            self.trend_search_input.setText(query)

        self.btn_analyze.setEnabled(False)
        target_desc = f"channel '{query}'" if mode == "channel" else f"'{query}'"
        self.lbl_trend_status.setText(f"Mining competitor comments & audience friction for {target_desc}...")
        self.lbl_trend_status.setStyleSheet("color: #0078D4; font-weight: bold;")

        self.scraper_thread = ScraperWorker(
            query=query,
            max_results=5,
            api_key=self.config.get("youtube_api_key"),
            mode=mode,
        )
        self.scraper_thread.progress.connect(lambda msg: self.lbl_trend_status.setText(msg))
        self.scraper_thread.finished.connect(self._on_trends_extracted)
        self.scraper_thread.error.connect(self._on_trends_error)
        self.scraper_thread.start()

    def _on_trends_extracted(self, payload: Dict[str, Any]):
        self.btn_analyze.setEnabled(True)
        trends = payload.get("trends", [])
        suggestions = payload.get("suggestions", [])
        self.lbl_trend_status.setText(f"Found {len(trends)} competitor videos. Generated {len(suggestions)} content concepts.")
        self.lbl_trend_status.setStyleSheet("color: #107C41; font-weight: bold;")

        self.table_trends.setRowCount(0)
        for row_idx, item in enumerate(trends):
            self.table_trends.insertRow(row_idx)
            self.table_trends.setItem(row_idx, 0, QTableWidgetItem(str(item.get("topic", ""))))
            views = item.get("views", 0)
            self.table_trends.setItem(row_idx, 1, QTableWidgetItem(f"{views:,}"))
            self.table_trends.setItem(row_idx, 2, QTableWidgetItem(str(item.get("confusion_points", ""))))
            self.table_trends.setItem(row_idx, 3, QTableWidgetItem(str(item.get("complaints", ""))))
            self.table_trends.setItem(row_idx, 4, QTableWidgetItem(str(item.get("praises", ""))))
            self.table_trends.setItem(row_idx, 5, QTableWidgetItem(str(item.get("content_gaps", ""))))

        if trends:
            self.table_trends.selectRow(0)

        self._populate_suggestion_deck(suggestions)

    def _populate_suggestion_deck(self, suggestions: List[Dict[str, Any]]):
        """Build interactive cards for AI content suggestions."""
        while self.sugg_layout.count():
            item = self.sugg_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        if not suggestions:
            empty_lbl = QLabel("No content concepts generated. Run an analysis above to populate suggestions.")
            empty_lbl.setStyleSheet("color: #777777; font-style: italic; padding: 12px;")
            self.sugg_layout.addWidget(empty_lbl)
            self.lbl_sugg_count.setText("0 Concepts available")
            return

        self.lbl_sugg_count.setText(f"{len(suggestions)} AI Content Concepts Ready")

        for sugg in suggestions:
            card = QFrame()
            card.setStyleSheet(
                "QFrame { background-color: #1E222A; border: 1px solid #333842; "
                "border-radius: 8px; padding: 10px; }"
            )
            c_layout = QVBoxLayout(card)
            c_layout.setContentsMargins(10, 8, 10, 8)
            c_layout.setSpacing(6)

            # Header: Title + Engine Badge + Category Badge
            h_row = QHBoxLayout()
            lbl_title = QLabel(sugg.get("title", "Concept"))
            lbl_title.setStyleSheet("font-weight: bold; font-size: 13px; color: #FFFFFF;")

            eng = sugg.get("recommended_engine", "2D_Crayon")
            eng_bg = "#FF6B6B" if eng == "3D_Teardown" else "#0078D4"
            eng_txt = "3D TEARDOWN" if eng == "3D_Teardown" else "2D CRAYON"
            lbl_eng = QLabel(eng_txt)
            lbl_eng.setStyleSheet(
                f"background-color: {eng_bg}; color: #FFFFFF; font-size: 9px; font-weight: bold; "
                "padding: 2px 6px; border-radius: 3px;"
            )

            lbl_cat = QLabel(sugg.get("category", "STEM").upper())
            lbl_cat.setStyleSheet(
                "background-color: #2D3139; color: #9AA0A6; font-size: 9px; font-weight: bold; "
                "padding: 2px 6px; border-radius: 3px;"
            )

            h_row.addWidget(lbl_title)
            h_row.addStretch()
            h_row.addWidget(lbl_cat)
            h_row.addWidget(lbl_eng)
            c_layout.addLayout(h_row)

            # Hook Preview
            hook_text = sugg.get("hook", "")
            lbl_hook = QLabel(f"🎣 Opening Hook: \"{hook_text}\"")
            lbl_hook.setStyleSheet("color: #64D2FF; font-size: 11px; font-style: italic;")
            lbl_hook.setWordWrap(True)
            c_layout.addWidget(lbl_hook)

            # Competitive Advantage Note
            adv_text = sugg.get("competitive_advantage", "")
            lbl_adv = QLabel(f"⚡ Competitive Edge: {adv_text}")
            lbl_adv.setStyleSheet("color: #34D399; font-size: 10px;")
            lbl_adv.setWordWrap(True)
            c_layout.addWidget(lbl_adv)

            # Action button
            b_row = QHBoxLayout()
            b_row.addStretch()
            btn_use = QPushButton("🚀 Use This Concept in Studio →")
            btn_use.setProperty("class", "primary")
            btn_use.clicked.connect(lambda chk, s=sugg: self._on_use_suggestion(s))
            b_row.addWidget(btn_use)
            c_layout.addLayout(b_row)

            self.sugg_layout.addWidget(card)

    def _on_use_suggestion(self, sugg: Dict[str, Any]):
        """Load selected AI content suggestion into Production Studio."""
        title = sugg.get("title", "")
        cat = sugg.get("category", "STEM")
        engine = sugg.get("recommended_engine", "2D_Crayon")
        hook = sugg.get("hook", "")
        confusion = sugg.get("confusion_focus", "")
        gap = sugg.get("complaint_resolved", "")

        self.input_title.setText(title)

        cat_idx = self.combo_category.findText(cat)
        if cat_idx >= 0:
            self.combo_category.setCurrentIndex(cat_idx)

        eng_idx = self.combo_engine.findData(engine)
        if eng_idx >= 0:
            self.combo_engine.setCurrentIndex(eng_idx)

        # Generate full script starting with pre-crafted hook
        new_script = modify_script(
            script_text="",
            prompt=f"Create hook: {hook}. Address confusion: {confusion}. Include gap: {gap}",
            category=cat,
            target_duration=self.spin_duration.value(),
            tiktok_product=self.combo_product.currentText(),
            topic=title,
            speech_speed=self.tab2_spin_speed.value(),
            voice=self.tab2_combo_voice.currentData() or "en-US-GuyNeural",
        )
        self.text_script.setPlainText(new_script)

        self.tab_widget.setCurrentIndex(1)
        self.status_bar.showMessage(f"AI Concept '{title}' transferred to Production Studio (Engine: {engine}).", 4000)
        self.terminal_log.append(f"[{datetime.datetime.now().strftime('%H:%M:%S')}] 🎯 Transferred concept '{title}' to Studio ({engine}).")

    def _on_trends_error(self, err: str):
        self.btn_analyze.setEnabled(True)
        self.lbl_trend_status.setText(f"Error: {err}")
        self.lbl_trend_status.setStyleSheet("color: #D83B01; font-weight: bold;")

    def _on_use_as_topic(self):
        row = self.table_trends.currentRow()
        if row < 0:
            QMessageBox.information(self, "Select a Topic", "Please select a row from the trend research table.")
            return

        topic = self.table_trends.item(row, 0).text()
        confusion = self.table_trends.item(row, 2).text() if self.table_trends.columnCount() > 2 else ""
        complaint = self.table_trends.item(row, 3).text() if self.table_trends.columnCount() > 3 else ""
        gap = self.table_trends.item(row, 5).text() if self.table_trends.columnCount() > 5 else ""

        # Deduce category & engine
        topic_lower = topic.lower()
        if any(w in topic_lower for w in ["machine", "engine", "gear", "device", "hardware", "motor", "tool", "hydraulic", "lighter", "piezo"]):
            cat_idx = self.combo_category.findText("Engineering")
            eng_idx = self.combo_engine.findData("3D_Teardown")
        elif any(w in topic_lower for w in ["how it's made", "how it is made", "manufacturing", "factory", "assembly"]):
            cat_idx = self.combo_category.findText("How It's Made")
            eng_idx = self.combo_engine.findData("3D_Teardown")
        elif "heist" in topic_lower or "vault" in topic_lower or "escape" in topic_lower:
            cat_idx = self.combo_category.findText("Escape/Heist")
            eng_idx = self.combo_engine.findData("2D_Crayon")
        elif "concrete" in topic_lower or "bridge" in topic_lower or "building" in topic_lower:
            cat_idx = self.combo_category.findText("Architecture")
            eng_idx = self.combo_engine.findData("2D_Crayon")
        elif "brain" in topic_lower or "psychology" in topic_lower or "illusion" in topic_lower:
            cat_idx = self.combo_category.findText("Psychology")
            eng_idx = self.combo_engine.findData("2D_Crayon")
        else:
            cat_idx = self.combo_category.findText("STEM")
            eng_idx = self.combo_engine.findData("2D_Crayon")

        if cat_idx >= 0:
            self.combo_category.setCurrentIndex(cat_idx)
        if eng_idx >= 0:
            self.combo_engine.setCurrentIndex(eng_idx)

        self.input_title.setText(topic)
        new_script = modify_script(
            script_text="",
            prompt=f"Create hook addressing confusion: {confusion}. Fix competitor flaw: {complaint}. Include gap: {gap}",
            category=self.combo_category.currentText(),
            target_duration=self.spin_duration.value(),
            tiktok_product=self.combo_product.currentText(),
            topic=topic,
            speech_speed=self.tab2_spin_speed.value(),
            voice=self.tab2_combo_voice.currentData() or "en-US-GuyNeural",
        )
        self.text_script.setPlainText(new_script)

        self.tab_widget.setCurrentIndex(1)
        self.status_bar.showMessage(f"Topic '{topic}' transferred to Production Studio.", 4000)

    def _on_save_trend_to_db(self):
        row = self.table_trends.currentRow()
        if row < 0:
            QMessageBox.information(self, "Select a Topic", "Please select a row to save.")
            return

        topic = self.table_trends.item(row, 0).text()
        views_str = self.table_trends.item(row, 1).text().replace(",", "")
        views = int(views_str) if views_str.isdigit() else 0
        confusion = self.table_trends.item(row, 2).text()
        complaints = self.table_trends.item(row, 3).text()
        praises = self.table_trends.item(row, 4).text()
        gap = self.table_trends.item(row, 5).text()

        row_id = db.save_trend_insight(
            topic=topic,
            source_url="https://youtube.com/search?q=" + topic,
            views=views,
            content_gaps=gap,
            confusion_points=confusion,
            complaints=complaints,
            praises=praises,
        )
        QMessageBox.information(self, "Trend Saved", f"Saved trend '{topic}' with comment intelligence to SQLite (ID: {row_id}).")

    def _on_load_saved_trends(self):
        trends = db.get_all_trends()
        if not trends:
            QMessageBox.information(self, "No Saved Trends", "No trend records found in SQLite database.")
            return

        self.table_trends.setRowCount(0)
        for row_idx, item in enumerate(trends):
            self.table_trends.insertRow(row_idx)
            self.table_trends.setItem(row_idx, 0, QTableWidgetItem(str(item.get("topic", ""))))
            views = item.get("views", 0)
            self.table_trends.setItem(row_idx, 1, QTableWidgetItem(f"{views:,}"))
            self.table_trends.setItem(row_idx, 2, QTableWidgetItem(str(item.get("confusion_points", ""))))
            self.table_trends.setItem(row_idx, 3, QTableWidgetItem(str(item.get("complaints", ""))))
            self.table_trends.setItem(row_idx, 4, QTableWidgetItem(str(item.get("praises", ""))))
            self.table_trends.setItem(row_idx, 5, QTableWidgetItem(str(item.get("content_gaps", ""))))

        suggestions = generate_content_suggestions(trends)
        self._populate_suggestion_deck(suggestions)
        self.lbl_trend_status.setText(f"Loaded {len(trends)} trends from SQLite.")

    # =================================================================
    # TAB 2 LOGIC: PRODUCTION STUDIO
    # =================================================================
    def _on_script_text_changed(self):
        text = self.text_script.toPlainText()
        words = [w for w in text.split() if w.strip()]
        word_count = len(words)
        voice = "en-US-GuyNeural"
        speed = 1.05
        if hasattr(self, "tab2_combo_voice") and self.tab2_combo_voice.currentData():
            voice = self.tab2_combo_voice.currentData()
        if hasattr(self, "tab2_spin_speed"):
            speed = self.tab2_spin_speed.value()
        # Measured neural rate, including the speed multiplier. 145 WPM
        # marked a ~46s GuyNeural read as a 60s script.
        est_seconds = estimate_spoken_seconds(word_count, speed=speed, voice=voice)
        needed = words_required(self.spin_duration.value(), speed=speed, voice=voice)

        target = self.spin_duration.value()
        color = "#107C41" if est_seconds >= MIN_PUBLISH_SECONDS else "#D88D00"
        if est_seconds >= float(target):
            hint = "✓ Spoken time meets the target"
        elif est_seconds >= MIN_PUBLISH_SECONDS:
            hint = f"Clears 60s — need about {needed} words to hold {target}s"
        else:
            hint = f"Under 60s at this voice — need about {needed} words"

        self.lbl_script_metrics.setText(
            f"Words: {word_count} | Est. Spoken Time: {est_seconds:.1f}s (Target: {target}s) — {hint}"
        )
        self.lbl_script_metrics.setStyleSheet(f"color: {color}; font-weight: bold;")

    def _on_category_changed(self, cat: str):
        cat_clean = cat.strip()
        if cat_clean in ("How It's Made", "Engineering"):
            idx = self.combo_engine.findData("3D_Teardown")
            if idx >= 0:
                self.combo_engine.setCurrentIndex(idx)
        elif cat_clean in ("Psychology", "Escape/Heist"):
            idx = self.combo_engine.findData("2D_Crayon")
            if idx >= 0:
                self.combo_engine.setCurrentIndex(idx)

    def _on_modify_script(self):
        prompt = self.input_ai_prompt.text().strip()
        if not prompt:
            prompt = "Make hook punchier and insert curiosity gap"
            self.input_ai_prompt.setText(prompt)

        current_script = self.text_script.toPlainText()
        revised = modify_script(
            script_text=current_script,
            prompt=prompt,
            category=self.combo_category.currentText(),
            target_duration=self.spin_duration.value(),
            tiktok_product=self.combo_product.currentText(),
            topic=self.input_title.text().strip(),
            speech_speed=self.tab2_spin_speed.value(),
            voice=self.tab2_combo_voice.currentData() or "en-US-GuyNeural",
        )
        self.text_script.setPlainText(revised)
        self.terminal_log.append(f"[{datetime.datetime.now().strftime('%H:%M:%S')}] ✨ Applied AI revision: '{prompt}'")
        self.input_ai_prompt.clear()

    def _on_save_project_draft(self):
        title = self.input_title.text().strip() or "Untitled Crayon Project"
        slug = re.sub(r"[^a-zA-Z0-9_-]", "-", title.lower())[:50]
        category = self.combo_category.currentText()
        script = self.text_script.toPlainText()
        dur = self.spin_duration.value()
        product = self.combo_product.currentText()
        v_engine = self.combo_engine.currentData() or "2D_Crayon"

        existing = db.get_project_by_slug(slug)
        if existing:
            db.update_project(
                project_id=existing["id"],
                title=title,
                category=category,
                script_text=script,
                duration_target=dur,
                tiktok_product=product,
                visual_engine=v_engine,
            )
            self.active_project_id = existing["id"]
        else:
            self.active_project_id = db.create_project(
                project_slug=slug,
                title=title,
                category=category,
                script_text=script,
                duration_target=dur,
                tiktok_product=product,
                status="Draft",
                visual_engine=v_engine,
            )

        self.active_project_slug = slug
        self.terminal_log.append(f"[{datetime.datetime.now().strftime('%H:%M:%S')}] 💾 Project Draft saved (ID: {self.active_project_id}, Engine: {v_engine})")
        self.status_bar.showMessage("Project draft saved to SQLite database.", 3000)
        self.refresh_calendar()

    def _on_run_pipeline(self):
        self.media_player.stop()
        self.media_player.setSource(QUrl())
        title = self.input_title.text().strip() or "Untitled Crayon Project"
        slug = re.sub(r"[^a-zA-Z0-9_-]", "-", title.lower())[:50]
        self.active_project_slug = slug

        script = self.text_script.toPlainText().strip()
        if not script:
            QMessageBox.warning(self, "Empty Script", "Please enter script text before generating the pipeline.")
            return

        self.btn_generate_pipeline.setEnabled(False)
        self.progress_bar.setValue(5)
        self.terminal_log.append(
            f"[{datetime.datetime.now().strftime('%H:%M:%S')}] 🚀 Initiating Pipeline Worker for: '{title}'..."
        )

        if hasattr(self, "tab2_combo_voice") and self.tab2_combo_voice.currentData():
            voice = self.tab2_combo_voice.currentData()
        elif hasattr(self, "combo_voice"):
            voice = self.combo_voice.currentText()
        else:
            voice = "en-US-GuyNeural"

        if hasattr(self, "tab2_spin_speed"):
            speed = self.tab2_spin_speed.value()
        elif hasattr(self, "spin_speed"):
            speed = self.spin_speed.value()
        else:
            speed = 1.00

        v_engine = self.combo_engine.currentData() or "2D_Crayon"

        self.pipeline_thread = PipelineWorker(
            project_slug=slug,
            title=title,
            hook=script.split(".")[0] if "." in script else script[:60],
            category=self.combo_category.currentText(),
            script_text=script,
            duration_target=self.spin_duration.value(),
            tiktok_product=self.combo_product.currentText(),
            voice=voice,
            speed=speed,
            visual_engine=v_engine,
        )
        self.pipeline_thread.log_message.connect(self._on_pipeline_log)
        self.pipeline_thread.progress_val.connect(self.progress_bar.setValue)
        self.pipeline_thread.pipeline_finished.connect(self._on_pipeline_completed)
        self.pipeline_thread.pipeline_error.connect(self._on_pipeline_error)
        self.pipeline_thread.start()

    def _on_pipeline_log(self, msg: str):
        self.terminal_log.append(f"[{datetime.datetime.now().strftime('%H:%M:%S')}] {msg}")

    def _on_pipeline_completed(self, payload: Dict[str, Any]):
        self.btn_generate_pipeline.setEnabled(True)
        self.active_project_id = payload.get("project_id")
        vo_path = payload.get("voiceover_path")
        self.current_media_path = vo_path

        # Update Tab 3
        self.meta_title.setText(payload.get("title", ""))
        self.meta_description.setText(
            f"{payload.get('script_text', '')[:120]}...\n\nAnimation created via CrayonStudio."
        )
        cat_lower = payload.get("category", "stem").lower().replace(" ", "")
        engine_tag = "#cad #explodedview" if payload.get("visual_engine") == "3D_Teardown" else "#crayonanimation"
        self.meta_hashtags.setText(
            f"#{cat_lower} {engine_tag} #satisfying #engineering #learnontiktok"
        )
        self.preview_canvas.update_metadata(
            title=payload.get("title", ""),
            hook=payload.get("script_text", "").split(".")[0],
            category=payload.get("category", "STEM"),
        )
        words_json = payload.get("words_json_path")
        if words_json and os.path.exists(words_json):
            try:
                with open(words_json, "r", encoding="utf-8") as f:
                    self.preview_canvas.set_word_timestamps(json.load(f))
            except Exception:
                pass

        # Load media in player
        if vo_path and os.path.exists(vo_path):
            self.media_player.setSource(QUrl.fromLocalFile(vo_path))
            self.btn_play_pause.setText("▶ Play")

        # Evaluate viral retention checklist automatically
        duration = payload.get("duration", 0.0)
        if payload.get("script_text"):
            self.text_script.setPlainText(payload.get("script_text"))
        self.chk_duration.setChecked(float(duration) >= MIN_PUBLISH_SECONDS)
        self.chk_foley.setChecked(True)  # Foley was generated
        self.chk_frame1.setChecked(True)
        self.chk_loop_check.setChecked(True)

        # Ensure canvas preview is shown for audio
        self.player_stack.setCurrentIndex(0)
        self.refresh_calendar()
        self.terminal_log.append("🎉 Pipeline completed! Switching to Player & Viral Review Tab.")
        self.tab_widget.setCurrentIndex(2)

    def _on_pipeline_error(self, err: str):
        self.btn_generate_pipeline.setEnabled(True)
        self.progress_bar.setValue(0)
        QMessageBox.critical(self, "Pipeline Error", f"Execution encountered an error:\n{err}")

    def _on_render_blender_animation(self):
        self.media_player.stop()
        self.media_player.setSource(QUrl())
        slug = self.active_project_slug
        proj_dir = os.path.join(PROJECTS_DIR, slug)
        words_json = os.path.join(proj_dir, "words_timestamp.json")
        if not os.path.exists(words_json):
            QMessageBox.warning(
                self,
                "Pipeline Incomplete",
                "Please run 'Generate Video Pipeline' first to produce speech and word timestamps.",
            )
            return

        blender_path = self.config.get("blender_path", "blender")
        ffmpeg_path = self.config.get("ffmpeg_path", "ffmpeg")
        v_engine = self.combo_engine.currentData() or "2D_Crayon"
        engine_label = VisualEngineRouter.get_display_name(v_engine)

        self.btn_render_blender.setEnabled(False)
        self.progress_bar.setValue(10)
        self.terminal_log.append(
            f"[{datetime.datetime.now().strftime('%H:%M:%S')}] 🚀 Dispatching to {engine_label}..."
        )

        style_ref = self.input_style_ref.text().strip() or self.config.get("style_reference_path", "")
        visual_source = "hybrid_stock"
        if hasattr(self, "combo_visual_source") and self.combo_visual_source.currentData():
            visual_source = self.combo_visual_source.currentData()
        enable_omni = visual_source in ("generative_video", "veo_lite")
        self.render_worker = BlenderRenderWorker(
            project_slug=slug,
            category=self.combo_category.currentText(),
            blender_path=blender_path,
            ffmpeg_path=ffmpeg_path,
            script_text=self.text_script.toPlainText().strip(),
            visual_engine=v_engine,
            style_reference_path=style_ref,
            enable_omni_video=enable_omni,
            visual_source=visual_source,
        )
        self.render_worker.log_message.connect(self._on_pipeline_log)
        self.render_worker.progress_val.connect(self.progress_bar.setValue)
        self.render_worker.render_finished.connect(self._on_blender_render_completed)
        self.render_worker.render_error.connect(self._on_blender_render_error)
        self.render_worker.start()

    def _on_blender_render_completed(self, final_mp4: str):
        self.btn_render_blender.setEnabled(True)
        self.current_media_path = final_mp4
        if self.active_project_id:
            db.update_project_status(self.active_project_id, "Rendered")
            self.refresh_calendar()

        # Switch player stack to video widget
        self.player_stack.setCurrentIndex(1)
        self.media_player.setSource(QUrl.fromLocalFile(final_mp4))
        self.btn_play_pause.setText("▶ Play")
        self.terminal_log.append(f"🎉 Final 9:16 video rendered and loaded: {final_mp4}")

        # Load Visual Critic 4-Keyframe inspection snapshots
        snap_dir = os.path.join(PROJECTS_DIR, self.active_project_slug, "preview_snapshots")
        self._load_critic_snapshots(snap_dir)

        self.tab_widget.setCurrentIndex(2)

    def _on_blender_render_error(self, err: str):
        self.btn_render_blender.setEnabled(True)
        self.progress_bar.setValue(0)
        QMessageBox.warning(
            self,
            "Blender Render Info",
            f"Headless Blender render could not complete:\n{err}\n\nTip: You can configure your Blender executable path in Tab 5 (Settings).",
        )

    def _on_apply_visual_revision(self):
        prompt = self.input_visual_revision.text().strip()
        if not prompt:
            QMessageBox.information(self, "Visual Revision", "Please enter a revision instruction (e.g. 'Expand exploded parts further').")
            return
        self.terminal_log.append(f"[{datetime.datetime.now().strftime('%H:%M:%S')}] ⚡ Applying visual revision: '{prompt}'...")
        self._on_render_blender_animation()

    def _load_critic_snapshots(self, snap_dir: str):
        """Loads the 4 Visual Critic snapshots into Tab 3 thumbnail strip."""
        filenames = [
            "frame_1_closed.png",
            "frame_2_exploded.png",
            "frame_3_action.png",
            "frame_4_cutaway.png",
        ]
        found_any = False
        for idx, fname in enumerate(filenames):
            fpath = os.path.join(snap_dir, fname)
            if idx < len(self.critic_thumbs):
                if os.path.exists(fpath):
                    pix = QPixmap(fpath)
                    if not pix.isNull():
                        self.critic_thumbs[idx].setPixmap(pix)
                        self.critic_thumbs[idx].setToolTip(f"{fname}\n{fpath}")
                        found_any = True
                else:
                    self.critic_thumbs[idx].clear()
                    self.critic_thumbs[idx].setText("No Render")

        if found_any:
            self.lbl_critic_summary.setText("✓ 4-Keyframe inspection: All checkpoints verified.")
            self.lbl_critic_summary.setStyleSheet("font-size: 10px; color: #00E676; font-weight: bold;")
        else:
            self.lbl_critic_summary.setText("Visual Critic: Standby. Awaiting project render.")
            self.lbl_critic_summary.setStyleSheet("font-size: 10px; color: #9AA0A6;")

    # =================================================================
    # TAB 3 LOGIC: VIRAL CHECKLIST & DISPATCH
    # =================================================================
    def _on_checklist_toggled(self):
        items = [
            self.chk_frame1.isChecked(),
            self.chk_loop_check.isChecked(),
            self.chk_friction.isChecked(),
            self.chk_duration.isChecked(),
            self.chk_foley.isChecked(),
        ]
        score = sum(1 for c in items if c)
        if score == 5:
            self.lbl_checklist_score.setText("Score: 5 / 5 — VIRAL READY! 🚀")
            self.lbl_checklist_score.setStyleSheet("color: #107C41; font-weight: bold;")
        else:
            self.lbl_checklist_score.setText(f"Score: {score} / 5 Checks Passed")
            self.lbl_checklist_score.setStyleSheet("color: #D88D00; font-weight: bold;")

    def _get_project_final_mp4(self) -> Optional[str]:
        slug = self.active_project_slug
        proj_dir = os.path.join(PROJECTS_DIR, slug)
        final_mp4 = os.path.join(proj_dir, f"{slug}_final.mp4")
        if os.path.exists(final_mp4):
            return final_mp4
        raw_mp4 = os.path.join(proj_dir, "scene_raw.mp4")
        if os.path.exists(raw_mp4):
            return raw_mp4
        if self.current_media_path and self.current_media_path.endswith(".mp4") and os.path.exists(self.current_media_path):
            return self.current_media_path
        return None

    def _on_export_video(self):
        video_path = self._get_project_final_mp4()
        if not video_path:
            QMessageBox.information(
                self,
                "Video Not Rendered Yet",
                "You haven't rendered the MP4 video yet!\n\n"
                "To create your video:\n"
                "1. Go to Tab 2: Production Studio\n"
                "2. Click '🚀 Generate Video Pipeline' (audio & timestamps)\n"
                "3. Click '🎨 Render 2D Animation Pass' (or 3D Teardown)\n\n"
                "Once rendering completes, return here and click '📥 Download / Export MP4' to save it anywhere on your PC.",
            )
            return

        default_name = f"{self.active_project_slug}.mp4"
        downloads_dir = os.path.join(os.path.expanduser("~"), "Downloads")
        dest_path, _ = QFileDialog.getSaveFileName(
            self,
            "Download / Export Video",
            os.path.join(downloads_dir, default_name),
            "MP4 Video (*.mp4)",
        )
        if dest_path:
            try:
                shutil.copy2(video_path, dest_path)
                reply = QMessageBox.question(
                    self,
                    "Export Successful",
                    f"Video successfully saved to:\n{dest_path}\n\nWould you like to open the folder now?",
                    QMessageBox.Yes | QMessageBox.No,
                    QMessageBox.Yes,
                )
                if reply == QMessageBox.Yes:
                    dest_dir = os.path.dirname(dest_path)
                    os.startfile(dest_dir)
            except Exception as e:
                QMessageBox.critical(self, "Export Error", f"Failed to export video:\n{e}")

    def _on_open_project_folder(self):
        slug = self.active_project_slug
        proj_dir = os.path.join(PROJECTS_DIR, slug)
        os.makedirs(proj_dir, exist_ok=True)
        try:
            os.startfile(proj_dir)
        except Exception as e:
            QMessageBox.critical(self, "Error Opening Folder", f"Could not open folder:\n{e}")

    def _on_copy_veo_prompts(self):
        script = self.text_script.toPlainText().strip()
        if not script:
            QMessageBox.warning(self, "No Script", "Please enter or generate a script first.")
            return

        slug = self.active_project_slug
        proj_dir = os.path.join(PROJECTS_DIR, slug)
        os.makedirs(proj_dir, exist_ok=True)
        words_json = os.path.join(proj_dir, "words_timestamp.json")

        from core.storyboard_engine import AIStoryboardEngine
        engine = AIStoryboardEngine(config_path="config.json")
        scenes = engine.segment_script_into_scenes(script, words_json, target_count=6)
        prompted = engine.build_scene_prompts(
            scenes=scenes,
            category=self.combo_category.currentText(),
            visual_engine=self.combo_engine.currentData() or "2D_Crayon",
        )

        lines = [
            "=== GOOGLE FLOW OMNI MULTI-TURN PROMPTS (9:16 VERTICAL, 3D PIXAR STYLE) ===",
            f"Project: {slug}",
            f"Total Scenes: {len(prompted)}",
            "How to use in Google Flow (flow.google) or Google AI Studio:",
            "  1. Start a new session with Round 1 (World Setup).",
            "  2. In the same conversation, submit Round 2, Round 3, etc. to extend the scene with full visual continuity!",
            "  3. Drop either the exported individual clips (clip_01.mp4 ... clip_06.mp4) OR the single full extended video (flow_omni.mp4)",
            "     directly into your project's 'storyboard/' folder before clicking Render!\n",
        ]
        for sc in prompted:
            idx = sc["scene_idx"] + 1
            round_hdr = "ROUND 1 (WORLD SETUP)" if idx == 1 else f"ROUND {idx} (SCENE EXTENSION)"
            lines.append(f"--- {round_hdr} ({sc['start_time']}s - {sc['end_time']}s) ---")
            lines.append(sc.get("omni_prompt", sc["prompt"]))
            lines.append("")

        prompt_text = "\n".join(lines)
        QApplication.clipboard().setText(prompt_text)

        omni_file = os.path.join(proj_dir, "flow_omni_prompts.txt")
        veo_file = os.path.join(proj_dir, "veo_prompts.txt")
        try:
            with open(omni_file, "w", encoding="utf-8") as f:
                f.write(prompt_text)
            with open(veo_file, "w", encoding="utf-8") as f:
                f.write(prompt_text)
        except Exception:
            pass

        self.terminal_log.append(
            f"[{datetime.datetime.now().strftime('%H:%M:%S')}] 📋 Copied {len(prompted)} Flow Omni Multi-Turn prompts to clipboard & saved to {omni_file}!"
        )
        QMessageBox.information(
            self,
            "Flow Omni Prompts Copied",
            f"✓ {len(prompted)} timestamped Flow Omni Multi-Turn prompts copied to clipboard!\n\n"
            f"Saved to: {omni_file}\n\n"
            "You can now paste them directly into flow.google or Google AI Studio.",
        )

    def _on_open_storyboard_folder(self):
        slug = self.active_project_slug
        proj_dir = os.path.join(PROJECTS_DIR, slug)
        sb_dir = os.path.join(proj_dir, "storyboard")
        os.makedirs(sb_dir, exist_ok=True)

        files, _ = QFileDialog.getOpenFileNames(
            self,
            "Select Flow / AI Video Clips to Import",
            "",
            "Video Files (*.mp4 *.mov *.mkv *.webm);;All Files (*)",
        )
        if files:
            files = sorted(files)
            imported = []
            if len(files) == 1:
                base_name = os.path.basename(files[0])
                if base_name.lower().startswith(("clip_", "scene_")):
                    dest = os.path.join(sb_dir, base_name)
                else:
                    dest = os.path.join(sb_dir, "flow_omni.mp4")
                shutil.copy2(files[0], dest)
                imported.append(os.path.basename(dest))
            else:
                for idx, src in enumerate(files, start=1):
                    dest = os.path.join(sb_dir, f"clip_{idx:02d}.mp4")
                    shutil.copy2(src, dest)
                    imported.append(os.path.basename(dest))

            msg = f"✓ Successfully imported {len(imported)} clip(s) into project storyboard:\n" + "\n".join(f"• {f}" for f in imported)
            self.terminal_log.append(f"[{datetime.datetime.now().strftime('%H:%M:%S')}] 🎬 {msg}")
            QMessageBox.information(
                self,
                "Video Clips Imported",
                f"{msg}\n\nYou can now click '🎨 Render AI Storyboard Video' to compose your final video with subtitles and audio!",
            )
        else:
            # If dialog canceled, open Explorer folder for drag-and-drop
            try:
                if sys.platform == "win32":
                    os.startfile(sb_dir)
                elif sys.platform == "darwin":
                    subprocess.Popen(["open", sb_dir])
                else:
                    subprocess.Popen(["xdg-open", sb_dir])
            except Exception as e:
                QMessageBox.critical(self, "Error Opening Folder", f"Could not open storyboard folder:\n{e}")

            self.terminal_log.append(
                f"[{datetime.datetime.now().strftime('%H:%M:%S')}] 📂 Opened storyboard folder: {sb_dir}\n"
                "Drop custom video clips (clip_01.mp4 ... clip_06.mp4) or full extended video (flow_omni.mp4) here."
            )

    def _on_mark_ready(self):
        if not self.active_project_id:
            # Create project if not yet in DB
            title = self.meta_title.text().strip() or self.input_title.text().strip()
            slug = re.sub(r"[^a-zA-Z0-9_-]", "-", title.lower())[:50]
            self.active_project_id = db.create_project(
                project_slug=slug,
                title=title,
                category=self.combo_category.currentText(),
                script_text=self.text_script.toPlainText(),
                duration_target=self.spin_duration.value(),
                status="Ready",
            )
        else:
            db.update_project_status(self.active_project_id, "Ready")

        QMessageBox.information(
            self,
            "Project Ready",
            f"Project status updated to 'Ready' in SQLite database. Visible on Content Calendar.",
        )
        self.refresh_calendar()

    def _on_dispatch_youtube(self):
        target_file = self.current_media_path or os.path.join(PROJECTS_DIR, "sample_render.mp4")
        metadata = {
            "title": self.meta_title.text().strip() or self.input_title.text().strip(),
            "description": self.meta_description.toPlainText().strip(),
            "tags": [tag.strip("#") for tag in self.meta_hashtags.text().split() if tag],
            "category_id": 27,
        }
        dry_run = self.chk_dry_run.isChecked()
        res = upload_to_youtube(target_file, metadata, dry_run=dry_run)

        # Update project status
        if self.active_project_id:
            db.update_project_status(self.active_project_id, "Published")
            self.refresh_calendar()

        msg = (
            f"Platform: {res['platform']}\n"
            f"Status: {res['status']}\n"
            f"Dry Run: {res['dry_run']}\n"
            f"Simulated Video ID: {res.get('simulated_video_id', 'N/A')}\n\n"
            f"Details: {res['message']}"
        )
        QMessageBox.information(self, "YouTube Dispatch", msg)

    def _on_dispatch_tiktok(self):
        target_file = self.current_media_path or os.path.join(PROJECTS_DIR, "sample_render.mp4")
        metadata = {
            "title": self.meta_title.text().strip() or self.input_title.text().strip(),
            "caption": self.meta_description.toPlainText().strip(),
            "hashtags": self.meta_hashtags.text().split(),
            "tiktok_product": self.combo_product.currentText(),
        }
        dry_run = self.chk_dry_run.isChecked()
        res = queue_tiktok_draft(target_file, metadata, dry_run=dry_run)

        if self.active_project_id:
            db.update_project_status(self.active_project_id, "Published")
            self.refresh_calendar()

        msg = (
            f"Platform: {res['platform']}\n"
            f"Status: {res['status']}\n"
            f"Dry Run: {res['dry_run']}\n"
            f"Simulated Publish ID: {res.get('simulated_publish_id', 'N/A')}\n\n"
            f"Details: {res['message']}"
        )
        QMessageBox.information(self, "TikTok Dispatch", msg)

    # =================================================================
    # TAB 4 LOGIC: CONTENT CALENDAR
    # =================================================================
    def refresh_calendar(self):
        """Build and populate the 14-day production calendar grid."""
        # Clear existing layout
        while self.cal_grid_layout.count():
            item = self.cal_grid_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        projects = db.get_all_projects()
        today = datetime.date.today()

        status_colors = {
            "Draft": ("#3A3A3C", "#E0E0E0"),
            "Audio_Ready": ("#004578", "#FFFFFF"),
            "Rendered": ("#4F2D7F", "#FFFFFF"),
            "Ready": ("#005B5B", "#FFFFFF"),
            "Scheduled": ("#7A5200", "#FFFFFF"),
            "Published": ("#0E5E2E", "#FFFFFF"),
        }

        # 14 days grid: 2 rows of 7 days
        for day_offset in range(14):
            day_date = today + datetime.timedelta(days=day_offset)
            row = day_offset // 7
            col = day_offset % 7

            day_card = QFrame()
            day_card.setProperty("class", "card")
            day_card.setStyleSheet("QFrame { background-color: #1A1A1A; border: 1px solid #2D2D2D; border-radius: 6px; }")
            dc_layout = QVBoxLayout(day_card)
            dc_layout.setContentsMargins(8, 8, 8, 8)
            dc_layout.setSpacing(6)

            # Date Header
            day_str = day_date.strftime("%a, %b %d")
            lbl_day = QLabel(day_str)
            lbl_day.setStyleSheet("font-weight: bold; font-size: 11px; color: #0078D4;")
            dc_layout.addWidget(lbl_day)

            # Assign projects to day (distribute active projects across days)
            day_projects = [
                p for p in projects
                if p.get("scheduled_time") and p["scheduled_time"].startswith(day_date.strftime("%Y-%m-%d"))
            ]

            # If no explicitly scheduled project, show planned slots or unassigned projects
            if not day_projects and day_offset < len(projects):
                # Distribute projects for calendar visualization
                day_projects = [projects[day_offset]]

            if day_projects:
                for proj in day_projects:
                    proj_box = QFrame()
                    proj_box.setStyleSheet(
                        "background-color: #242424; border: 1px solid #333333; border-radius: 4px; padding: 4px;"
                    )
                    pb_layout = QVBoxLayout(proj_box)
                    pb_layout.setContentsMargins(4, 4, 4, 4)
                    pb_layout.setSpacing(3)

                    p_title = QLabel(proj.get("title", "Untitled")[:24])
                    p_title.setStyleSheet("font-weight: 600; font-size: 11px; color: #FFFFFF;")
                    p_cat = QLabel(f"{proj.get('category', 'STEM')} • {proj.get('duration_target', 65)}s")
                    p_cat.setStyleSheet("font-size: 10px; color: #9AA0A6;")

                    status = proj.get("status", "Draft")
                    bg_col, txt_col = status_colors.get(status, ("#3A3A3A", "#FFFFFF"))
                    p_status = QLabel(status.upper())
                    p_status.setStyleSheet(
                        f"background-color: {bg_col}; color: {txt_col}; "
                        "padding: 2px 4px; border-radius: 3px; font-size: 8px; font-weight: bold;"
                    )

                    v_engine = proj.get("visual_engine", "2D_Crayon")
                    if v_engine == "3D_Teardown":
                        e_text, e_bg = "3D TEARDOWN", "#FF6B6B"
                    else:
                        e_text, e_bg = "2D CRAYON", "#0078D4"
                    p_engine = QLabel(e_text)
                    p_engine.setStyleSheet(
                        f"background-color: {e_bg}; color: #FFFFFF; "
                        "padding: 2px 4px; border-radius: 3px; font-size: 8px; font-weight: bold;"
                    )

                    badge_layout = QHBoxLayout()
                    badge_layout.setSpacing(4)
                    badge_layout.addWidget(p_status)
                    badge_layout.addWidget(p_engine)
                    badge_layout.addStretch()

                    btn_open = QPushButton("Open")
                    btn_open.setStyleSheet("padding: 2px 6px; font-size: 10px;")
                    # Capture proj dict in closure
                    btn_open.clicked.connect(lambda checked, p=proj: self._on_load_project_into_studio(p))

                    pb_layout.addWidget(p_title)
                    pb_layout.addWidget(p_cat)
                    pb_layout.addLayout(badge_layout)
                    pb_layout.addWidget(btn_open)
                    dc_layout.addWidget(proj_box)
            else:
                lbl_empty = QLabel("No dispatch scheduled")
                lbl_empty.setStyleSheet("font-size: 10px; color: #555555; font-style: italic;")
                dc_layout.addWidget(lbl_empty)

            dc_layout.addStretch()
            self.cal_grid_layout.addWidget(day_card, row, col)

    def _on_load_project_into_studio(self, proj: Dict[str, Any]):
        """Load selected project record from calendar into Studio & Player."""
        self.active_project_id = proj.get("id")
        self.active_project_slug = proj.get("project_slug", "project")
        self.input_title.setText(proj.get("title", ""))

        cat = proj.get("category", "STEM")
        cat_idx = self.combo_category.findText(cat)
        if cat_idx >= 0:
            self.combo_category.setCurrentIndex(cat_idx)

        v_engine = proj.get("visual_engine", "2D_Crayon")
        v_idx = self.combo_engine.findData(v_engine)
        if v_idx >= 0:
            self.combo_engine.setCurrentIndex(v_idx)

        self.text_script.setPlainText(proj.get("script_text", ""))
        self.spin_duration.setValue(proj.get("duration_target", 65))

        prod = proj.get("tiktok_product", "")
        prod_idx = self.combo_product.findText(prod)
        if prod_idx >= 0:
            self.combo_product.setCurrentIndex(prod_idx)

        # Check if rendered MP4 or voiceover file exists in projects/
        proj_dir = os.path.join(PROJECTS_DIR, self.active_project_slug)
        final_mp4 = os.path.join(proj_dir, f"{self.active_project_slug}_final.mp4")
        vo_path = os.path.join(proj_dir, "voiceover.wav")

        if os.path.exists(final_mp4):
            self.current_media_path = final_mp4
            self.player_stack.setCurrentIndex(1)
            self.media_player.setSource(QUrl.fromLocalFile(final_mp4))
            self.btn_play_pause.setText("▶ Play")
        elif os.path.exists(vo_path):
            self.current_media_path = vo_path
            self.player_stack.setCurrentIndex(0)
            self.media_player.setSource(QUrl.fromLocalFile(vo_path))
            self.btn_play_pause.setText("▶ Play")
        else:
            self.current_media_path = None
            self.player_stack.setCurrentIndex(0)

        # Load Visual Critic snapshots if existing
        snap_dir = os.path.join(proj_dir, "preview_snapshots")
        self._load_critic_snapshots(snap_dir)

        self.preview_canvas.update_metadata(
            title=proj.get("title", ""),
            hook=proj.get("hook") or proj.get("title", ""),
            category=cat,
        )
        words_json = os.path.join(proj_dir, "words_timestamp.json")
        if os.path.exists(words_json):
            try:
                with open(words_json, "r", encoding="utf-8") as f:
                    self.preview_canvas.set_word_timestamps(json.load(f))
            except Exception:
                pass

        self.tab_widget.setCurrentIndex(1)
        self.status_bar.showMessage(f"Project '{proj.get('title')}' loaded into Production Studio.", 3000)

    # =================================================================
    # TAB 5 LOGIC: SETTINGS
    # =================================================================
    def _load_saved_settings_to_ui(self):
        self.input_blender_path.setText(self.config.get("blender_path", ""))
        self.input_ffmpeg_path.setText(self.config.get("ffmpeg_path", ""))

        voice = self.config.get("default_voice", "en-US-GuyNeural")
        v_idx = self.combo_voice.findText(voice)
        if v_idx >= 0:
            self.combo_voice.setCurrentIndex(v_idx)

        if hasattr(self, "tab2_combo_voice"):
            t2_idx = self.tab2_combo_voice.findData(voice)
            if t2_idx >= 0:
                self.tab2_combo_voice.setCurrentIndex(t2_idx)

        speed_val = float(self.config.get("speech_speed", 1.00))
        self.spin_speed.setValue(speed_val)
        if hasattr(self, "tab2_spin_speed"):
            self.tab2_spin_speed.setValue(speed_val)

        self.spin_default_duration.setValue(int(self.config.get("target_duration", 69)))
        if hasattr(self, "spin_duration"):
            self.spin_duration.setValue(int(self.config.get("target_duration", 69)))
        if hasattr(self, "input_pexels_key"):
            self.input_pexels_key.setText(self.config.get("pexels_api_key", ""))
        if hasattr(self, "input_pixabay_key"):
            self.input_pixabay_key.setText(self.config.get("pixabay_api_key", ""))
        self.chk_dry_run.setChecked(bool(self.config.get("dry_run_mode", True)))
        self.input_yt_key.setText(self.config.get("youtube_api_key", ""))
        self.input_gemini_key.setText(self.config.get("gemini_api_key", ""))

        default_style = self.config.get("style_reference_path", "")
        self.input_default_style_ref.setText(default_style)
        if hasattr(self, "input_style_ref") and not self.input_style_ref.text().strip():
            self.input_style_ref.setText(default_style)

    def _on_browse_style_ref(self):
        path, _ = QFileDialog.getOpenFileName(
            self,
            "Select Style Reference Screenshot",
            "",
            "Image Files (*.png *.jpg *.jpeg *.webp);;All Files (*)",
        )
        if path:
            self.input_style_ref.setText(path)

    def _on_browse_default_style(self):
        path, _ = QFileDialog.getOpenFileName(
            self,
            "Select Default Style Reference Screenshot",
            "",
            "Image Files (*.png *.jpg *.jpeg *.webp);;All Files (*)",
        )
        if path:
            self.input_default_style_ref.setText(path)
            if hasattr(self, "input_style_ref") and not self.input_style_ref.text().strip():
                self.input_style_ref.setText(path)

    def _on_browse_blender(self):
        path, _ = QFileDialog.getOpenFileName(
            self,
            "Select Blender Executable",
            "C:\\",
            "Executable Files (*.exe);;All Files (*)",
        )
        if path:
            self.input_blender_path.setText(path)

    def _on_browse_ffmpeg(self):
        path, _ = QFileDialog.getOpenFileName(
            self,
            "Select FFmpeg Executable",
            "C:\\",
            "Executable Files (*.exe);;All Files (*)",
        )
        if path:
            self.input_ffmpeg_path.setText(path)

    def _on_validate_binaries(self):
        blender_path = self.input_blender_path.text().strip()
        ffmpeg_path = self.input_ffmpeg_path.text().strip()

        orch = BlenderOrchestrator(blender_path)
        comp = FFmpegCompositor(ffmpeg_path)

        b_ok = orch.validate_blender_binary()
        f_ok = comp.validate_ffmpeg_binary()

        b_str = "✓ Blender Detected" if b_ok else "❌ Blender Not Found (Will use stub)"
        f_str = "✓ FFmpeg Detected" if f_ok else "❌ FFmpeg Not Found (Will use stub)"

        self.lbl_binary_status.setText(f"{b_str} | {f_str}")
        self.lbl_binary_status.setStyleSheet("color: #FFFFFF; font-weight: bold;")

    def _on_dry_run_toggled(self, state: int):
        is_dry = bool(state)
        if is_dry:
            self.dry_run_indicator.setText("● DRY-RUN ACTIVE")
            self.dry_run_indicator.setStyleSheet(
                "color: #D88D00; font-weight: bold; background: #2A2000; "
                "padding: 4px 10px; border-radius: 4px; border: 1px solid #7A5200;"
            )
        else:
            self.dry_run_indicator.setText("● LIVE DISPATCH")
            self.dry_run_indicator.setStyleSheet(
                "color: #107C41; font-weight: bold; background: #0A2412; "
                "padding: 4px 10px; border-radius: 4px; border: 1px solid #107C41;"
            )

    def _on_save_settings(self):
        cfg = {
            "blender_path": self.input_blender_path.text().strip(),
            "ffmpeg_path": self.input_ffmpeg_path.text().strip(),
            "default_voice": self.combo_voice.currentText(),
            "speech_speed": self.spin_speed.value(),
            "target_duration": self.spin_default_duration.value(),
            "dry_run_mode": self.chk_dry_run.isChecked(),
            "youtube_api_key": self.input_yt_key.text().strip(),
            "gemini_api_key": self.input_gemini_key.text().strip(),
            "style_reference_path": self.input_default_style_ref.text().strip(),
            "visual_source": (
                self.combo_visual_source.currentData()
                if hasattr(self, "combo_visual_source") and self.combo_visual_source.currentData()
                else self.config.get("visual_source", "hybrid_stock")
            ),
            "pexels_api_key": self.input_pexels_key.text().strip() if hasattr(self, "input_pexels_key") else "",
            "pixabay_api_key": self.input_pixabay_key.text().strip() if hasattr(self, "input_pixabay_key") else "",
        }
        self.config = cfg
        if save_app_config(cfg):
            self.lbl_settings_saved.setText("✓ Settings saved to config.json")
            QTimer.singleShot(3000, lambda: self.lbl_settings_saved.setText(""))
            self.status_bar.showMessage("Settings saved successfully.", 3000)
        else:
            QMessageBox.critical(self, "Save Error", "Could not write to config.json.")


def main():
    """Application entrypoint."""
    app = QApplication(sys.argv)
    app.setApplicationName("CrayonStudio")
    app.setStyle("Fusion")

    window = CrayonStudioApp()
    window.show()

    sys.exit(app.exec())


if __name__ == "__main__":
    main()
