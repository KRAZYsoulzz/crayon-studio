"""
CRAYON STUDIO — Visual Engine Router
Dispatches AI Storyboard & Omni 1.1 Flash rendering across modern visual style presets
with automated Visual Critic 4-Keyframe inspection.
"""

from __future__ import annotations

import logging
import os
from typing import Any, Callable, Dict, List, Optional

from core.storyboard_engine import AIStoryboardEngine
from core.visual_critic import generate_and_verify_snapshots

logger = logging.getLogger("VisualEngineRouter")


class VisualEngineRouter:
    """
    Unified router for CrayonStudio AI Visual Style Presets & Render Modes:
      - 3D_Pixar: 3D Pixar / Zack D. Films Cutaway Animation
      - 3D_Teardown: 3D Isometric Hardware Teardown (Exploded CAD / X-Ray)
      - 2D_Kurzgesagt: 2D Kurzgesagt / Stylized Illustrated Storybook
      - Custom_Style: Custom Reference Image Lock (<IMAGE_REF_0>)
    """

    ENGINE_PIXAR = "3D_Pixar"
    ENGINE_TEARDOWN = "3D_Teardown"
    ENGINE_KURZGESAGT = "2D_Kurzgesagt"
    ENGINE_CUSTOM = "Custom_Style"
    # Legacy alias
    ENGINE_2D = "3D_Pixar"
    ENGINE_3D = "3D_Teardown"

    DISPLAY_NAMES = {
        "3D_Pixar": "3D Pixar / Zack D. Films Cutaway",
        "3D_Teardown": "3D Isometric Hardware Teardown (Exploded CAD / X-Ray)",
        "2D_Kurzgesagt": "2D Kurzgesagt / Stylized Illustrated Storybook",
        "Custom_Style": "Custom Style Reference Lock (<IMAGE_REF_0>)",
        "2D_Crayon": "3D Pixar / Zack D. Films Cutaway",
    }

    RENDER_MODE_NAMES = {
        "smart_hybrid": "Smart Hybrid (Recommended — Omni Hook/Climax + Nano Banana Keyframes)",
        "full_omni": "Full Gemini Omni 1.1 Flash Video (Multi-Turn / Timecoded)",
        "keyframe_only": "Nano Banana 2.1 Keyframes + 30fps 2.5D Motion (Ultra-Low Cost)",
    }

    def __init__(
        self,
        visual_engine: str = "3D_Pixar",
        ffmpeg_path: Optional[str] = None,
        blender_path: Optional[str] = None,
    ):
        if visual_engine == "2D_Crayon":
            visual_engine = self.ENGINE_PIXAR
        self.visual_engine = visual_engine if visual_engine in self.DISPLAY_NAMES else self.ENGINE_PIXAR
        self.ffmpeg_path = ffmpeg_path or "ffmpeg"

    @classmethod
    def get_display_name(cls, engine: str) -> str:
        return cls.DISPLAY_NAMES.get(engine, cls.DISPLAY_NAMES[cls.ENGINE_PIXAR])

    @classmethod
    def recommend_engine_for_category(cls, category: str) -> str:
        """Suggests the optimal visual style preset based on content category."""
        cat_lower = category.lower().strip()
        if any(keyword in cat_lower for keyword in ["how it", "engineering", "hardware", "machine", "device", "gadget"]):
            return cls.ENGINE_TEARDOWN
        if "psych" in cat_lower:
            return cls.ENGINE_KURZGESAGT
        return cls.ENGINE_PIXAR

    def render_project(
        self,
        project_dir: str,
        words_json_path: str,
        output_mp4_path: str,
        category: str = "STEM",
        script_text: Optional[str] = None,
        render_mode: str = "smart_hybrid",
        style_reference_path: Optional[str] = None,
        enable_omni_video: bool = False,
        visual_revision_prompt: str = "",
        custom_scenes: Optional[List[Dict[str, Any]]] = None,
        progress_callback: Optional[Callable[[str], None]] = None,
    ) -> Dict[str, Any]:
        """Executes rendering through AIStoryboardEngine followed by 4-keyframe Visual Critic inspection."""
        def _cb(msg: str):
            if progress_callback:
                progress_callback(msg)
            logger.info(msg)

        _cb(f"[Engine] Initializing {self.get_display_name(self.visual_engine)} ({render_mode})...")

        engine = AIStoryboardEngine()
        rendered_video = engine.render_project(
            project_dir=project_dir,
            words_json_path=words_json_path,
            output_mp4_path=output_mp4_path,
            category=category,
            script_text=script_text,
            visual_engine=self.visual_engine,
            render_mode=render_mode,
            style_reference_path=style_reference_path,
            enable_omni_video=enable_omni_video,
            visual_revision_prompt=visual_revision_prompt,
            custom_scenes=custom_scenes,
            progress_callback=_cb,
        )

        _cb("[Critic] Running Visual Critic 4-Keyframe automated inspection...")
        critic_report = generate_and_verify_snapshots(
            video_path=rendered_video,
            project_dir=project_dir,
            total_duration=0.0,
            ffmpeg_path=self.ffmpeg_path,
        )

        status_icon = "[OK]" if critic_report.get("passed") else "[WARN]"
        _cb(f"{status_icon} Visual Critic Report: {critic_report.get('notes', 'Inspection finished')}")

        return {
            "video_path": rendered_video,
            "visual_engine": self.visual_engine,
            "render_mode": render_mode,
            "snapshots": critic_report.get("snapshots", []),
            "critic_report": critic_report,
        }
