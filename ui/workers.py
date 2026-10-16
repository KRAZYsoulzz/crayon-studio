"""
CRAYON STUDIO — Asynchronous QThread Workers
Handles non-blocking execution for:
- Competitor Comment Mining & Gemini Suggestion Synthesis (`ScraperWorker`)
- Gemini 3.8 Flash Script Authoring & Surgical Revisions (`ScriptAIWorker`)
- Voiceover TTS + Whisper Word Alignment + Style Foley + Scene Segmentation (`AudioPipelineWorker`)
- Full Storyboard & Omni 1.1 Flash Video Render + FFmpeg 1080p Compositing (`StoryboardRenderWorker`)
- Single-Scene Keyframe / Omni Video Regeneration (`SingleSceneWorker`)
"""

from __future__ import annotations

import json
import logging
import os
from typing import Any, Dict, List, Optional

from PySide6.QtCore import QThread, Signal

from core.ai_modifier import modify_script, get_last_ai_status
from core.audio_generator import generate_voiceover
from core.engine_router import VisualEngineRouter
from core.ffmpeg_compositor import FFmpegCompositor
from core.foley_mixer import generate_foley_track
from core.scraper import (
    generate_content_suggestions,
    scan_competitor_channel,
    search_trends_and_comments,
)
from core.storyboard_engine import AIStoryboardEngine
from core.timestamp_aligner import extract_word_timestamps
import database.db as db

logger = logging.getLogger("crayon_studio.workers")

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PROJECTS_DIR = os.path.join(BASE_DIR, "projects")


class ScraperWorker(QThread):
    """Background worker for YouTube competitor search, channel scanning, and Gemini suggestion synthesis."""

    progress = Signal(str)
    finished = Signal(dict)
    error = Signal(str)

    def __init__(
        self,
        query: str,
        max_results: int = 5,
        api_key: Optional[str] = None,
        gemini_api_key: Optional[str] = None,
        mode: str = "keyword",
    ):
        super().__init__()
        self.query = query
        self.max_results = max_results
        self.api_key = api_key
        self.gemini_api_key = gemini_api_key
        self.mode = mode

    def run(self):
        try:
            if self.mode == "channel":
                self.progress.emit(f"Scanning competitor channel '{self.query}' for audience friction...")
                trends = scan_competitor_channel(self.query, self.max_results)
            else:
                self.progress.emit(f"Mining competitor videos & comments for '{self.query}'...")
                trends = search_trends_and_comments(self.query, self.max_results, self.api_key)

            self.progress.emit("Synthesizing high-retention video concepts with Gemini...")
            suggestions = generate_content_suggestions(trends, api_key=self.gemini_api_key)
            self.finished.emit({
                "trends": trends,
                "suggestions": suggestions,
            })
        except Exception as e:
            logger.error("Scraper worker failed: %s", e)
            self.error.emit(str(e))


class ScriptAIWorker(QThread):
    """Non-blocking background worker for Gemini 3.8 Flash script generation, surgical revision,
    and automatic scene choreography without freezing the UI thread."""

    progress = Signal(str)
    finished = Signal(str, list, str)  # (revised_script, scenes, log_note)
    error = Signal(str)

    def __init__(
        self,
        script_text: str,
        prompt: str,
        category: str,
        target_duration: int,
        tiktok_product: str,
        topic: str,
        api_key: Optional[str] = None,
        confusion_points: str = "",
        complaints: str = "",
        content_gaps: str = "",
        choreograph_scenes: bool = True,
        visual_engine: str = "3D_Pixar",
        render_mode: str = "smart_hybrid",
        style_reference_path: str = "",
        existing_scenes: Optional[List[Dict[str, Any]]] = None,
        project_dir: str = "",
    ):
        super().__init__()
        self.script_text = script_text
        self.prompt = prompt
        self.category = category
        self.target_duration = target_duration
        self.tiktok_product = tiktok_product
        self.topic = topic
        self.api_key = api_key
        self.confusion_points = confusion_points
        self.complaints = complaints
        self.content_gaps = content_gaps
        self.choreograph_scenes = choreograph_scenes
        self.visual_engine = visual_engine
        self.render_mode = render_mode
        self.style_reference_path = style_reference_path
        self.existing_scenes = existing_scenes or []
        self.project_dir = project_dir

    def run(self):
        try:
            is_new = not self.script_text.strip()
            if is_new:
                self.progress.emit("Writing 61-70s viral script with Gemini 3.8 Flash...")
            else:
                self.progress.emit(f"Updating script: '{self.prompt}' with Gemini 3.8 Flash...")

            revised = modify_script(
                script_text=self.script_text,
                prompt=self.prompt,
                category=self.category,
                target_duration=self.target_duration,
                tiktok_product=self.tiktok_product,
                topic=self.topic,
                api_key=self.api_key,
                confusion_points=self.confusion_points,
                complaints=self.complaints,
                content_gaps=self.content_gaps,
            )

            scenes: List[Dict[str, Any]] = []
            if self.choreograph_scenes and revised.strip():
                self.progress.emit("Choreographing visual scene cards with style DNA...")
                sb_engine = AIStoryboardEngine(gemini_api_key=self.api_key or "")
                words_json = os.path.join(self.project_dir, "words_timestamp.json") if self.project_dir else ""
                raw_scenes = sb_engine.segment_script_into_scenes(
                    script_text=revised,
                    words_json_path=words_json,
                    target_count=6,
                    default_duration=float(self.target_duration),
                )
                style_dna = sb_engine.extract_style_dna(
                    self.style_reference_path,
                    visual_engine=self.visual_engine,
                    progress_callback=self.progress.emit,
                )
                scenes = sb_engine.build_scene_prompts(
                    scenes=raw_scenes,
                    category=self.category,
                    visual_engine=self.visual_engine,
                    render_mode=self.render_mode,
                    style_dna=style_dna,
                    existing_scenes=self.existing_scenes,
                    style_reference_path=self.style_reference_path,
                )

            action_label = "Generated new script" if is_new else f"Applied revision: '{self.prompt}'"
            status_note = get_last_ai_status()
            self.finished.emit(revised, scenes, f"{action_label} ({len(revised.split())} words) [{status_note}]")
        except Exception as e:
            logger.error("ScriptAIWorker failed: %s", e)
            self.error.emit(str(e))


class StoryboardChoreographyWorker(QThread):
    """Asynchronous background worker for choreographing scene cards and prompts without freezing the GUI."""

    progress = Signal(str)
    finished = Signal(list)
    error = Signal(str)

    def __init__(
        self,
        script_text: str,
        category: str,
        visual_engine: str,
        render_mode: str,
        target_duration: float,
        style_reference_path: str = "",
        existing_scenes: Optional[List[Dict[str, Any]]] = None,
        words_json_path: str = "",
        api_key: Optional[str] = None,
    ):
        super().__init__()
        self.script_text = script_text
        self.category = category
        self.visual_engine = visual_engine
        self.render_mode = render_mode
        self.target_duration = target_duration
        self.style_reference_path = style_reference_path
        self.existing_scenes = existing_scenes or []
        self.words_json_path = words_json_path
        self.api_key = api_key

    def run(self):
        try:
            self.progress.emit("Analyzing script timing & natural beat boundaries...")
            sb_engine = AIStoryboardEngine(gemini_api_key=self.api_key or "")
            raw_scenes = sb_engine.segment_script_into_scenes(
                script_text=self.script_text,
                words_json_path=self.words_json_path,
                target_count=6,
                default_duration=self.target_duration,
            )
            self.progress.emit("Extracting visual aesthetic style DNA...")
            style_dna = sb_engine.extract_style_dna(
                self.style_reference_path,
                visual_engine=self.visual_engine,
                progress_callback=self.progress.emit,
            )
            self.progress.emit("Choreographing dynamic 9:16 scene actions with Gemini 3.8 Flash...")
            scenes = sb_engine.build_scene_prompts(
                scenes=raw_scenes,
                category=self.category,
                visual_engine=self.visual_engine,
                render_mode=self.render_mode,
                style_dna=style_dna,
                existing_scenes=self.existing_scenes,
                style_reference_path=self.style_reference_path,
            )
            self.finished.emit(scenes)
        except Exception as e:
            logger.error("StoryboardChoreographyWorker failed: %s", e)
            self.error.emit(str(e))


class AudioPipelineWorker(QThread):
    """Asynchronous worker for Audio TTS, Whisper word alignment, Foley, and initial Scene Choreography."""

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
        visual_engine: str = "3D_Pixar",
        render_mode: str = "smart_hybrid",
        style_reference_path: str = "",
        meta_title: str = "",
        meta_description: str = "",
        meta_hashtags: str = "",
        existing_scenes: Optional[List[Dict[str, Any]]] = None,
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
        self.render_mode = render_mode
        self.style_reference_path = style_reference_path
        self.meta_title = meta_title or title
        self.meta_description = meta_description
        self.meta_hashtags = meta_hashtags
        self.existing_scenes = existing_scenes

    def run(self):
        try:
            self.log_message.emit("Initializing project workspace & saving current on-screen script...")
            self.progress_val.emit(10)
            proj_dir = os.path.join(PROJECTS_DIR, self.project_slug)
            os.makedirs(proj_dir, exist_ok=True)
            with open(os.path.join(proj_dir, "script.txt"), "w", encoding="utf-8") as f:
                f.write(self.script_text)

            # 1. Audio Synthesis
            self.log_message.emit(f"Synthesizing neural documentary voiceover [Voice: {self.voice}, Speed: {self.speed:.2f}x]...")
            self.progress_val.emit(35)
            vo_path = os.path.join(proj_dir, "voiceover.wav")
            generate_voiceover(self.script_text, vo_path, voice=self.voice, speed=self.speed)
            self.log_message.emit(f"Voiceover synthesized: {vo_path}")

            # 2. Word-Level Timestamp Extraction (faster-whisper)
            self.log_message.emit("Extracting word-level timestamps with faster-whisper...")
            self.progress_val.emit(60)
            words_json_path = os.path.join(proj_dir, "words_timestamp.json")
            words_list = extract_word_timestamps(vo_path, words_json_path, script_text=self.script_text)
            total_dur = float(words_list[-1]["end"]) if words_list else float(self.duration_target)
            self.log_message.emit(f"Aligned {len(words_list)} words (Total spoken duration: {total_dur:.1f}s)")

            # 3. Segment Script & Choreograph Scenes with Gemini 3.8 Flash
            self.log_message.emit("Choreographing 6 timed storyboard scenes & prompts...")
            self.progress_val.emit(78)
            sb_engine = AIStoryboardEngine()
            raw_scenes = sb_engine.segment_script_into_scenes(self.script_text, words_json_path, target_count=6)
            style_dna = sb_engine.extract_style_dna(self.style_reference_path, visual_engine=self.visual_engine)
            scenes = sb_engine.build_scene_prompts(
                scenes=raw_scenes,
                category=self.category,
                visual_engine=self.visual_engine,
                render_mode=self.render_mode,
                style_dna=style_dna,
                existing_scenes=self.existing_scenes,
                style_reference_path=self.style_reference_path,
            )
            sb_json_path = os.path.join(proj_dir, "storyboard.json")
            with open(sb_json_path, "w", encoding="utf-8") as f:
                json.dump(scenes, f, indent=2)
            sb_engine._write_flow_prompts_file(proj_dir, scenes)

            # 4. Style-Adaptive Transition Foley
            self.log_message.emit(f"Synthesizing {self.visual_engine} transition Foley cues...")
            self.progress_val.emit(90)
            foley_path = os.path.join(proj_dir, "foley_track.wav")
            generate_foley_track(words_json_path, foley_path, duration=total_dur, visual_engine=self.visual_engine)

            # 5. Persist complete state to SQLite
            proj_id = db.upsert_project(
                project_slug=self.project_slug,
                title=self.title,
                hook=self.hook,
                category=self.category,
                visual_engine=self.visual_engine,
                render_mode=self.render_mode,
                script_text=self.script_text,
                duration_target=self.duration_target,
                tiktok_product=self.tiktok_product,
                style_reference_path=self.style_reference_path,
                meta_title=self.meta_title,
                meta_description=self.meta_description,
                meta_hashtags=self.meta_hashtags,
                storyboard_json=json.dumps(scenes),
                status="Audio_Ready",
            )

            self.progress_val.emit(100)
            self.log_message.emit("Audio & Scene Timeline ready. Review scenes below or click 'Render Final Video'.")

            self.pipeline_finished.emit({
                "project_id": proj_id,
                "project_slug": self.project_slug,
                "title": self.title,
                "script_text": self.script_text,
                "category": self.category,
                "duration": total_dur,
                "voiceover_path": vo_path,
                "words_json_path": words_json_path,
                "words_list": words_list,
                "foley_path": foley_path,
                "visual_engine": self.visual_engine,
                "render_mode": self.render_mode,
                "scenes": scenes,
            })
        except Exception as e:
            logger.error("AudioPipelineWorker error: %s", e, exc_info=True)
            self.log_message.emit(f"ERROR: {e}")
            self.pipeline_error.emit(str(e))


class StoryboardRenderWorker(QThread):
    """Background worker for AI Storyboard + Omni 1.1 Flash render + FFmpeg 1080p subtitle compositing."""

    log_message = Signal(str)
    progress_val = Signal(int)
    render_finished = Signal(dict)
    render_error = Signal(str)

    def __init__(
        self,
        project_slug: str,
        category: str,
        ffmpeg_path: str,
        script_text: str,
        visual_engine: str = "3D_Pixar",
        render_mode: str = "smart_hybrid",
        style_reference_path: Optional[str] = None,
        visual_revision_prompt: str = "",
        custom_scenes: Optional[List[Dict[str, Any]]] = None,
        voice: str = "en-US-GuyNeural",
        speed: float = 1.00,
    ):
        super().__init__()
        self.project_slug = project_slug
        self.category = category
        self.ffmpeg_path = ffmpeg_path
        self.script_text = script_text
        self.visual_engine = visual_engine
        self.render_mode = render_mode
        self.style_reference_path = style_reference_path
        self.visual_revision_prompt = visual_revision_prompt
        self.custom_scenes = custom_scenes
        self.voice = voice
        self.speed = speed

    def run(self):
        try:
            proj_dir = os.path.join(PROJECTS_DIR, self.project_slug)
            os.makedirs(proj_dir, exist_ok=True)

            script_file = os.path.join(proj_dir, "script.txt")
            words_json = os.path.join(proj_dir, "words_timestamp.json")
            vo_path = os.path.join(proj_dir, "voiceover.wav")
            foley_path = os.path.join(proj_dir, "foley_track.wav")
            raw_video = os.path.join(proj_dir, "scene_raw.mp4")
            final_mp4 = os.path.join(proj_dir, f"{self.project_slug}_final.mp4")

            # Auto-detect if script changed since last audio generation or if audio hasn't been generated yet
            old_disk_script = ""
            if os.path.exists(script_file):
                try:
                    with open(script_file, "r", encoding="utf-8") as f:
                        old_disk_script = f.read().strip()
                except Exception:
                    pass

            if self.script_text.strip():
                with open(script_file, "w", encoding="utf-8") as f:
                    f.write(self.script_text.strip())

            script_changed = bool(self.script_text.strip() and self.script_text.strip() != old_disk_script)
            if not os.path.exists(vo_path) or not os.path.exists(words_json) or script_changed:
                self.log_message.emit("Syncing voiceover & word timestamps to match current on-screen script...")
                self.progress_val.emit(12)
                generate_voiceover(self.script_text, vo_path, voice=self.voice, speed=self.speed)
                words_list = extract_word_timestamps(vo_path, words_json, script_text=self.script_text)
                total_dur = float(words_list[-1]["end"]) if words_list else 65.0
                generate_foley_track(words_json, foley_path, duration=total_dur, visual_engine=self.visual_engine)

            self.progress_val.emit(25)
            router = VisualEngineRouter(
                visual_engine=self.visual_engine,
                ffmpeg_path=self.ffmpeg_path,
            )
            render_res = router.render_project(
                project_dir=proj_dir,
                words_json_path=words_json,
                output_mp4_path=raw_video,
                category=self.category,
                script_text=self.script_text,
                render_mode=self.render_mode,
                style_reference_path=self.style_reference_path,
                visual_revision_prompt=self.visual_revision_prompt,
                custom_scenes=self.custom_scenes,
                progress_callback=lambda msg: self.log_message.emit(msg),
            )

            self.log_message.emit("Upscaling to 1080x1920 & burning kinetic .ass subtitles with FFmpeg...")
            self.progress_val.emit(80)
            comp = FFmpegCompositor(ffmpeg_path=self.ffmpeg_path)
            comp.composite_video(
                video_path=raw_video,
                voiceover_path=vo_path,
                words_json_path=words_json,
                output_mp4_path=final_mp4,
                foley_path=foley_path,
                progress_callback=lambda msg: self.log_message.emit(msg),
            )

            # Read updated storyboard.json
            scenes = []
            sb_json_path = os.path.join(proj_dir, "storyboard.json")
            if os.path.exists(sb_json_path):
                try:
                    with open(sb_json_path, "r", encoding="utf-8") as f:
                        scenes = json.load(f)
                except Exception:
                    pass

            self.progress_val.emit(100)
            self.log_message.emit(f"Broadcast-ready 1080x1920 MP4 rendered: {final_mp4}")
            self.render_finished.emit({
                "final_mp4": final_mp4,
                "scenes": scenes,
                "critic_report": render_res.get("critic_report", {}),
            })
        except Exception as e:
            logger.error("StoryboardRenderWorker error: %s", e, exc_info=True)
            self.render_error.emit(str(e))


class SingleSceneWorker(QThread):
    """Worker to regenerate a single scene's keyframe or Omni video clip from the Storyboard Inspector."""

    log_message = Signal(str)
    scene_finished = Signal(int, dict)
    scene_error = Signal(str)

    def __init__(
        self,
        project_slug: str,
        scene_idx: int,
        scene_data: Dict[str, Any],
        category: str,
        visual_engine: str,
        project_render_mode: str,
        total_scenes: int = 6,
        style_reference_path: Optional[str] = None,
    ):
        super().__init__()
        self.project_slug = project_slug
        self.scene_idx = scene_idx
        self.scene_data = scene_data
        self.category = category
        self.visual_engine = visual_engine
        self.project_render_mode = project_render_mode
        self.total_scenes = total_scenes
        self.style_reference_path = style_reference_path

    def run(self):
        try:
            proj_dir = os.path.join(PROJECTS_DIR, self.project_slug)
            engine = AIStoryboardEngine()
            updated = engine.regenerate_single_scene(
                project_dir=proj_dir,
                scene_idx=self.scene_idx,
                scene_data=self.scene_data,
                category=self.category,
                visual_engine=self.visual_engine,
                project_render_mode=self.project_render_mode,
                total_scenes=self.total_scenes,
                style_reference_path=self.style_reference_path,
                progress_callback=lambda msg: self.log_message.emit(msg),
            )
            self.scene_finished.emit(self.scene_idx, updated)
        except Exception as e:
            logger.error("SingleSceneWorker error: %s", e, exc_info=True)
            self.scene_error.emit(str(e))
