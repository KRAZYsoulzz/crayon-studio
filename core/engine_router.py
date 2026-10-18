"""
CRAYON STUDIO — Visual Engine Router
Dispatches AI Storyboard & Sketch-Reveal jobs (2D Storybook & 3D Teardown)
with automated Visual Critic 4-Keyframe inspection.
"""

import logging
import os
import shutil
from typing import Callable, Dict, List, Optional

from core.storyboard_engine import AIStoryboardEngine
from core.blender_orchestrator import BlenderOrchestrator
from core.teardown_3d_engine import Teardown3DEngine
from core.visual_critic import generate_and_verify_snapshots

logger = logging.getLogger("VisualEngineRouter")


class VisualEngineRouter:
    """
    Unified router that selects between:
      - Engine A: AI Storyboard & Sketch-Reveal (Continuous Storybook)
      - Engine B: 3D AI Hardware Teardown (Exploded View & X-Ray)
      - Legacy: Headless Blender 3D Curves
    """

    ENGINE_2D = "2D_Crayon"
    ENGINE_3D = "3D_Teardown"
    ENGINE_BLENDER = "Blender_Legacy"

    DISPLAY_NAMES = {
        "2D_Crayon": "[2D Crayon] AI Storyboard & Sketch-Reveal (Continuous Storybook)",
        "3D_Teardown": "[3D Teardown] AI Hardware Teardown (Exploded View & X-Ray)",
        "Blender_Legacy": "[Blender] Legacy Blender 3D Curves",
    }

    def __init__(
        self,
        visual_engine: str = "2D_Crayon",
        blender_path: Optional[str] = None,
        ffmpeg_path: Optional[str] = None,
    ):
        self.visual_engine = visual_engine if visual_engine in self.DISPLAY_NAMES else self.ENGINE_2D
        self.blender_path = blender_path
        self.ffmpeg_path = ffmpeg_path or "ffmpeg"

    @classmethod
    def get_display_name(cls, engine: str) -> str:
        return cls.DISPLAY_NAMES.get(engine, cls.DISPLAY_NAMES[cls.ENGINE_2D])

    @classmethod
    def recommend_engine_for_category(cls, category: str) -> str:
        """Suggests the optimal engine based on content category."""
        cat_lower = category.lower().strip()
        if any(keyword in cat_lower for keyword in ["how it", "engineering", "hardware", "machine", "device", "gadget"]):
            return cls.ENGINE_3D
        return cls.ENGINE_2D

    def render_project(
        self,
        project_dir: str,
        words_json_path: str,
        output_mp4_path: str,
        category: str = "STEM",
        script_text: Optional[str] = None,
        style_reference_path: Optional[str] = None,
        enable_omni_video: bool = False,
        visual_source: Optional[str] = None,
        progress_callback: Optional[Callable[[str], None]] = None,
    ) -> Dict:
        """
        Executes rendering through the selected engine, followed by
        4-keyframe visual inspection.
        Returns dict with output_mp4_path, snapshots, and critic_report.
        """
        def _cb(msg: str):
            if progress_callback:
                progress_callback(msg)
            logger.info(msg)

        _cb(f"[Engine] Initializing {self.get_display_name(self.visual_engine)}...")

        if self.visual_engine == self.ENGINE_BLENDER:
            engine = BlenderOrchestrator(blender_path=self.blender_path)
            rendered_video = engine.render_project(
                project_dir=project_dir,
                words_json_path=words_json_path,
                output_mp4_path=output_mp4_path,
                category=category,
                script_text=script_text,
                progress_callback=_cb,
            )
        else:
            # Default for 2D_Crayon and 3D_Teardown: AIStoryboardEngine
            engine = AIStoryboardEngine(config_path="config.json")
            rendered_video = engine.render_project(
                project_dir=project_dir,
                words_json_path=words_json_path,
                output_mp4_path=output_mp4_path,
                category=category,
                script_text=script_text,
                visual_engine=self.visual_engine,
                style_reference_path=style_reference_path,
                enable_omni_video=enable_omni_video,
                visual_source=visual_source,
                progress_callback=_cb,
            )

        # Run Visual Critic 4-Keyframe automated inspection
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
            "snapshots": critic_report.get("snapshots", []),
            "critic_report": critic_report,
        }
