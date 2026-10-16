import os
import re
import sys
import json
import shutil
from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QHBoxLayout, QVBoxLayout,
    QLabel, QPushButton, QStackedWidget, QFrame, QMessageBox, QFileDialog
)
from PySide6.QtCore import Qt, QTimer

from database.db import (
    init_db, upsert_project, get_all_projects, get_project_by_id, update_project_status
)
from core.storyboard_engine import AIStoryboardEngine
from core.uploader import upload_to_youtube, queue_tiktok_draft
from core.usage_tracker import usage_tracker

from ui.theme import STUDIO_DARK_QSS
from ui.glass_widgets import LiveUsagePill, GlassCard
from ui.studio_view import StudioView
from ui.research_view import ResearchView
from ui.calendar_view import CalendarView
from ui.settings_view import SettingsView
from ui.player_dock import PlayerInspectorDock
from ui.workers import (
    ScraperWorker, ScriptAIWorker, StoryboardChoreographyWorker,
    AudioPipelineWorker, StoryboardRenderWorker, SingleSceneWorker
)

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
CONFIG_PATH = os.path.join(BASE_DIR, "config.json")
PROJECTS_ROOT = os.path.join(BASE_DIR, "projects")


def slugify_topic(title: str) -> str:
    slug = re.sub(r"[^a-zA-Z0-9]+", "-", (title or "untitled-project").lower()).strip("-")
    return slug[:64] or "untitled-project"


def load_app_config() -> dict:
    if os.path.exists(CONFIG_PATH):
        try:
            with open(CONFIG_PATH, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    return {
        "gemini_api_key": "",
        "text_model": "gemini-3.8-flash",
        "image_model": "gemini-nano-banana-2.1",
        "omni_model": "gemini-omni-1.1-flash",
        "omni_resolution": "720p",
        "default_render_mode": "smart_hybrid",
        "tts_voice": "en-US-GuyNeural",
        "tts_speed": 1.05,
        "ffmpeg_path": "ffmpeg",
    }


def save_app_config(cfg: dict):
    with open(CONFIG_PATH, "w", encoding="utf-8") as f:
        json.dump(cfg, f, indent=2)


class CrayonStudioWindow(QMainWindow):
    """
    Apple-Caliber Guided AI Short-Form Video Studio powered by Gemini Interactions API
    (`gemini-3.8-flash`, `gemini-nano-banana-2.1`, `gemini-omni-1.1-flash`) with
    Live API Health & Token/Cost Telemetry.
    """
    def __init__(self):
        super().__init__()
        init_db()
        os.makedirs(PROJECTS_ROOT, exist_ok=True)
        self.config = load_app_config()

        self.current_project: dict = {
            "id": None,
            "project_slug": "how-sand-turns-to-glass",
            "title": "How Sand Turns to Glass",
            "hook": "",
            "category": "STEM",
            "visual_engine": "3D_Pixar",
            "render_mode": self.config.get("default_render_mode", "smart_hybrid"),
            "style_reference_path": "",
            "script_text": "",
            "tiktok_product": "",
            "duration_target": 65,
            "status": "Draft",
            "scheduled_time": None,
            "meta_title": "",
            "meta_description": "",
            "meta_hashtags": "#shorts #engineering #howthingswork #science #fyp",
            "storyboard_json": "[]",
        }
        self.competitor_insights: dict = {"confusion_points": "", "complaints": "", "content_gaps": ""}
        self.words_timestamps: list[dict] = []
        self._active_workers: list = []
        self._sync_guard = False

        # Debounced background auto-save timer (450ms) to eliminate keystroke hitching
        self._autosave_timer = QTimer(self)
        self._autosave_timer.setSingleShot(True)
        self._autosave_timer.setInterval(450)
        self._autosave_timer.timeout.connect(self._on_debounced_save)

        self.setWindowTitle("CrayonStudio — Guided Short-Form Video Studio")
        self.resize(1440, 880)
        self.setMinimumSize(1100, 700)
        self.setStyleSheet(STUDIO_DARK_QSS)

        self._build_layout()
        self._load_initial_project()
        self._refresh_usage_and_costs()

    def _build_layout(self):
        root = QWidget()
        self.setCentralWidget(root)
        main_h = QHBoxLayout(root)
        main_h.setContentsMargins(0, 0, 0, 0)
        main_h.setSpacing(0)

        # 1. Left Frosted Sidebar Navigation Rail
        nav_rail = QFrame()
        nav_rail.setObjectName("navRail")
        nav_rail.setFixedWidth(226)
        nav_layout = QVBoxLayout(nav_rail)
        nav_layout.setContentsMargins(14, 20, 14, 18)
        nav_layout.setSpacing(6)

        brand_title = QLabel("CrayonStudio")
        brand_title.setStyleSheet("color: #F5F5F7; font-weight: 800; font-size: 19px;")
        nav_layout.addWidget(brand_title)

        brand_sub = QLabel("Guided Short-Form Video Maker")
        brand_sub.setStyleSheet("color: #98989D; font-weight: 500; font-size: 11px;")
        nav_layout.addWidget(brand_sub)
        nav_layout.addSpacing(16)

        self.nav_buttons: list[QPushButton] = []
        nav_items = [
            ("🎬  Create Video", 0),
            ("🔍  Topic Finder", 1),
            ("📅  Saved Videos", 2),
            ("⚙️  Settings", 3),
        ]
        for label, idx in nav_items:
            btn = QPushButton(label)
            btn.setProperty("class", "navBtn")
            btn.setCheckable(True)
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            btn.clicked.connect(lambda _checked=False, i=idx: self.switch_nav(i))
            nav_layout.addWidget(btn)
            self.nav_buttons.append(btn)

        nav_layout.addStretch()

        # Quick Help / New Video Button in Sidebar
        btn_quick_new = QPushButton("➕ Start Brand New Video")
        btn_quick_new.setProperty("class", "chip")
        btn_quick_new.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_quick_new.clicked.connect(self.create_blank_project)
        nav_layout.addWidget(btn_quick_new)
        nav_layout.addSpacing(6)

        model_card = GlassCard(radius=12, elevated=False)
        m_layout = QVBoxLayout(model_card)
        m_layout.setContentsMargins(12, 10, 12, 10)
        m_layout.setSpacing(3)
        lbl_m_hdr = QLabel("Active Studio Engines")
        lbl_m_hdr.setStyleSheet("color: #F5F5F7; font-weight: 700; font-size: 11px;")
        m_layout.addWidget(lbl_m_hdr)
        self.lbl_model_stack = QLabel(
            "• Writer: Gemini 3.8 Flash\n"
            "• Art: Nano Banana 2.1\n"
            "• Video: Omni 1.1 (1080p HD)"
        )
        self.lbl_model_stack.setStyleSheet("color: #98989D; font-size: 11px;")
        m_layout.addWidget(self.lbl_model_stack)
        nav_layout.addWidget(model_card)

        main_h.addWidget(nav_rail)

        # 2. Center Column: Top Glass Header Bar + Workspace Stack
        center_col = QWidget()
        center_v = QVBoxLayout(center_col)
        center_v.setContentsMargins(0, 0, 0, 0)
        center_v.setSpacing(0)

        top_bar = QFrame()
        top_bar.setObjectName("topBar")
        top_bar.setFixedHeight(54)
        tb_layout = QHBoxLayout(top_bar)
        tb_layout.setContentsMargins(20, 8, 20, 8)
        tb_layout.setSpacing(12)

        self.lbl_active_project = QLabel("Current Video: How Sand Turns to Glass")
        self.lbl_active_project.setStyleSheet("color: #F5F5F7; font-weight: 700; font-size: 14px;")
        tb_layout.addWidget(self.lbl_active_project)
        tb_layout.addStretch()

        self.usage_pill = LiveUsagePill(usage_tracker)
        tb_layout.addWidget(self.usage_pill)

        center_v.addWidget(top_bar)

        self.workspace_stack = QStackedWidget()
        self.studio_view = StudioView()
        self.research_view = ResearchView()
        self.calendar_view = CalendarView()
        self.settings_view = SettingsView(self.config)

        self.workspace_stack.addWidget(self.studio_view)
        self.workspace_stack.addWidget(self.research_view)
        self.workspace_stack.addWidget(self.calendar_view)
        self.workspace_stack.addWidget(self.settings_view)
        center_v.addWidget(self.workspace_stack, stretch=1)

        main_h.addWidget(center_col, stretch=1)

        # 3. Persistent Right 9:16 Phone Preview & Publish Dock
        self.player_dock = PlayerInspectorDock()
        main_h.addWidget(self.player_dock, 0)

        self._connect_signals()
        self.switch_nav(0)

    def _connect_signals(self):
        self.usage_pill.open_settings_requested.connect(lambda: self.switch_nav(3))
        self.studio_view.generate_script_requested.connect(self.on_generate_script)
        self.studio_view.revise_script_requested.connect(self.on_revise_script)
        self.studio_view.save_project_requested.connect(self._on_project_settings_changed)
        self.studio_view.state_changed.connect(self._on_project_settings_changed)
        self.studio_view.run_audio_requested.connect(self.on_run_audio)
        self.studio_view.run_render_requested.connect(self.on_run_render)
        self.studio_view.open_research_requested.connect(lambda: self.switch_nav(1))

        sb = self.studio_view.storyboard_inspector
        sb.auto_segment_requested.connect(self.auto_segment_storyboard)
        sb.copy_prompts_requested.connect(self.on_copy_omni_prompts)
        sb.import_clips_requested.connect(self.on_import_external_clips)
        sb.regenerate_scene_requested.connect(self.on_regenerate_single_scene)
        sb.scenes_updated.connect(self._on_scenes_edited)
        sb.clear_scenes_requested.connect(self.on_clear_storyboard_scenes)

        self.research_view.scrape_requested.connect(self.on_scrape_competitors)
        self.research_view.send_to_studio_requested.connect(self.on_research_concept_selected)

        self.calendar_view.project_selected.connect(self.load_project_dict_into_ui)
        self.calendar_view.new_project_requested.connect(self.create_blank_project)
        self.calendar_view.schedule_date_requested.connect(self.on_schedule_project)

        self.settings_view.save_settings_requested.connect(self.on_save_settings)

        self.player_dock.visual_revision_requested.connect(self.on_visual_revision_requested)
        self.player_dock.autofill_metadata_requested.connect(self.on_autofill_metadata)
        self.player_dock.save_calendar_requested.connect(self.on_save_to_calendar)
        self.player_dock.export_mp4_requested.connect(self.on_export_mp4)
        self.player_dock.dispatch_webhook_requested.connect(self.on_dispatch_webhook)
        self.player_dock.reset_preview_requested.connect(self.on_reset_preview)

    def _on_project_settings_changed(self):
        if self._sync_guard:
            return
        # Immediately update lightweight active title without heavy I/O
        title = self.studio_view.input_title.text().strip() or "Untitled Video"
        self.lbl_active_project.setText(f"Current Video: {title}")
        # Debounce heavy SQLite upsert, file writes, and canvas decode
        self._autosave_timer.start()

    def _on_debounced_save(self):
        if self._sync_guard:
            return
        self.sync_ui_to_project_state(persist_db=True)
        self._refresh_usage_and_costs()

    def _refresh_usage_and_costs(self):
        self.usage_pill.refresh_from_snapshot(usage_tracker.get_snapshot())
        self.studio_view.update_cost_estimates(
            usage_tracker,
            image_model=self.config.get("image_model", "gemini-nano-banana-2.1"),
            omni_res=self.config.get("omni_resolution", "720p"),
        )
        title = self.studio_view.input_title.text().strip() or "Untitled Video"
        self.lbl_active_project.setText(f"Current Video: {title}")

    def switch_nav(self, index: int):
        for i, btn in enumerate(self.nav_buttons):
            btn.setChecked(i == index)
            btn.setProperty("active", "true" if i == index else "false")
            btn.style().unpolish(btn)
            btn.style().polish(btn)
        if index == 2:
            self.sync_ui_to_project_state(persist_db=True)
            self.calendar_view.refresh_projects(get_all_projects())
        self.workspace_stack.setCurrentIndex(index)

    def get_project_dir(self) -> str:
        slug = self.current_project.get("project_slug") or slugify_topic(self.current_project.get("title", "project"))
        p_dir = os.path.join(PROJECTS_ROOT, slug)
        os.makedirs(p_dir, exist_ok=True)
        os.makedirs(os.path.join(p_dir, "storyboard"), exist_ok=True)
        return p_dir

    # =========================================================================
    # SINGLE SOURCE OF TRUTH: UI <-> PROJECT STATE & SQLITE SYNC
    # =========================================================================
    def sync_ui_to_project_state(self, persist_db: bool = True) -> dict:
        """
        Synchronizes every on-screen field from StudioView, StoryboardInspector,
        and PlayerInspectorDock into `self.current_project`, writes `storyboard.json`
        to disk, and persists to SQLite via `upsert_project()`.
        """
        if self._sync_guard:
            return self.current_project

        raw_title = self.studio_view.input_title.text().strip()
        title = raw_title
        slug = self.current_project.get("project_slug") or (slugify_topic(raw_title) if raw_title else "untitled-video")
        if not self.current_project.get("id"):
            slug = slugify_topic(raw_title) if raw_title else "untitled-video"

        category = self.studio_view.combo_category.currentText() or "STEM"
        visual_engine = self.studio_view.combo_style.currentData() or "3D_Pixar"
        render_mode = self.studio_view.combo_render_mode.currentData() or "smart_hybrid"
        style_ref = self.studio_view.style_reference_path
        target_dur = int(self.studio_view.spin_duration.value())
        product_bridge = self.studio_view.input_product.text().strip()
        script_text = self.studio_view.txt_script.toPlainText().strip()
        scenes = self.studio_view.storyboard_inspector.get_scenes()

        meta_title = self.player_dock.meta_title.text().strip() or raw_title
        meta_desc = self.player_dock.meta_description.toPlainText().strip()
        meta_tags = self.player_dock.meta_hashtags.text().strip()
        sb_json_str = json.dumps(scenes, ensure_ascii=False)

        self.current_project.update({
            "project_slug": slug,
            "title": title,
            "category": category,
            "visual_engine": visual_engine,
            "render_mode": render_mode,
            "style_reference_path": style_ref,
            "duration_target": target_dur,
            "tiktok_product": product_bridge,
            "script_text": script_text,
            "meta_title": meta_title,
            "meta_description": meta_desc,
            "meta_hashtags": meta_tags,
            "storyboard_json": sb_json_str,
        })

        if persist_db:
            proj_id = upsert_project(
                project_slug=slug,
                title=raw_title or "Untitled Short",
                hook=self.current_project.get("hook", ""),
                category=category,
                visual_engine=visual_engine,
                render_mode=render_mode,
                script_text=script_text,
                duration_target=target_dur,
                tiktok_product=product_bridge,
                style_reference_path=style_ref,
                meta_title=meta_title,
                meta_description=meta_desc,
                meta_hashtags=meta_tags,
                storyboard_json=sb_json_str,
                status=self.current_project.get("status", "Draft"),
                scheduled_time=self.current_project.get("scheduled_time"),
            )
            self.current_project["id"] = proj_id

        p_dir = self.get_project_dir()
        if script_text:
            with open(os.path.join(p_dir, "script.txt"), "w", encoding="utf-8") as f:
                f.write(script_text)
        if scenes:
            for sb_path in (
                os.path.join(p_dir, "storyboard.json"),
                os.path.join(p_dir, "storyboard", "storyboard.json"),
            ):
                with open(sb_path, "w", encoding="utf-8") as f:
                    json.dump(scenes, f, indent=2, ensure_ascii=False)

        self.player_dock.live_canvas.set_project_data(
            words=self.words_timestamps,
            scenes=scenes,
            project_dir=p_dir,
            visual_style=visual_engine,
            duration=float(target_dur),
        )
        self.lbl_active_project.setText(f"Current Video: {raw_title or 'Untitled Video'}")
        return self.current_project

    def _load_initial_project(self):
        projects = get_all_projects()
        if projects:
            self.load_project_dict_into_ui(projects[0])
        else:
            self.studio_view.input_title.setText(self.current_project["title"])
            self.sync_ui_to_project_state(persist_db=True)

    def load_project_dict_into_ui(self, proj: dict):
        self._sync_guard = True
        try:
            full_proj = get_project_by_id(int(proj["id"])) if proj.get("id") else proj
            self.current_project = dict(full_proj or proj)

            self.studio_view.input_title.setText(str(self.current_project.get("title", "")))
            cat = str(self.current_project.get("category", "STEM"))
            c_idx = self.studio_view.combo_category.findText(cat)
            if c_idx >= 0:
                self.studio_view.combo_category.setCurrentIndex(c_idx)

            style = str(self.current_project.get("visual_engine", "3D_Pixar"))
            self.studio_view._on_style_card_clicked(style)

            rmode = str(self.current_project.get("render_mode", "smart_hybrid"))
            self.studio_view._on_mode_card_clicked(rmode)

            self.studio_view.set_style_reference_path(str(self.current_project.get("style_reference_path", "")))
            self.studio_view.spin_duration.setValue(int(self.current_project.get("duration_target") or 65))
            self.studio_view.input_product.setText(str(self.current_project.get("tiktok_product", "")))
            script_txt = str(self.current_project.get("script_text", ""))
            self.studio_view.txt_script.setPlainText(script_txt)

            self.player_dock.meta_title.setText(str(self.current_project.get("meta_title") or self.current_project.get("title", "")))
            self.player_dock.meta_description.setPlainText(str(self.current_project.get("meta_description", "")))
            self.player_dock.meta_hashtags.setText(
                str(self.current_project.get("meta_hashtags") or "#shorts #engineering #explained #fyp")
            )

            p_dir = self.get_project_dir()
            words_file = os.path.join(p_dir, "words_timestamp.json")
            if os.path.exists(words_file):
                try:
                    with open(words_file, "r", encoding="utf-8") as f:
                        self.words_timestamps = json.load(f)
                except Exception:
                    self.words_timestamps = []
            else:
                self.words_timestamps = []

            scenes = []
            raw_sb = self.current_project.get("storyboard_json", "")
            if raw_sb:
                try:
                    scenes = json.loads(raw_sb)
                except Exception:
                    scenes = []
            if not scenes:
                for sb_disk in (
                    os.path.join(p_dir, "storyboard.json"),
                    os.path.join(p_dir, "storyboard", "storyboard.json"),
                ):
                    if os.path.exists(sb_disk):
                        try:
                            with open(sb_disk, "r", encoding="utf-8") as f:
                                scenes = json.load(f)
                            if scenes:
                                break
                        except Exception:
                            pass

            self.studio_view.storyboard_inspector.load_scenes(scenes, p_dir)
            self.player_dock.live_canvas.set_project_data(
                words=self.words_timestamps,
                scenes=scenes,
                project_dir=p_dir,
                visual_style=style,
                duration=float(self.current_project.get("duration_target") or 45),
            )

            slug = self.current_project.get("project_slug", "")
            video_candidate = os.path.join(p_dir, f"{slug}_final.mp4")
            if os.path.exists(video_candidate):
                self.player_dock.load_video(video_candidate)
                self.studio_view.step_bar.set_step(3)
            elif scenes and self.words_timestamps:
                self.player_dock.preview_stack.setCurrentIndex(0)
                self.studio_view.step_bar.set_step(2)
            elif script_txt.strip():
                self.player_dock.preview_stack.setCurrentIndex(0)
                self.studio_view.step_bar.set_step(1)
            else:
                self.player_dock.preview_stack.setCurrentIndex(0)
                self.studio_view.step_bar.set_step(0)
        finally:
            self._sync_guard = False

        self._refresh_usage_and_costs()
        self.switch_nav(0)

    def create_blank_project(self):
        self._sync_guard = True
        try:
            self.current_project = {
                "id": None,
                "project_slug": "untitled-video",
                "title": "",
                "hook": "",
                "category": "STEM",
                "visual_engine": "3D_Pixar",
                "render_mode": self.config.get("default_render_mode", "smart_hybrid"),
                "style_reference_path": "",
                "script_text": "",
                "tiktok_product": "",
                "duration_target": 65,
                "status": "Draft",
                "scheduled_time": None,
                "meta_title": "",
                "meta_description": "",
                "meta_hashtags": "#shorts #howthingswork #science #fyp",
                "storyboard_json": "[]",
            }
            self.words_timestamps = []
            self.studio_view.input_title.clear()
            self.studio_view.txt_script.clear()
            self.studio_view.storyboard_inspector.load_scenes([], "")
            self.player_dock.clear_preview()
            self.studio_view.step_bar.set_step(0, "Step 1 of 4: Pick an idea below or enter a topic, then click 'Write My Script →'")
            self.load_project_dict_into_ui(self.current_project)
        finally:
            self._sync_guard = False

        self.sync_ui_to_project_state(persist_db=False)
        self.studio_view.lbl_pipeline_status.setText("Ready — Start a fresh video by entering a topic in Step 1.")

    def on_clear_storyboard_scenes(self):
        self.current_project["storyboard_json"] = "[]"
        p_dir = self.get_project_dir()
        for sb_p in (
            os.path.join(p_dir, "storyboard.json"),
            os.path.join(p_dir, "storyboard", "storyboard.json"),
        ):
            if os.path.exists(sb_p):
                try:
                    with open(sb_p, "w", encoding="utf-8") as f:
                        f.write("[]")
                except Exception:
                    pass
        self.player_dock.clear_preview()
        self.sync_ui_to_project_state(persist_db=True)
        self._refresh_usage_and_costs()
        self.studio_view.lbl_pipeline_status.setText("✓ Cleared all preview scenes. Ready to write a new script or add scenes.")

    def on_reset_preview(self):
        self.sync_ui_to_project_state(persist_db=False)
        self.studio_view.lbl_pipeline_status.setText("Preview canvas reset.")

    # =========================================================================
    # WORKFLOW 1: COMPETITOR RADAR -> STUDIO
    # =========================================================================
    def on_scrape_competitors(self, query: str, mode: str):
        worker = ScraperWorker(
            query=query,
            max_results=5,
            gemini_api_key=self.config.get("gemini_api_key", ""),
            mode=mode,
        )
        worker.progress.connect(self.research_view.lbl_status.setText)
        worker.finished.connect(self._on_scrape_finished)
        worker.error.connect(lambda err: self.research_view.lbl_status.setText(f"Note: {err}"))
        self._active_workers.append(worker)
        worker.start()

    def _on_scrape_finished(self, payload: dict):
        self.research_view.load_results(payload)
        self._refresh_usage_and_costs()

    def on_research_concept_selected(self, concept: dict):
        self.competitor_insights = {
            "confusion_points": concept.get("confusion_points", ""),
            "complaints": concept.get("complaints", ""),
            "content_gaps": concept.get("content_gaps", ""),
        }
        title = concept.get("title", "Untitled Concept")
        self.current_project["id"] = None
        self.current_project["project_slug"] = slugify_topic(title)
        self.current_project["hook"] = concept.get("hook", "")

        self.studio_view.input_title.setText(title)

        cat = concept.get("category", "STEM")
        idx = self.studio_view.combo_category.findText(cat)
        if idx >= 0:
            self.studio_view.combo_category.setCurrentIndex(idx)

        style = concept.get("style", "3D_Pixar")
        self.studio_view._on_style_card_clicked(style)

        self.studio_view.txt_script.clear()
        self.sync_ui_to_project_state(persist_db=True)
        self.switch_nav(0)
        self.on_generate_script()

    # =========================================================================
    # WORKFLOW 2: GEMINI 3.8 FLASH SCRIPT GENERATION & SURGICAL REVISION
    # =========================================================================
    def on_generate_script(self):
        state = self.sync_ui_to_project_state(persist_db=True)
        self.studio_view.lbl_pipeline_status.setText("Writing your 61-70s viral script with Gemini 3.8 Flash...")
        self.studio_view.btn_generate_script.setEnabled(False)

        worker = ScriptAIWorker(
            script_text="",
            prompt=state.get("hook", ""),
            category=state["category"],
            target_duration=state["duration_target"],
            tiktok_product=state["tiktok_product"],
            topic=state["title"],
            api_key=self.config.get("gemini_api_key", ""),
            confusion_points=self.competitor_insights.get("confusion_points", ""),
            complaints=self.competitor_insights.get("complaints", ""),
            content_gaps=self.competitor_insights.get("content_gaps", ""),
            choreograph_scenes=True,
            visual_engine=state["visual_engine"],
            render_mode=state["render_mode"],
            style_reference_path=state["style_reference_path"],
            existing_scenes=self.studio_view.storyboard_inspector.get_scenes(),
            project_dir=self.get_project_dir(),
        )
        worker.progress.connect(self.studio_view.lbl_pipeline_status.setText)
        worker.finished.connect(self._on_script_ready)
        worker.error.connect(self._on_script_error)
        self._active_workers.append(worker)
        worker.start()

    def on_revise_script(self, instruction: str):
        state = self.sync_ui_to_project_state(persist_db=True)
        self.studio_view.lbl_pipeline_status.setText(f"Updating script: '{instruction}'...")
        self.studio_view.btn_apply_revision.setEnabled(False)

        worker = ScriptAIWorker(
            script_text=state["script_text"],
            prompt=instruction,
            category=state["category"],
            target_duration=state["duration_target"],
            tiktok_product=state["tiktok_product"],
            topic=state["title"],
            api_key=self.config.get("gemini_api_key", ""),
            confusion_points=self.competitor_insights.get("confusion_points", ""),
            complaints=self.competitor_insights.get("complaints", ""),
            content_gaps=self.competitor_insights.get("content_gaps", ""),
            choreograph_scenes=True,
            visual_engine=state["visual_engine"],
            render_mode=state["render_mode"],
            style_reference_path=state["style_reference_path"],
            existing_scenes=self.studio_view.storyboard_inspector.get_scenes(),
            project_dir=self.get_project_dir(),
        )
        worker.progress.connect(self.studio_view.lbl_pipeline_status.setText)
        worker.finished.connect(self._on_script_ready)
        worker.error.connect(self._on_script_error)
        self._active_workers.append(worker)
        worker.start()

    def _on_script_ready(self, script_text: str, *args):
        if len(args) == 2:
            scenes, log_note = args[0], str(args[1])
        elif len(args) == 1:
            scenes, log_note = [], str(args[0])
        else:
            scenes, log_note = [], "Script Ready"

        self.studio_view.btn_generate_script.setEnabled(True)
        self.studio_view.btn_apply_revision.setEnabled(True)
        self.studio_view.input_ai_prompt.clear()
        self.studio_view.txt_script.setPlainText(script_text)
        self.studio_view.step_bar.set_step(1)
        p_dir = self.get_project_dir()
        if not scenes:
            engine = AIStoryboardEngine(gemini_api_key=self.config.get("gemini_api_key", ""))
            words_json = os.path.join(p_dir, "words_timestamp.json")
            raw_scenes = engine.segment_script_into_scenes(script_text, words_json, target_count=6)
            scenes = engine.build_scene_prompts(raw_scenes, "STEM", "3D_Pixar")
        if scenes:
            self.studio_view.storyboard_inspector.load_scenes(scenes, p_dir)
        self.on_autofill_metadata()
        self.sync_ui_to_project_state(persist_db=True)
        self._refresh_usage_and_costs()
        scene_msg = f"{len(scenes)} scene cards ready" if scenes else "ready"
        self.studio_view.lbl_pipeline_status.setText(
            f"✓ {log_note} — Script & {scene_msg}! (Click 'Next Step →' to build voiceover)"
        )

    def _on_script_error(self, err: str):
        self.studio_view.btn_generate_script.setEnabled(True)
        self.studio_view.btn_apply_revision.setEnabled(True)
        self.studio_view.lbl_pipeline_status.setText(f"Script error: {err}")
        self._refresh_usage_and_costs()

    # =========================================================================
    # WORKFLOW 3: STORYBOARD SEGMENTATION, CACHING & SINGLE-SCENE REGENERATION
    # =========================================================================
    def auto_segment_storyboard(self):
        state = self.sync_ui_to_project_state(persist_db=True)
        script_text = state["script_text"]
        if not script_text.strip():
            return

        p_dir = self.get_project_dir()
        words_json = os.path.join(p_dir, "words_timestamp.json")
        self.studio_view.lbl_pipeline_status.setText("Choreographing visual scenes in background...")

        worker = StoryboardChoreographyWorker(
            script_text=script_text,
            category=state["category"],
            visual_engine=state["visual_engine"],
            render_mode=state["render_mode"],
            target_duration=float(state["duration_target"]),
            style_reference_path=state["style_reference_path"],
            existing_scenes=self.studio_view.storyboard_inspector.get_scenes(),
            words_json_path=words_json,
            api_key=self.config.get("gemini_api_key", ""),
        )
        worker.progress.connect(self.studio_view.lbl_pipeline_status.setText)
        worker.finished.connect(self._on_segmentation_ready)
        worker.error.connect(lambda err: self.studio_view.lbl_pipeline_status.setText(f"Choreography note: {err}"))
        self._active_workers.append(worker)
        worker.start()

    def _on_segmentation_ready(self, scenes: list):
        p_dir = self.get_project_dir()
        if scenes:
            self.studio_view.storyboard_inspector.load_scenes(scenes, p_dir)
        self.sync_ui_to_project_state(persist_db=True)
        self._refresh_usage_and_costs()
        self.studio_view.lbl_pipeline_status.setText(
            f"✓ Choreographed {len(scenes)} visual scene cards — review below or click 'Next Step →'"
        )

    def _on_scenes_edited(self, _scenes: list):
        self.sync_ui_to_project_state(persist_db=True)
        self._refresh_usage_and_costs()

    def on_regenerate_single_scene(self, scene_index: int, scene_dict: dict):
        state = self.sync_ui_to_project_state(persist_db=True)
        self.studio_view.lbl_pipeline_status.setText(f"Redoing Scene {scene_index + 1}...")

        worker = SingleSceneWorker(
            project_slug=state["project_slug"],
            scene_idx=scene_index,
            scene_data=scene_dict,
            category=state["category"],
            visual_engine=state["visual_engine"],
            project_render_mode=state["render_mode"],
            total_scenes=max(1, len(self.studio_view.storyboard_inspector.get_scenes())),
            style_reference_path=state["style_reference_path"] or None,
        )
        worker.log_message.connect(self.studio_view.lbl_pipeline_status.setText)
        worker.scene_finished.connect(self._on_single_scene_done)
        worker.scene_error.connect(lambda err: self.studio_view.lbl_pipeline_status.setText(f"Scene error: {err}"))
        self._active_workers.append(worker)
        worker.start()

    def _on_single_scene_done(self, idx: int, updated_scene: dict):
        self.studio_view.storyboard_inspector.update_single_scene(idx, updated_scene)
        self.sync_ui_to_project_state(persist_db=True)
        self._refresh_usage_and_costs()
        self.studio_view.lbl_pipeline_status.setText(f"✓ Scene {idx + 1} updated and saved")

    def on_visual_revision_requested(self, instruction: str):
        modified_indices = self.studio_view.storyboard_inspector.apply_visual_revision(instruction)
        self.player_dock.input_visual_revision.clear()
        self.sync_ui_to_project_state(persist_db=True)
        self._refresh_usage_and_costs()
        self.studio_view.lbl_pipeline_status.setText(
            f"Updated {len(modified_indices)} scene(s) — rendering updated visuals..."
        )
        self.on_run_render(visual_revision_prompt=instruction)

    def on_copy_omni_prompts(self):
        state = self.sync_ui_to_project_state(persist_db=True)
        p_dir = self.get_project_dir()
        engine = AIStoryboardEngine(gemini_api_key=self.config.get("gemini_api_key", ""))
        scenes = self.studio_view.storyboard_inspector.get_scenes()
        engine._write_flow_prompts_file(p_dir, scenes)
        txt_path = os.path.join(p_dir, "flow_prompts.txt")
        if os.path.exists(txt_path):
            with open(txt_path, "r", encoding="utf-8") as f:
                QApplication.clipboard().setText(f.read())
        self.studio_view.lbl_pipeline_status.setText("✓ Copied scene prompts to clipboard")

    def on_import_external_clips(self):
        files, _ = QFileDialog.getOpenFileNames(
            self, "Import External Scene Clips or Keyframes", "", "Media (*.mp4 *.png *.jpg *.webp)"
        )
        if not files:
            return
        p_dir = self.get_project_dir()
        sb_dir = os.path.join(p_dir, "storyboard")
        scenes = self.studio_view.storyboard_inspector.get_scenes()
        for i, src in enumerate(files):
            if i >= len(scenes):
                break
            ext = os.path.splitext(src)[1].lower()
            if ext == ".mp4":
                dst = os.path.join(sb_dir, f"clip_{i + 1:02d}.mp4")
                shutil.copy2(src, dst)
                scenes[i]["video_clip_path"] = dst
            else:
                dst = os.path.join(sb_dir, f"scene_{i + 1:02d}.png")
                shutil.copy2(src, dst)
                scenes[i]["image_path"] = dst
            scenes[i]["scene_hash"] = ""
        self.studio_view.storyboard_inspector.load_scenes(scenes, p_dir)
        self.sync_ui_to_project_state(persist_db=True)
        self._refresh_usage_and_costs()

    # =========================================================================
    # WORKFLOW 4: VOICE, FOLEY & WORD-LEVEL TIMESTAMP PIPELINE
    # =========================================================================
    def on_run_audio(self):
        state = self.sync_ui_to_project_state(persist_db=True)
        if not state["script_text"].strip():
            QMessageBox.warning(self, "No Script Yet", "Click 'Write My Script' in Step 1 first.")
            return

        self.studio_view.btn_run_audio.setEnabled(False)
        self.studio_view.progress_bar.setValue(5)

        worker = AudioPipelineWorker(
            project_slug=state["project_slug"],
            title=state["title"],
            hook=state.get("hook", ""),
            category=state["category"],
            script_text=state["script_text"],
            duration_target=state["duration_target"],
            tiktok_product=state["tiktok_product"],
            voice=self.config.get("tts_voice", "en-US-AndrewNeural"),
            speed=float(self.config.get("tts_speed", 1.08)),
            visual_engine=state["visual_engine"],
            render_mode=state["render_mode"],
            style_reference_path=state["style_reference_path"],
            meta_title=state["meta_title"],
            meta_description=state["meta_description"],
            meta_hashtags=state["meta_hashtags"],
            existing_scenes=self.studio_view.storyboard_inspector.get_scenes(),
        )
        worker.log_message.connect(self.studio_view.lbl_pipeline_status.setText)
        worker.progress_val.connect(self.studio_view.progress_bar.setValue)
        worker.pipeline_finished.connect(self._on_audio_done)
        worker.pipeline_error.connect(self._on_pipeline_error)
        self._active_workers.append(worker)
        worker.start()

    def _on_audio_done(self, result: dict):
        self.studio_view.btn_run_audio.setEnabled(True)
        self.current_project["id"] = result.get("project_id", self.current_project.get("id"))
        self.current_project["status"] = "Audio_Ready"
        self.words_timestamps = result.get("words_list", [])
        scenes = result.get("scenes", [])
        if scenes:
            self.studio_view.storyboard_inspector.load_scenes(scenes, self.get_project_dir())
        self.studio_view.step_bar.set_step(2)
        self.sync_ui_to_project_state(persist_db=True)
        self._refresh_usage_and_costs()
        self.studio_view.lbl_pipeline_status.setText(
            "✓ Voiceover & scene timing ready! Click 'Step 4: Create My Video' to render your MP4."
        )

    # =========================================================================
    # WORKFLOW 5: 9:16 RENDERING, LANCZOS UPSCALING & VISUAL CRITIC GATE
    # =========================================================================
    def on_run_render(self, visual_revision_prompt: str = ""):
        if not self.studio_view.btn_run_render.isEnabled():
            return  # render already in progress; ignore double-clicks
        state = self.sync_ui_to_project_state(persist_db=True)
        if not state["script_text"].strip():
            QMessageBox.warning(self, "No Script Yet", "Click 'Write My Script' in Step 1 first.")
            return

        self.studio_view.step_bar.set_step(3)
        self.studio_view.btn_run_render.setEnabled(False)
        self.studio_view.progress_bar.setValue(5)

        worker = StoryboardRenderWorker(
            project_slug=state["project_slug"],
            category=state["category"],
            ffmpeg_path=self.config.get("ffmpeg_path", "ffmpeg"),
            script_text=state["script_text"],
            visual_engine=state["visual_engine"],
            render_mode=state["render_mode"],
            style_reference_path=state["style_reference_path"] or None,
            visual_revision_prompt=visual_revision_prompt,
            custom_scenes=self.studio_view.storyboard_inspector.get_scenes(),
            voice=self.config.get("tts_voice", "en-US-GuyNeural"),
            speed=float(self.config.get("tts_speed", 1.05)),
        )
        worker.log_message.connect(self.studio_view.lbl_pipeline_status.setText)
        worker.progress_val.connect(self.studio_view.progress_bar.setValue)
        worker.render_finished.connect(self._on_render_done)
        worker.render_error.connect(self._on_pipeline_error)
        self._active_workers.append(worker)
        worker.start()

    def _on_render_done(self, result: dict):
        self.studio_view.btn_run_render.setEnabled(True)
        final_mp4 = result.get("final_mp4", "")
        scenes = result.get("scenes", [])
        critic_report = result.get("critic_report", {})

        self.current_project["status"] = "Rendered"
        p_dir = self.get_project_dir()
        if scenes:
            self.studio_view.storyboard_inspector.load_scenes(scenes, p_dir)

        self.sync_ui_to_project_state(persist_db=True)
        self._refresh_usage_and_costs()

        if final_mp4 and os.path.exists(final_mp4):
            self.player_dock.load_video(final_mp4)
        if critic_report:
            self.player_dock.load_critic_report(critic_report)
            self.player_dock.chk_ret_visual.setChecked(bool(critic_report.get("passed", True)))

        self.studio_view.lbl_pipeline_status.setText(
            f"✓ Your video is ready! Click '💾 Save Video (.MP4)' on the right phone dock."
        )

    def _on_pipeline_error(self, err: str):
        self.studio_view.btn_run_audio.setEnabled(True)
        self.studio_view.btn_run_render.setEnabled(True)
        self._refresh_usage_and_costs()
        self.studio_view.lbl_pipeline_status.setText(f"Note: {err}")

    # =========================================================================
    # WORKFLOW 6: METADATA, CALENDAR, EXPORT & DISPATCH
    # =========================================================================
    def on_autofill_metadata(self):
        state = self.sync_ui_to_project_state(persist_db=False)
        topic = state["title"]
        cat = state["category"]
        self.player_dock.meta_title.setText(f"{topic} (Explained in {state['duration_target']}s)")
        self.player_dock.meta_description.setPlainText(
            f"Here is how {topic} actually works inside.\nCategory: {cat}\nWatch till the end for the full breakdown!"
        )
        self.player_dock.meta_hashtags.setText("#shorts #howthingswork #engineering #science #explained #fyp")
        self.sync_ui_to_project_state(persist_db=True)

    def on_save_to_calendar(self):
        self.sync_ui_to_project_state(persist_db=True)
        self.switch_nav(2)

    def on_schedule_project(self, project_id: int, date_str: str):
        update_project_status(project_id, status="Scheduled", scheduled_time=date_str)
        if self.current_project.get("id") == project_id:
            self.current_project["scheduled_time"] = date_str
            self.current_project["status"] = "Scheduled"
        self.calendar_view.refresh_projects(get_all_projects())

    def on_export_mp4(self):
        state = self.sync_ui_to_project_state(persist_db=True)
        p_dir = self.get_project_dir()
        vid = os.path.join(p_dir, f"{state['project_slug']}_final.mp4")
        if not os.path.exists(vid):
            QMessageBox.information(self, "Video Not Created Yet", "Click 'Step 4: Create My Video' first before saving.")
            return
        dst, _ = QFileDialog.getSaveFileName(
            self, "Save Final 1080x1920 MP4 Video", f"{state['project_slug']}_1080x1920.mp4", "MP4 Video (*.mp4)"
        )
        if dst:
            shutil.copy2(vid, dst)
            self.studio_view.lbl_pipeline_status.setText(f"✓ Saved video to {dst}")

    def on_dispatch_webhook(self):
        state = self.sync_ui_to_project_state(persist_db=True)
        p_dir = self.get_project_dir()
        vid = os.path.join(p_dir, f"{state['project_slug']}_final.mp4")
        metadata = {
            "title": state["meta_title"] or state["title"],
            "description": state["meta_description"],
            "tags": [t.lstrip("#") for t in state["meta_hashtags"].split() if t.strip()],
            "hashtags": [t for t in state["meta_hashtags"].split() if t.strip()],
            "tiktok_product": state["tiktok_product"],
        }
        yt_res = upload_to_youtube(vid, metadata, scheduled_time=state.get("scheduled_time"), dry_run=True)
        tk_res = queue_tiktok_draft(vid, metadata, dry_run=True)
        self.studio_view.lbl_pipeline_status.setText(
            f"✓ Queued: {yt_res.get('message')} | {tk_res.get('message')}"
        )

    def on_save_settings(self, updated_cfg: dict):
        self.config = dict(updated_cfg)
        save_app_config(self.config)
        usage_tracker.probe_api_health(self.config.get("gemini_api_key", ""))
        self._refresh_usage_and_costs()
        self.lbl_model_stack.setText(
            f"• Writer: {self.config.get('text_model', 'gemini-3.8-flash')}\n"
            f"• Art: {self.config.get('image_model', 'gemini-nano-banana-2.1')}\n"
            f"• Video: omni-1.1 ({self.config.get('omni_resolution', '720p')}->1080p)"
        )


def main():
    app = QApplication(sys.argv)
    window = CrayonStudioWindow()
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
