"""
CRAYON STUDIO — Token-Efficient Gemini Omni 1.1 Flash & Nano Banana 2.1 Storyboard Engine

Powered by the official `google-genai >= 2.30.1` Interactions API:
1. Keyframe Generation via `gemini-nano-banana-2.1` (and `gemini-3.1-flash-lite-image` fast option)
2. Generative Video via `gemini-omni-1.1-flash` with:
   - 3 Token-Efficient Render Modes (`smart_hybrid`, `full_omni`, `keyframe_only`)
   - Multi-Turn Continuity (`previous_interaction_id`)
   - First-Frame (`<FIRST_FRAME>`) & Seamless Loop Last-Frame (`<LAST_FRAME>`) Interpolation
   - Dual-Beat 10s Timecoded Batching (`[0-5s] ... [5-10s] ...`) to cut video API calls by 50%
   - 720p default generation for token/speed efficiency (upscaled to 1080p in FFmpegCompositor)
3. Content-Addressable SHA-256 Scene Caching (`scene_hash` in `storyboard.json`) so only modified
   scenes regenerate when prompts or visual revisions are applied.
"""

from __future__ import annotations

import base64
import hashlib
import json
import logging
import math
import os
import re
import shutil
import subprocess
import threading
import time
from typing import Any, Callable, Dict, List, Optional, Tuple

import cv2
import numpy as np
from PIL import Image

logger = logging.getLogger("crayon_studio.storyboard_engine")

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DEFAULT_CONFIG_PATH = os.path.join(BASE_DIR, "config.json")


FAL_WAN_T2V_ENDPOINT = "fal-ai/wan-t2v"
FAL_WAN_I2V_ENDPOINT = "fal-ai/wan-i2v"
FAL_WAN_NEGATIVE_PROMPT = "blurry, low quality, jpeg artifacts, deformed, extra limbs, subtitles, text, watermark, flicker"
_INFLIGHT_CLIPS: set = set()
_INFLIGHT_LOCK = threading.Lock()


class AIStoryboardEngine:
    """Token-efficient AI Storyboard, Keyframe (`gemini-nano-banana-2.1`), and Video (`gemini-omni-1.1-flash`) Engine."""

    STYLE_DNA_PRESETS: Dict[str, str] = {
        "3D_Pixar": (
            "3D Pixar and Zack D. Films style educational cutaway animation, tactile clay and brushed metal materials "
            "with subsurface scattering, volumetric studio lighting, vibrant saturated palette, vertical 9:16 composition, "
            "upper two-thirds subject framing, strictly no text, no words, no letters, no watermark."
        ),
        "3D_Teardown": (
            "Exploded-view 3D isometric CAD mechanical engineering teardown illustration, precision brushed steel, "
            "copper windings, translucent X-ray polycarbonate housing, glowing cyan and amber energy pathways, "
            "sleek dark studio background, vertical 9:16 composition, strictly no text, no words, no letters, no watermark."
        ),
        "2D_Kurzgesagt": (
            "2D Kurzgesagt and stylized vector storybook illustration, crisp geometric layered shapes, vibrant neon-accented "
            "color palette against deep rich background, atmospheric glow, clean educational diagram aesthetic, "
            "vertical 9:16 composition, strictly no text, no words, no letters, no watermark."
        ),
        "Custom_Style": (
            "High-craft educational animation locked to the provided reference aesthetic, rich volumetric lighting, "
            "vertical 9:16 composition, strictly no text, no words, no letters, no watermark."
        ),
    }
    # Legacy alias compatibility
    STYLE_DNA_PRESETS["2D_Crayon"] = STYLE_DNA_PRESETS["3D_Pixar"]

    CAMERA_ANGLES = [
        "Macro exterior establishing hero shot with dramatic volumetric rim lighting",
        "Isometric 3D cutaway cross-section slicing open the outer housing to reveal internal parts",
        "Dynamic close-up tracking shot following the internal force vector and energy transfer",
        "Microscopic internal chamber view showing the core physical mechanism reacting in real time",
        "High-contrast stress-test view highlighting load pathways and structural precision",
        "Seamless visual loop framing that transitions back into the opening hero perspective",
    ]

    def __init__(
        self,
        config_path: str = DEFAULT_CONFIG_PATH,
        gemini_api_key: Optional[str] = None,
    ):
        self.config_path = config_path if os.path.isabs(config_path) else os.path.join(BASE_DIR, config_path)
        self.gemini_api_key = (gemini_api_key or os.environ.get("GEMINI_API_KEY", "")).strip()
        self.ffmpeg_path = "ffmpeg"
        self.image_model = "gemini-nano-banana-2.1"
        self.omni_resolution = "720p"
        self.fal_key = os.environ.get("FAL_KEY", "").strip()
        self.video_duration = int(os.environ.get("VIDEO_DURATION", "10"))
        self.video_resolution = os.environ.get("VIDEO_RESOLUTION", "720p")
        self.video_aspect_ratio = os.environ.get("VIDEO_ASPECT_RATIO", "9:16")

        if os.path.exists(self.config_path):
            try:
                with open(self.config_path, "r", encoding="utf-8") as f:
                    cfg = json.load(f)
                    if not self.gemini_api_key:
                        self.gemini_api_key = str(cfg.get("gemini_api_key", "")).strip()
                    self.ffmpeg_path = cfg.get("ffmpeg_path", "ffmpeg") or "ffmpeg"
                    self.image_model = cfg.get("image_model", "gemini-nano-banana-2.1") or "gemini-nano-banana-2.1"
                    self.omni_resolution = cfg.get("omni_resolution", "720p") or "720p"
            except Exception:
                pass

    @staticmethod
    def compute_scene_hash(
        prompt: str,
        omni_prompt: str,
        style_dna: str,
        visual_engine: str,
        effective_mode: str,
        duration: float,
        revision_note: str = "",
        style_reference_path: str = "",
    ) -> str:
        """Compute deterministic SHA-256 hash for content-addressable scene caching."""
        payload = {
            "prompt": prompt.strip(),
            "omni_prompt": omni_prompt.strip(),
            "style_dna": style_dna.strip(),
            "visual_engine": visual_engine,
            "effective_mode": effective_mode,
            "duration_bucket": round(float(duration), 1),
            "revision_note": revision_note.strip(),
            "style_ref": os.path.abspath(style_reference_path) if style_reference_path else "",
        }
        raw = json.dumps(payload, sort_keys=True, ensure_ascii=True).encode("utf-8")
        return hashlib.sha256(raw).hexdigest()[:16]

    @staticmethod
    def resolve_effective_scene_mode(
        scene_idx: int,
        total_scenes: int,
        project_render_mode: str = "smart_hybrid",
        scene_mode_override: str = "auto",
    ) -> str:
        """Determine whether a scene should render as 'omni_video' or 'keyframe'.

        - If scene_mode_override is explicitly 'omni_video' or 'keyframe', honor it.
        - Otherwise resolve from project_render_mode:
            * 'full_omni' -> 'omni_video' for all scenes
            * 'keyframe_only' -> 'keyframe' for all scenes
            * 'smart_hybrid' -> 'omni_video' for Scene 1 (Hook, idx 0) and Climax (idx total//2),
              and 'keyframe' for exposition beats (cuts Omni token cost by ~65%).
        """
        if scene_mode_override in ("omni_video", "keyframe"):
            return scene_mode_override

        if project_render_mode == "full_omni":
            return "omni_video"
        if project_render_mode == "keyframe_only":
            return "keyframe"

        # Default: smart_hybrid
        climax_idx = max(1, total_scenes // 2)
        if scene_idx in (0, climax_idx):
            return "omni_video"
        return "keyframe"

    @staticmethod
    def _encode_image_part(image_path: str) -> Optional[Dict[str, str]]:
        """Encode a local image as an inline base64 part for Interactions API."""
        if not image_path or not os.path.exists(image_path):
            return None
        try:
            ext = os.path.splitext(image_path)[1].lower()
            mime = "image/jpeg" if ext in (".jpg", ".jpeg") else "image/webp" if ext == ".webp" else "image/png"
            with open(image_path, "rb") as f:
                b64 = base64.b64encode(f.read()).decode("ascii")
            return {"type": "image", "data": b64, "mime_type": mime}
        except Exception:
            return None

    def extract_style_dna(
        self,
        style_image_path: Optional[str] = None,
        visual_engine: str = "3D_Pixar",
        progress_callback: Optional[Callable[[str], None]] = None,
    ) -> str:
        """Analyze a style reference image using Gemini 3.8 Flash via Interactions API, or return preset DNA."""
        preset_dna = self.STYLE_DNA_PRESETS.get(visual_engine, self.STYLE_DNA_PRESETS["3D_Pixar"])
        if not style_image_path or not os.path.exists(style_image_path):
            return preset_dna

        cached_txt = os.path.splitext(style_image_path)[0] + "_dna.txt"
        if os.path.exists(cached_txt):
            try:
                with open(cached_txt, "r", encoding="utf-8") as f:
                    dna = f.read().strip()
                    if dna:
                        return dna
            except Exception:
                pass

        if self.gemini_api_key:
            try:
                if progress_callback:
                    progress_callback("[Director] Extracting visual style DNA with Gemini 3.8 Flash...")
                from google import genai

                client = genai.Client(api_key=self.gemini_api_key)
                img_part = self._encode_image_part(style_image_path)
                if img_part:
                    prompt = (
                        "Analyze the visual artistic style of this reference image. "
                        "In 2 concise sentences, describe its lighting, material/shading style, and color palette. "
                        "End with: 'vertical 9:16 aspect ratio, strictly no text, no words, no letters, no watermark.'"
                    )
                    interaction = client.interactions.create(
                        model="gemini-3.8-flash",
                        input=[img_part, {"type": "text", "text": prompt}],
                        store=False,
                    )
                    out_txt = getattr(interaction, "output_text", "")
                    if out_txt:
                        dna = out_txt.strip().replace("\n", " ")
                        try:
                            with open(cached_txt, "w", encoding="utf-8") as f:
                                f.write(dna)
                        except Exception:
                            pass
                        return dna
            except Exception as e:
                if progress_callback:
                    progress_callback(f"[Director] Style reference note ({e}). Using preset DNA.")

        return preset_dna

    def segment_script_into_scenes(
        self,
        script_text: str,
        words_json_path: str,
        target_count: int = 6,
        default_duration: float = 65.0,
    ) -> List[Dict[str, Any]]:
        """Segment script text and Whisper word timestamps into 5 to 7 timed visual scenes."""
        words: List[Dict[str, Any]] = []
        if words_json_path and os.path.exists(words_json_path):
            try:
                with open(words_json_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    words = data if isinstance(data, list) else data.get("words", [])
            except Exception:
                words = []

        total_duration = float(words[-1].get("end", default_duration)) if words else default_duration
        target_count = max(4, min(8, target_count))

        # Check if words_json matches current script_text reasonably well; if script was edited
        # significantly since words_json was generated, segment directly from script_text sentences
        script_words = [w.strip() for w in script_text.split() if w.strip()]
        if not words or (script_words and abs(len(words) - len(script_words)) > max(20, len(script_words) * 0.35)):
            sentences = [s.strip() for s in re.split(r"(?<=[.!?])\s+", script_text.strip()) if s.strip()]
            if not sentences:
                sentences = [script_text.strip() or "Educational animation sequence."]

            chunk_size = max(1, math.ceil(len(sentences) / target_count))
            scenes = []
            for i in range(0, len(sentences), chunk_size):
                chunk = sentences[i : i + chunk_size]
                s_time = (i / len(sentences)) * total_duration
                e_time = min(total_duration, ((i + len(chunk)) / len(sentences)) * total_duration)
                scenes.append({
                    "scene_idx": len(scenes),
                    "start_time": round(s_time, 2),
                    "end_time": round(e_time, 2),
                    "duration": round(max(3.0, e_time - s_time), 2),
                    "script_excerpt": " ".join(chunk),
                })
            return scenes

        scenes = []
        target_dur = total_duration / target_count
        boundary_indices = []

        curr_start = 0
        for s_idx in range(1, target_count):
            ideal_time = s_idx * target_dur
            best_idx = None
            best_diff = float("inf")

            for w_idx in range(curr_start + 6, max(curr_start + 7, len(words) - 6)):
                if w_idx >= len(words):
                    break
                w = words[w_idx]
                w_text = str(w.get("word", ""))
                w_end = float(w.get("end", 0.0))
                diff = abs(w_end - ideal_time)

                if any(w_text.endswith(p) for p in (".", "!", "?")):
                    score = diff * 0.4
                elif any(w_text.endswith(p) for p in (",", ";", "—", ":")):
                    score = diff * 0.8
                else:
                    score = diff * 1.5

                if score < best_diff:
                    best_diff = score
                    best_idx = w_idx

            if best_idx is not None and best_idx not in boundary_indices:
                boundary_indices.append(best_idx)
                curr_start = best_idx

        slices = [0] + sorted(boundary_indices) + [len(words)]
        for i in range(len(slices) - 1):
            w_slice = words[slices[i] : slices[i + 1]]
            if not w_slice:
                continue
            s_time = float(w_slice[0].get("start", 0.0))
            e_time = float(w_slice[-1].get("end", total_duration))
            excerpt = " ".join(str(w.get("word", "")).strip() for w in w_slice).strip()
            scenes.append({
                "scene_idx": len(scenes),
                "start_time": round(s_time, 2),
                "end_time": round(e_time, 2),
                "duration": round(max(3.0, e_time - s_time), 2),
                "script_excerpt": excerpt,
            })

        return scenes

    def _synthesize_fallback_action(self, excerpt: str, scene_idx: int, category: str, visual_engine: str) -> str:
        """Topic-adaptive scene action synthesis derived directly from the scene's script excerpt."""
        angle = self.CAMERA_ANGLES[scene_idx % len(self.CAMERA_ANGLES)]
        clean_excerpt = re.sub(r"[^a-zA-Z0-9 ,.-]", "", excerpt).strip()
        short_focus = " ".join(clean_excerpt.split()[:18]).rstrip(".,;:!-")
        style_hint = (
            "exploded 3D CAD mechanical assembly"
            if visual_engine == "3D_Teardown"
            else "stylized 2D Kurzgesagt vector cutaway"
            if visual_engine == "2D_Kurzgesagt"
            else "3D Pixar educational cutaway"
        )
        return f"{angle} in {style_hint} style depicting: {short_focus}"

    def build_scene_prompts(
        self,
        scenes: List[Dict[str, Any]],
        category: str = "STEM",
        visual_engine: str = "3D_Pixar",
        render_mode: str = "smart_hybrid",
        style_dna: Optional[str] = None,
        visual_revision_prompt: str = "",
        existing_scenes: Optional[List[Dict[str, Any]]] = None,
        style_reference_path: str = "",
    ) -> List[Dict[str, Any]]:
        """Choreograph concrete, concise scene prompts for each beat of the script.

        - Uses `gemini-3.8-flash` via Interactions API with structured JSON output.
        - Applies `visual_revision_prompt` if provided by the user.
        - Preserves manual per-scene prompt/mode edits from `existing_scenes` when the excerpt matches
          and no overriding `visual_revision_prompt` was issued.
        """
        dna = style_dna or self.STYLE_DNA_PRESETS.get(visual_engine, self.STYLE_DNA_PRESETS["3D_Pixar"])
        total = len(scenes)
        rev_clean = visual_revision_prompt.strip()

        # Map existing scenes by index so user customizations in the Storyboard Inspector are respected
        existing_by_idx: Dict[int, Dict[str, Any]] = {}
        if existing_scenes:
            for esc in existing_scenes:
                if isinstance(esc, dict) and "scene_idx" in esc:
                    existing_by_idx[int(esc["scene_idx"])] = esc

        ai_action_descs: List[str] = []
        need_ai_choreography = any(
            idx not in existing_by_idx
            or existing_by_idx[idx].get("script_excerpt", "").strip() != sc.get("script_excerpt", "").strip()
            or bool(rev_clean)
            for idx, sc in enumerate(scenes)
        )

        if self.gemini_api_key and need_ai_choreography:
            try:
                from google import genai

                client = genai.Client(api_key=self.gemini_api_key)
                excerpts = [sc.get("script_excerpt", "") for sc in scenes]
                rev_directive = (
                    f"\nUSER VISUAL REVISION INSTRUCTION TO APPLY ACROSS SCENES: '{rev_clean}'\n"
                    if rev_clean
                    else ""
                )
                schema = {
                    "type": "object",
                    "properties": {
                        "scene_actions": {
                            "type": "array",
                            "items": {"type": "string"},
                        }
                    },
                    "required": ["scene_actions"],
                }
                prompt_ai = (
                    f"You are an animation director for a {visual_engine} ({category}) vertical 9:16 short.\n"
                    f"For each of the {total} script excerpts below, write a concise (18-28 words), concrete physical visual action "
                    "description showing what is happening on screen.\n"
                    "CRITICAL RULES:\n"
                    "1. Each scene MUST use a distinct camera angle and visual focal point directly matching its script excerpt.\n"
                    "2. Keep subjects in the upper two-thirds of the vertical frame so the bottom 35% stays clean for captions.\n"
                    "3. Never include on-screen text or labels.\n"
                    f"{rev_directive}"
                    f"Script Excerpts: {json.dumps(excerpts, ensure_ascii=False)}"
                )
                from core.usage_tracker import usage_tracker

                interaction = client.interactions.create(
                    model="gemini-3.8-flash",
                    input=prompt_ai,
                    store=False,
                    response_format={
                        "type": "text",
                        "mime_type": "application/json",
                        "schema": schema,
                    },
                )
                out_txt = getattr(interaction, "output_text", "")
                if out_txt:
                    usage_tracker.record_interaction(
                        "gemini-3.8-flash",
                        "scene_choreography",
                        interaction,
                        prompt_chars=len(prompt_ai),
                        output_chars=len(out_txt),
                    )
                    parsed = json.loads(out_txt)
                    actions = parsed.get("scene_actions", [])
                    if isinstance(actions, list) and len(actions) == total:
                        ai_action_descs = [str(a).strip() for a in actions]
            except Exception as e:
                from core.usage_tracker import usage_tracker

                usage_tracker.record_error("gemini-3.8-flash", "scene_choreography", e)
                logger.warning("Gemini scene choreography note (%s). Using topic-adaptive choreographer.", e)

        enhanced_scenes: List[Dict[str, Any]] = []
        for idx, sc in enumerate(scenes):
            excerpt = sc.get("script_excerpt", "")
            prev = existing_by_idx.get(idx, {})
            same_excerpt = prev.get("script_excerpt", "").strip() == excerpt.strip()

            # Preserve user-edited action/prompt if excerpt is unchanged and no global visual revision was triggered
            if same_excerpt and prev.get("user_edited") and not rev_clean:
                action_desc = prev.get("action_desc", "")
                prompt = prev.get("prompt", "")
                omni_prompt = prev.get("omni_prompt", prompt)
            else:
                if idx < len(ai_action_descs) and ai_action_descs[idx]:
                    action_desc = ai_action_descs[idx]
                elif same_excerpt and prev.get("action_desc"):
                    action_desc = prev["action_desc"]
                else:
                    action_desc = self._synthesize_fallback_action(excerpt, idx, category, visual_engine)

                if rev_clean and rev_clean.lower() not in action_desc.lower():
                    action_desc = f"{action_desc}. Visual modification: {rev_clean}"

                # Concise, token-efficient prompts (avoids bloated repetition)
                prompt = f"{action_desc}. {dna}"
                omni_prompt = (
                    f"Single continuous vertical 9:16 shot: {action_desc}. "
                    f"{dna} Smooth physical motion. No dialogue. No text."
                )

            scene_mode_override = prev.get("render_mode", "auto")
            effective_mode = self.resolve_effective_scene_mode(
                scene_idx=idx,
                total_scenes=total,
                project_render_mode=render_mode,
                scene_mode_override=scene_mode_override,
            )
            revision_note = rev_clean or prev.get("revision_note", "")

            scene_hash = self.compute_scene_hash(
                prompt=prompt,
                omni_prompt=omni_prompt,
                style_dna=dna,
                visual_engine=visual_engine,
                effective_mode=effective_mode,
                duration=sc.get("duration", 8.0),
                revision_note=revision_note,
                style_reference_path=style_reference_path,
            )

            sc_copy = dict(sc)
            sc_copy.update({
                "concept_title": f"Scene {idx + 1}/{total}",
                "action_desc": action_desc,
                "prompt": prompt,
                "omni_prompt": omni_prompt,
                "render_mode": scene_mode_override,
                "effective_mode": effective_mode,
                "revision_note": revision_note,
                "scene_hash": scene_hash,
                "user_edited": bool(prev.get("user_edited", False) and not rev_clean),
                "image_path": prev.get("image_path", ""),
                "video_clip_path": prev.get("video_clip_path", ""),
            })
            enhanced_scenes.append(sc_copy)

        return enhanced_scenes

    def generate_clean_fallback_card(
        self,
        output_path: str,
        scene_idx: int = 0,
        category: str = "STEM",
        action_desc: str = "",
        visual_engine: str = "3D_Pixar",
    ) -> str:
        """High-detail procedural schematic & 3D cutaway canvas when completely offline."""
        w, h = 1080, 1920
        act_lower = (action_desc + " " + category + " " + visual_engine).lower()

        if visual_engine == "3D_Teardown" or any(k in act_lower for k in ["teardown", "cad", "motor", "engine", "piezo", "gear"]):
            c_top, c_mid, c_bot = (28, 20, 14), (95, 65, 25), (18, 12, 10)
            accent_bgr = (255, 210, 40)
            secondary_bgr = (60, 180, 255)
        elif any(k in act_lower for k in ["heat", "melt", "furnace", "fire", "lava", "spark", "volt"]):
            c_top, c_mid, c_bot = (16, 12, 28), (35, 85, 200), (12, 18, 42)
            accent_bgr = (80, 190, 255)
            secondary_bgr = (255, 210, 90)
        elif any(k in act_lower for k in ["ocean", "water", "sea", "wave", "concrete", "fluid"]):
            c_top, c_mid, c_bot = (46, 24, 12), (140, 100, 28), (26, 14, 8)
            accent_bgr = (230, 215, 80)
            secondary_bgr = (140, 240, 170)
        else:
            c_top, c_mid, c_bot = (36, 18, 24), (115, 55, 75), (20, 10, 14)
            accent_bgr = (255, 195, 95)
            secondary_bgr = (150, 120, 255)

        # Vectorized vertical gradient construction (fast NumPy broadcasting)
        y_vals = np.linspace(0.0, 1.0, h, dtype=np.float32)[:, None]
        base = np.zeros((h, w, 3), dtype=np.uint8)
        top_mask = y_vals < 0.55
        r_top = np.clip(y_vals / 0.55, 0.0, 1.0)
        r_bot = np.clip((y_vals - 0.55) / 0.45, 0.0, 1.0)
        for ch in range(3):
            col_line = np.where(
                top_mask,
                c_top[ch] * (1.0 - r_top) + c_mid[ch] * r_top,
                c_mid[ch] * (1.0 - r_bot) + c_bot[ch] * r_bot,
            )
            base[:, :, ch] = np.clip(col_line, 0, 255).astype(np.uint8)

        # Volumetric radial spotlight in upper-middle (cx=540, cy=660)
        cx, cy = w // 2, 660
        y_grid, x_grid = np.ogrid[:h, :w]
        dist = np.sqrt((x_grid - cx) ** 2 + (y_grid - cy) ** 2)
        spotlight = (np.clip(1.0 - dist / 600.0, 0.0, 1.0) ** 2.0) * 85.0
        for ch in range(3):
            base[:, :, ch] = np.clip(base[:, :, ch].astype(np.float32) + spotlight, 0, 255).astype(np.uint8)

        # Draw subtle isometric engineering grid & concentric cutaway geometry in upper 60%
        overlay = base.copy()
        for rad in (140, 230, 320):
            cv2.circle(overlay, (cx, cy), rad, accent_bgr, 2, lineType=cv2.LINE_AA)
        for angle_deg in range(0, 360, 30):
            rad_ang = math.radians(angle_deg + scene_idx * 15)
            x1 = int(cx + 90 * math.cos(rad_ang))
            y1 = int(cy + 90 * math.sin(rad_ang))
            x2 = int(cx + 340 * math.cos(rad_ang))
            y2 = int(cy + 340 * math.sin(rad_ang))
            cv2.line(overlay, (x1, y1), (x2, y2), secondary_bgr, 2, lineType=cv2.LINE_AA)

        # Isometric core polygon
        poly_pts = []
        sides = 6
        for k in range(sides):
            a = math.radians(k * 60 + scene_idx * 20)
            poly_pts.append([int(cx + 150 * math.cos(a)), int(cy + 150 * math.sin(a))])
        cv2.polylines(overlay, [np.array(poly_pts, dtype=np.int32)], True, (255, 255, 255), 3, lineType=cv2.LINE_AA)
        cv2.addWeighted(overlay, 0.38, base, 0.62, 0, base)

        # Ambient floating bokeh particles
        rng = np.random.default_rng(42 + scene_idx * 17)
        for _ in range(32):
            px = int(rng.integers(50, w - 50))
            py = int(rng.integers(80, 1140))
            rad = int(rng.integers(3, 12))
            cv2.circle(base, (px, py), rad, (235, 245, 255), -1, lineType=cv2.LINE_AA)

        os.makedirs(os.path.dirname(os.path.abspath(output_path)), exist_ok=True)
        cv2.imwrite(output_path, base)
        return output_path

    def generate_scene_image(
        self,
        prompt: str,
        output_path: str,
        seed: int = 42,
        scene_idx: int = 0,
        action_desc: str = "",
        category: str = "STEM",
        visual_engine: str = "3D_Pixar",
        style_reference_path: Optional[str] = None,
        force_regenerate: bool = False,
        progress_callback: Optional[Callable[[str], None]] = None,
    ) -> str:
        """Generate 9:16 keyframe image using `gemini-nano-banana-2.1` via Interactions API."""
        if not force_regenerate and os.path.exists(output_path) and os.path.getsize(output_path) > 10000:
            return output_path

        os.makedirs(os.path.dirname(os.path.abspath(output_path)), exist_ok=True)

        if self.gemini_api_key and not getattr(self, "_credits_exhausted", False):
            try:
                from google import genai

                client = genai.Client(api_key=self.gemini_api_key)
                clean_prompt = prompt[:950]

                # Build multimodal input (attach style reference image if configured)
                ref_part = self._encode_image_part(style_reference_path) if style_reference_path else None
                if ref_part:
                    input_payload: Any = [
                        ref_part,
                        {"type": "text", "text": f"Match the visual art style of this reference image: {clean_prompt}"},
                    ]
                else:
                    input_payload = clean_prompt

                # Prioritize user-configured Nano Banana model, then fast Nano Banana 2 Lite, then Nano Banana Pro
                models_to_try = []
                for m in (self.image_model, "gemini-nano-banana-2.1", "gemini-3.1-flash-lite-image", "gemini-3-pro-image"):
                    if m and m not in models_to_try:
                        models_to_try.append(m)

                for img_model in models_to_try:
                    try:
                        if progress_callback:
                            progress_callback(f"[Nano Banana] Generating Scene {scene_idx + 1} keyframe with {img_model}...")

                        interaction = client.interactions.create(
                            model=img_model,
                            input=input_payload,
                            store=False,
                            response_format={
                                "type": "image",
                                "aspect_ratio": "9:16",
                            },
                        )

                        img_bytes = None
                        out_img = getattr(interaction, "output_image", None)
                        if out_img and getattr(out_img, "data", None):
                            raw_data = out_img.data
                            img_bytes = base64.b64decode(raw_data) if isinstance(raw_data, str) else raw_data

                        if img_bytes and len(img_bytes) > 5000:
                            from core.usage_tracker import usage_tracker

                            usage_tracker.record_interaction(
                                img_model,
                                f"keyframe_scene_{scene_idx + 1}",
                                interaction,
                                images_generated=1,
                            )
                            with open(output_path, "wb") as f:
                                f.write(img_bytes)
                            self._last_image_generated = True
                            with Image.open(output_path) as im:
                                if im.size != (1080, 1920):
                                    im = im.resize((1080, 1920), Image.Resampling.LANCZOS)
                                    im.save(output_path)
                            if progress_callback:
                                progress_callback(f"[OK] Scene {scene_idx + 1} keyframe generated via {img_model}.")
                            return output_path
                    except Exception as mod_err:
                        from core.usage_tracker import usage_tracker

                        usage_tracker.record_error(img_model, f"keyframe_scene_{scene_idx + 1}", mod_err)
                        err_str = str(mod_err)
                        if "402" in err_str or "prepayment credits are depleted" in err_str.lower():
                            self._credits_exhausted = True
                            if progress_callback:
                                progress_callback(
                                    "[Billing Notice] Gemini prepayment credits depleted (HTTP 402) — switching remaining scenes to procedural 3D schematic keyframes."
                                )
                            break
                        if progress_callback:
                            progress_callback(f"[Nano Banana] {img_model} note: {mod_err}")
            except Exception as e:
                if progress_callback:
                    progress_callback(f"[Nano Banana] API note ({e}). Using procedural schematic card.")

        if progress_callback:
            progress_callback(f"[Storyboard] Scene {scene_idx + 1}: Rendering procedural 3D schematic keyframe.")
        return self.generate_clean_fallback_card(
            output_path=output_path,
            scene_idx=scene_idx,
            category=category,
            action_desc=action_desc,
            visual_engine=visual_engine,
        )

    def _wan_segment(
        self,
        prompt: str,
        image_path: Optional[str],
        out_path: str,
        num_frames: int,
        fps: int,
    ) -> bool:
        """One fal.ai Wan call. Image-to-video when an image is given (keeps the keyframe's style)."""
        import fal_client
        import requests

        args: Dict[str, Any] = {
            "prompt": prompt,
            "num_frames": num_frames,
            "frames_per_second": fps,
            "resolution": self.video_resolution,
            "aspect_ratio": self.video_aspect_ratio,
        }
        endpoint = FAL_WAN_T2V_ENDPOINT
        if image_path and os.path.exists(image_path):
            args["image_url"] = fal_client.upload_file(image_path)
            # fal's default negative prompt contains "style, artwork, painting", which
            # fights stylized (Pixar/cartoon) keyframes -- override it.
            args["negative_prompt"] = FAL_WAN_NEGATIVE_PROMPT
            endpoint = FAL_WAN_I2V_ENDPOINT
        result = fal_client.subscribe(endpoint, arguments=args)
        url = (result.get("video") or {}).get("url")
        if not url:
            return False
        resp = requests.get(url, timeout=300)
        resp.raise_for_status()
        if len(resp.content) <= 10000:
            return False
        os.makedirs(os.path.dirname(os.path.abspath(out_path)), exist_ok=True)
        with open(out_path, "wb") as f:
            f.write(resp.content)
        return True

    def _chain_wan_segments(self, segments: List[str], out_path: str, total_sec: float) -> bool:
        """Concatenate Wan segments with FFmpeg and trim to `total_sec`."""
        list_file = out_path + ".concat.txt"
        try:
            with open(list_file, "w", encoding="utf-8") as f:
                for seg in segments:
                    f.write(f"file '{os.path.abspath(seg).replace(chr(92), '/')}'\n")
            cmd = [
                self.ffmpeg_path, "-y", "-f", "concat", "-safe", "0", "-i", list_file,
                "-t", f"{total_sec:.2f}", "-c:v", "libx264", "-pix_fmt", "yuv420p", "-an", out_path,
            ]
            subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=False)
            return os.path.exists(out_path) and os.path.getsize(out_path) > 10000
        finally:
            if os.path.exists(list_file):
                os.remove(list_file)

    def generate_ai_video_clip(
        self,
        scene_prompt: str,
        start_image_path: Optional[str],
        output_clip_path: str,
        duration_sec: float = 8.0,
        last_image_path: Optional[str] = None,
        previous_interaction_id: Optional[str] = None,
        gemini_api_key: Optional[str] = None,
        force_regenerate: bool = False,
        progress_callback: Optional[Callable[[str], None]] = None,
    ) -> Tuple[bool, Optional[str]]:
        """Generate a vertical (9:16, TikTok/Reels/Shorts) AI clip via fal.ai Wan.

        Only the clean scene prompt is sent (no chat history / system prompt). When a keyframe
        exists it uses Wan image-to-video (keyframe = first frame) so the project style stays
        consistent; otherwise text-to-video. One Wan call yields <= ~6.25s, so longer clips
        (up to VIDEO_DURATION, default 10s) chain segments: each next segment starts from the
        previous segment's last frame, then FFmpeg joins and trims them.
        Last-frame and multi-turn args are accepted but ignored.
        Duplicate in-flight requests for the same output clip are rejected.
        """
        if not force_regenerate and os.path.exists(output_clip_path) and os.path.getsize(output_clip_path) > 20000:
            if progress_callback:
                progress_callback(f"[Cache Hit] Reusing cached video clip: {os.path.basename(output_clip_path)}")
            return True, previous_interaction_id

        if not self.fal_key:
            return False, previous_interaction_id

        key = os.path.abspath(output_clip_path)
        with _INFLIGHT_LOCK:
            if key in _INFLIGHT_CLIPS:
                if progress_callback:
                    progress_callback(f"[Wan] Already generating {os.path.basename(output_clip_path)}; skipping duplicate.")
                return False, previous_interaction_id
            _INFLIGHT_CLIPS.add(key)

        segs: List[str] = []
        try:
            os.environ.setdefault("FAL_KEY", self.fal_key)
            fps = 16
            max_frames = 100
            total_sec = max(3.0, min(float(duration_sec), float(self.video_duration)))
            n_segs = max(1, math.ceil(total_sec / (max_frames / fps)))
            prompt = scene_prompt.strip()[:950]
            image = start_image_path
            for i in range(n_segs):
                remaining = total_sec - i * (max_frames / fps)
                frames = max(81, min(max_frames, int(round(remaining * fps))))
                seg_path = f"{output_clip_path}.seg{i}.mp4"
                if progress_callback:
                    progress_callback(
                        f"[Wan] Segment {i + 1}/{n_segs}: {frames / fps:.1f}s {self.video_resolution} {self.video_aspect_ratio}..."
                    )
                if not self._wan_segment(prompt, image, seg_path, frames, fps):
                    break
                segs.append(seg_path)
                if i + 1 < n_segs:
                    last_png = f"{output_clip_path}.seg{i}_last.png"
                    subprocess.run(
                        [self.ffmpeg_path, "-y", "-sseof", "-0.1", "-i", seg_path, "-frames:v", "1", last_png],
                        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=False,
                    )
                    if not os.path.exists(last_png):
                        break
                    segs_last = last_png
                    image = segs_last

            ok = False
            if len(segs) == n_segs and n_segs == 1:
                os.replace(segs[0], output_clip_path)
                segs = []
                ok = True
            elif segs:
                ok = self._chain_wan_segments(segs, output_clip_path, total_sec)
            if ok:
                if progress_callback:
                    progress_callback(
                        f"[OK] [Wan] Saved {os.path.getsize(output_clip_path) // 1024} KB clip: {os.path.basename(output_clip_path)}"
                    )
                return True, previous_interaction_id
        except Exception as e:
            if progress_callback:
                progress_callback(f"[Wan] Generation note: {e}")
        finally:
            with _INFLIGHT_LOCK:
                _INFLIGHT_CLIPS.discard(key)
            for tmp in segs + [f"{output_clip_path}.seg{i}_last.png" for i in range(4)]:
                if os.path.exists(tmp):
                    try:
                        os.remove(tmp)
                    except OSError:
                        pass

        return False, previous_interaction_id

    def ensure_style_reference(
        self,
        project_dir: str,
        script_text: str,
        visual_engine: str,
        category: str,
        style_reference_path: Optional[str],
        progress_callback: Optional[Callable[[str], None]] = None,
    ) -> Optional[str]:
        """Return the user's style reference, or auto-generate (and cache) one for the project.

        The generated `style_reference.png` is passed to every keyframe, which then seeds the
        Wan clips, so all scenes share one look. Delete the file to regenerate it.
        """
        if style_reference_path:
            return style_reference_path
        ref_path = os.path.join(project_dir, "style_reference.png")
        if os.path.exists(ref_path) and os.path.getsize(ref_path) > 10000:
            return ref_path
        if not self.gemini_api_key or getattr(self, "_credits_exhausted", False):
            return None
        if progress_callback:
            progress_callback("[Style] Generating project style reference image...")
        dna = self.STYLE_DNA_PRESETS.get(visual_engine, self.STYLE_DNA_PRESETS["3D_Pixar"])
        topic = " ".join(script_text.split())[:200]
        self._last_image_generated = False
        self.generate_scene_image(
            prompt=f"Style-guide hero frame for a short educational video about: {topic}. {dna}",
            output_path=ref_path,
            category=category,
            visual_engine=visual_engine,
            force_regenerate=True,
            progress_callback=progress_callback,
        )
        if self._last_image_generated:
            return ref_path
        # Procedural fallback card is not a usable style reference.
        if os.path.exists(ref_path):
            os.remove(ref_path)
        return None

    def generate_batched_omni_pair(
        self,
        scene_a: Dict[str, Any],
        scene_b: Dict[str, Any],
        out_clip_a: str,
        out_clip_b: str,
        previous_interaction_id: Optional[str] = None,
        progress_callback: Optional[Callable[[str], None]] = None,
    ) -> Tuple[bool, Optional[str]]:
        """Token-Efficiency Optimization: Generates TWO adjacent storyboard scenes in a SINGLE 10s
        `gemini-omni-1.1-flash` call using `[0-5s] ... [5-10s] ...` timecode syntax, then splits
        the resulting 10s MP4 into `out_clip_a` and `out_clip_b` via FFmpeg.
        """
        combined_prompt = (
            f"[0-5s] {scene_a.get('action_desc', '')}. "
            f"[5-10s] Cut to next angle: {scene_b.get('action_desc', '')}. "
            f"{self.STYLE_DNA_PRESETS.get('3D_Pixar')} No dialogue. No text."
        )
        tmp_pair_path = out_clip_a.replace(".mp4", "_pair10s.mp4")
        ok, next_inter_id = self.generate_ai_video_clip(
            scene_prompt=combined_prompt,
            start_image_path=scene_a.get("image_path"),
            output_clip_path=tmp_pair_path,
            duration_sec=10.0,
            previous_interaction_id=previous_interaction_id,
            force_regenerate=True,
            progress_callback=progress_callback,
        )
        if not ok or not os.path.exists(tmp_pair_path):
            return False, previous_interaction_id

        try:
            cmd_a = [self.ffmpeg_path, "-y", "-ss", "0", "-i", tmp_pair_path, "-t", "5", "-c", "copy", out_clip_a]
            cmd_b = [self.ffmpeg_path, "-y", "-ss", "5", "-i", tmp_pair_path, "-t", "5", "-c", "copy", out_clip_b]
            subprocess.run(cmd_a, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=False)
            subprocess.run(cmd_b, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=False)
            if os.path.exists(out_clip_a) and os.path.exists(out_clip_b):
                return True, next_inter_id
        except Exception:
            pass
        return False, next_inter_id

    def _render_physics_layer(
        self,
        frame: np.ndarray,
        f: int,
        scene_type: str,
        w: int = 1080,
        h: int = 1920,
    ) -> np.ndarray:
        """Draws 30fps active physical motion layers within the upper 60% of the frame (y < 1140)."""
        out = frame.copy()
        safe_max_y = 1140

        if scene_type == "water":
            wave_y = int(960 + 18.0 * math.sin(f * 0.12))
            pts = []
            for x in range(0, w + 40, 30):
                dy = int(14.0 * math.sin(f * 0.10 + x * 0.015) + 8.0 * math.cos(f * 0.07 + x * 0.03))
                pts.append((x, wave_y + dy))
            pts.append((w, safe_max_y))
            pts.append((0, safe_max_y))
            overlay = out.copy()
            cv2.fillPoly(overlay, [np.array(pts, dtype=np.int32)], (225, 175, 50))
            cv2.addWeighted(overlay, 0.25, out, 0.75, 0, out)

        elif scene_type == "crystal":
            cx, cy = 540, 640
            growth = min(1.0, f / 90.0)
            for cid in range(10):
                ang = cid * (math.pi / 5.0)
                dist = int((60 + (cid % 4) * 35) * growth)
                px = int(cx + dist * math.cos(ang))
                py = int(cy + dist * math.sin(ang))
                sz = int((22 + (cid % 3) * 10) * growth)
                pts = np.array([[px, py - sz], [px + int(sz * 0.8), py], [px, py + sz], [px - int(sz * 0.8), py]], dtype=np.int32)
                overlay = out.copy()
                cv2.fillPoly(overlay, [pts], (130, 230, 40))
                cv2.addWeighted(overlay, 0.35, out, 0.65, 0, out)

        elif scene_type == "ash":
            for pid in range(24):
                drift_x = math.sin(f * 0.05 + pid) * 25
                y = int((950 - (f * 1.8 + pid * 38)) % 800 + 200)
                x = int((pid * 39 + drift_x) % (w - 120) + 60)
                if 180 < y < safe_max_y:
                    r = (pid % 3) + 2
                    col = (40, 160, 250) if pid % 2 == 0 else (220, 235, 245)
                    cv2.circle(out, (x, y), r, col, -1)

        else:
            for bid in range(12):
                bx = int((bid * 83 + math.sin(f * 0.03 + bid) * 30) % (w - 160) + 80)
                by = int((bid * 67 + math.cos(f * 0.02 + bid) * 25) % 750 + 200)
                br = int(14 + (bid % 4) * 6)
                overlay = out.copy()
                cv2.circle(overlay, (bx, by), br, (255, 220, 150), -1)
                cv2.addWeighted(overlay, 0.10, out, 0.90, 0, out)

        return out

    def animate_storyboard(
        self,
        scenes_data: List[Dict[str, Any]],
        output_mp4_path: str,
        fps: int = 30,
        progress_callback: Optional[Callable[[str], None]] = None,
    ) -> str:
        """Composite 30fps video pass from Omni video clips and/or Nano Banana 2.5D keyframes."""
        w, h = 1080, 1920
        os.makedirs(os.path.dirname(os.path.abspath(output_mp4_path)), exist_ok=True)

        fourcc = cv2.VideoWriter_fourcc(*"mp4v")
        writer = cv2.VideoWriter(output_mp4_path, fourcc, float(fps), (w, h))
        if not writer.isOpened():
            raise RuntimeError(f"Could not open OpenCV VideoWriter for: {output_mp4_path}")

        loaded_scenes = []
        for sc in scenes_data:
            dur = max(2.0, float(sc.get("duration", 8.0)))
            num_frames = int(round(dur * fps))
            video_clip_path = sc.get("video_clip_path")
            img_path = sc.get("image_path")

            ex_text = (sc.get("script_excerpt", "") + " " + sc.get("action_desc", "")).lower()
            if any(k in ex_text for k in ["ocean", "wave", "water", "splash", "brine", "fluid"]):
                phys_type = "water"
            elif any(k in ex_text for k in ["crystal", "tobermorite", "interlock", "grow", "lattice"]):
                phys_type = "crystal"
            elif any(k in ex_text for k in ["ash", "lime", "pozzolana", "volcanic", "spark", "electron"]):
                phys_type = "ash"
            else:
                phys_type = "general"

            loaded_scenes.append({
                "scene_idx": sc.get("scene_idx", 0),
                "duration": dur,
                "total_frames": num_frames,
                "video_clip_path": video_clip_path if (video_clip_path and os.path.exists(video_clip_path) and os.path.getsize(video_clip_path) > 10000) else None,
                "img_path": img_path,
                "phys_type": phys_type,
            })

        total_project_frames = max(1, sum(s["total_frames"] for s in loaded_scenes))
        frames_rendered = 0
        trans_len = 15

        t_start = time.time()
        for idx, sc in enumerate(loaded_scenes):
            num_frames = sc["total_frames"]
            phys_type = sc["phys_type"]

            if sc["video_clip_path"]:
                cap = cv2.VideoCapture(sc["video_clip_path"])
                clip_frames = []
                while True:
                    ret, fr = cap.read()
                    if not ret:
                        break
                    if fr.shape[0] != h or fr.shape[1] != w:
                        fr = cv2.resize(fr, (w, h), interpolation=cv2.INTER_LANCZOS4)
                    clip_frames.append(fr)
                cap.release()

                if not clip_frames:
                    clip_frames = [np.zeros((h, w, 3), dtype=np.uint8)]

                next_start_frame = self._peek_next_scene_first_frame(loaded_scenes, idx, w, h)
                for f in range(num_frames):
                    pos = int(f * (len(clip_frames) / float(num_frames)))
                    fr = clip_frames[min(len(clip_frames) - 1, pos)].copy()
                    if next_start_frame is not None and f >= (num_frames - trans_len):
                        alpha = (f - (num_frames - trans_len)) / float(trans_len)
                        fr = cv2.addWeighted(fr, 1.0 - alpha, next_start_frame, alpha, 0)
                    writer.write(fr)
                    frames_rendered += 1
                continue

            img_path = sc["img_path"]
            img = cv2.imread(img_path) if (img_path and os.path.exists(img_path)) else None
            if img is None:
                img = np.full((h, w, 3), (36, 22, 16), dtype=np.uint8)
            if img.shape[0] != h or img.shape[1] != w:
                img = cv2.resize(img, (w, h), interpolation=cv2.INTER_LANCZOS4)

            next_img = self._peek_next_scene_first_frame(loaded_scenes, idx, w, h)

            # Cinematic Ken Burns trajectory parameters per scene (direction changes dynamically)
            scene_dir = idx % 4
            for f in range(num_frames):
                progress = f / float(max(1, num_frames))
                # Dynamic zoom from 1.0 to 1.18 (or 1.18 to 1.05)
                if scene_dir in (0, 2):
                    zoom = 1.02 + 0.16 * progress
                else:
                    zoom = 1.18 - 0.12 * progress

                # Dynamic camera pan and tilt (X: -35px to +35px, Y: -50px to +50px)
                if scene_dir == 0:     # Pan right and tilt slightly up
                    center_x = 540 + int(35 * progress)
                    center_y = 960 - int(45 * progress)
                elif scene_dir == 1:   # Pan left and push in
                    center_x = 540 - int(35 * progress)
                    center_y = 960 + int(30 * progress)
                elif scene_dir == 2:   # Tilt down (reveal)
                    center_x = 540 + int(20 * (progress - 0.5))
                    center_y = 960 + int(55 * progress)
                else:                  # Subtle diagonal pull-back
                    center_x = 540 - int(30 * progress)
                    center_y = 960 - int(40 * progress)

                M = cv2.getRotationMatrix2D((center_x, center_y), 0.0, zoom)
                frame_canvas = cv2.warpAffine(img, M, (w, h), flags=cv2.INTER_LINEAR, borderMode=cv2.BORDER_REFLECT)
                frame_canvas = self._render_physics_layer(frame_canvas, f, phys_type, w=w, h=h)

                if next_img is not None and f >= (num_frames - trans_len):
                    alpha = (f - (num_frames - trans_len)) / float(trans_len)
                    frame_canvas = cv2.addWeighted(frame_canvas, 1.0 - alpha, next_img, alpha, 0)

                writer.write(frame_canvas)
                frames_rendered += 1

                if frames_rendered % 90 == 0 and progress_callback:
                    pct = int((frames_rendered / total_project_frames) * 100)
                    progress_callback(f"[Compositor] Rendering 30fps motion frames: {pct}% ({frames_rendered}/{total_project_frames})")

        writer.release()
        elapsed = time.time() - t_start
        fps_actual = frames_rendered / max(0.1, elapsed)
        if progress_callback:
            progress_callback(f"[Compositor] Motion pass complete: {frames_rendered} frames in {elapsed:.1f}s ({fps_actual:.1f} fps)")
        return output_mp4_path

    @staticmethod
    def _peek_next_scene_first_frame(loaded_scenes: List[Dict[str, Any]], idx: int, w: int, h: int) -> Optional[np.ndarray]:
        """Read the first frame of the next scene (or Scene 0 on the final scene for seamless loop!)."""
        nxt = loaded_scenes[(idx + 1) % len(loaded_scenes)] if loaded_scenes else None
        if not nxt:
            return None
        if nxt.get("video_clip_path") and os.path.exists(nxt["video_clip_path"]):
            ncap = cv2.VideoCapture(nxt["video_clip_path"])
            nret, nfr = ncap.read()
            ncap.release()
            if nret and nfr is not None:
                if nfr.shape[0] != h or nfr.shape[1] != w:
                    nfr = cv2.resize(nfr, (w, h), interpolation=cv2.INTER_LANCZOS4)
                return nfr
        if nxt.get("img_path") and os.path.exists(nxt["img_path"]):
            nfr = cv2.imread(nxt["img_path"])
            if nfr is not None:
                if nfr.shape[0] != h or nfr.shape[1] != w:
                    nfr = cv2.resize(nfr, (w, h), interpolation=cv2.INTER_LANCZOS4)
                return nfr
        return None

    def regenerate_single_scene(
        self,
        project_dir: str,
        scene_idx: int,
        scene_data: Dict[str, Any],
        category: str = "STEM",
        visual_engine: str = "3D_Pixar",
        project_render_mode: str = "smart_hybrid",
        total_scenes: int = 6,
        style_reference_path: Optional[str] = None,
        progress_callback: Optional[Callable[[str], None]] = None,
    ) -> Dict[str, Any]:
        """Regenerate a single scene's keyframe and/or Omni video clip on demand from the UI Inspector."""
        storyboard_dir = os.path.join(project_dir, "storyboard")
        scenes_dir = os.path.join(project_dir, "scenes")
        os.makedirs(storyboard_dir, exist_ok=True)
        os.makedirs(scenes_dir, exist_ok=True)

        idx_1based = scene_idx + 1
        sb_img_path = os.path.join(storyboard_dir, f"scene_{idx_1based:02d}.png")
        sc_img_path = os.path.join(scenes_dir, f"scene_{idx_1based:02d}.png")
        omni_clip_target = os.path.join(storyboard_dir, f"scene_{idx_1based:02d}.mp4")

        cached_ref = os.path.join(project_dir, "style_reference.png")
        if not style_reference_path and os.path.exists(cached_ref):
            style_reference_path = cached_ref  # reuse the project's auto-generated style reference
        dna = self.extract_style_dna(style_reference_path, visual_engine=visual_engine, progress_callback=progress_callback)
        effective_mode = self.resolve_effective_scene_mode(
            scene_idx=scene_idx,
            total_scenes=total_scenes,
            project_render_mode=project_render_mode,
            scene_mode_override=scene_data.get("render_mode", "auto"),
        )

        # Always regenerate keyframe with force_regenerate=True
        self.generate_scene_image(
            prompt=scene_data.get("prompt", ""),
            output_path=sb_img_path,
            seed=42 + scene_idx * 17 + int(time.time()) % 100,
            scene_idx=scene_idx,
            action_desc=scene_data.get("action_desc", ""),
            category=category,
            visual_engine=visual_engine,
            style_reference_path=style_reference_path,
            force_regenerate=True,
            progress_callback=progress_callback,
        )
        try:
            shutil.copyfile(sb_img_path, sc_img_path)
        except Exception:
            pass

        updated = dict(scene_data)
        updated["image_path"] = sb_img_path
        updated["effective_mode"] = effective_mode

        if effective_mode == "omni_video" and self.fal_key:
            ok, _ = self.generate_ai_video_clip(
                scene_prompt=updated.get("omni_prompt", updated.get("prompt", "")),
                start_image_path=sb_img_path,
                output_clip_path=omni_clip_target,
                duration_sec=float(updated.get("duration", 8.0)),
                force_regenerate=True,
                progress_callback=progress_callback,
            )
            updated["video_clip_path"] = omni_clip_target if ok else ""
        else:
            # Remove stale video clip if switched to keyframe mode
            if os.path.exists(omni_clip_target):
                try:
                    os.remove(omni_clip_target)
                except Exception:
                    pass
            updated["video_clip_path"] = ""

        updated["scene_hash"] = self.compute_scene_hash(
            prompt=updated.get("prompt", ""),
            omni_prompt=updated.get("omni_prompt", ""),
            style_dna=dna,
            visual_engine=visual_engine,
            effective_mode=effective_mode,
            duration=float(updated.get("duration", 8.0)),
            revision_note=updated.get("revision_note", ""),
            style_reference_path=style_reference_path or "",
        )

        # Persist updated scene into storyboard.json
        sb_json_path = os.path.join(project_dir, "storyboard.json")
        if os.path.exists(sb_json_path):
            try:
                with open(sb_json_path, "r", encoding="utf-8") as f:
                    all_scenes = json.load(f)
                if isinstance(all_scenes, list) and 0 <= scene_idx < len(all_scenes):
                    all_scenes[scene_idx] = updated
                    with open(sb_json_path, "w", encoding="utf-8") as f:
                        json.dump(all_scenes, f, indent=2)
            except Exception:
                pass

        return updated

    def render_project(
        self,
        project_dir: str,
        words_json_path: str,
        output_mp4_path: str,
        category: str = "STEM",
        script_text: Optional[str] = None,
        visual_engine: str = "3D_Pixar",
        render_mode: str = "smart_hybrid",
        style_reference_path: Optional[str] = None,
        enable_omni_video: bool = False,
        visual_revision_prompt: str = "",
        custom_scenes: Optional[List[Dict[str, Any]]] = None,
        batch_omni_beats: bool = True,
        progress_callback: Optional[Callable[[str], None]] = None,
    ) -> str:
        """End-to-end token-efficient AI Storyboard & Omni 1.1 Flash rendering pipeline."""
        os.makedirs(project_dir, exist_ok=True)
        storyboard_dir = os.path.join(project_dir, "storyboard")
        scenes_dir = os.path.join(project_dir, "scenes")
        os.makedirs(storyboard_dir, exist_ok=True)
        os.makedirs(scenes_dir, exist_ok=True)

        # Legacy flag compatibility
        if enable_omni_video and render_mode == "keyframe_only":
            render_mode = "full_omni"

        # 1. Resolve current script text
        if not script_text:
            script_file = os.path.join(project_dir, "script.txt")
            if os.path.exists(script_file):
                with open(script_file, "r", encoding="utf-8") as f:
                    script_text = f.read().strip()
            else:
                script_text = "Educational storybook animation"

        # Load prior storyboard.json to compare hashes for content-addressable caching
        sb_json_path = os.path.join(project_dir, "storyboard.json")
        prior_scenes_on_disk: List[Dict[str, Any]] = []
        if os.path.exists(sb_json_path):
            try:
                with open(sb_json_path, "r", encoding="utf-8") as f:
                    loaded = json.load(f)
                    if isinstance(loaded, list):
                        prior_scenes_on_disk = loaded
            except Exception:
                prior_scenes_on_disk = []

        prior_hash_map: Dict[int, str] = {
            int(s.get("scene_idx", i)): str(s.get("scene_hash", ""))
            for i, s in enumerate(prior_scenes_on_disk)
            if isinstance(s, dict)
        }

        if progress_callback:
            progress_callback(f"[Director] Choreographing {visual_engine} storyboard ({render_mode} mode)...")

        # 2. Segment script into 6 timed scenes (or use custom_scenes timings if aligned)
        base_scenes = self.segment_script_into_scenes(
            script_text=script_text,
            words_json_path=words_json_path,
            target_count=6,
        )

        # 3. Extract or resolve Style DNA (auto-generate a style reference if none was provided)
        style_reference_path = self.ensure_style_reference(
            project_dir, script_text, visual_engine, category, style_reference_path, progress_callback
        )
        style_dna = self.extract_style_dna(
            style_image_path=style_reference_path,
            visual_engine=visual_engine,
            progress_callback=progress_callback,
        )

        # 4. Build scene prompts and compute content-addressable SHA-256 hashes
        prompted_scenes = self.build_scene_prompts(
            scenes=base_scenes,
            category=category,
            visual_engine=visual_engine,
            render_mode=render_mode,
            style_dna=style_dna,
            visual_revision_prompt=visual_revision_prompt,
            existing_scenes=custom_scenes or prior_scenes_on_disk,
            style_reference_path=style_reference_path or "",
        )

        # Save Flow Omni multi-turn prompts text for external Google Flow users
        self._write_flow_prompts_file(project_dir, prompted_scenes)

        # 5. Check for continuous imported Flow video in storyboard/
        self._ingest_continuous_flow_video_if_present(storyboard_dir, prompted_scenes, progress_callback)

        # 6. Generate or reuse cached keyframes & Omni video clips per scene
        prev_interaction_id: Optional[str] = None
        total_scenes = len(prompted_scenes)

        for sc in prompted_scenes:
            idx = int(sc["scene_idx"])
            idx_1based = idx + 1
            old_hash = prior_hash_map.get(idx, "")
            new_hash = sc.get("scene_hash", "")
            hash_changed = (old_hash != new_hash) or bool(visual_revision_prompt.strip())

            sb_img_path = os.path.join(storyboard_dir, f"scene_{idx_1based:02d}.png")
            sc_img_path = os.path.join(scenes_dir, f"scene_{idx_1based:02d}.png")
            omni_clip_target = os.path.join(storyboard_dir, f"scene_{idx_1based:02d}.mp4")
            sc["image_path"] = sb_img_path

            # Check for manually imported clip_01.mp4 .. clip_06.mp4
            possible_clips = [
                os.path.join(storyboard_dir, f"clip_{idx_1based:02d}.mp4"),
                os.path.join(storyboard_dir, f"clip_{idx_1based}.mp4"),
                os.path.join(scenes_dir, f"clip_{idx_1based:02d}.mp4"),
                os.path.join(scenes_dir, f"clip_{idx_1based}.mp4"),
            ]
            custom_clip = next((cp for cp in possible_clips if os.path.exists(cp) and os.path.getsize(cp) > 20000), None)
            if custom_clip:
                if progress_callback:
                    progress_callback(f"[OK] Using imported custom clip: {os.path.basename(custom_clip)}")
                sc["video_clip_path"] = custom_clip
                continue

            # Generate or reuse keyframe image
            self.generate_scene_image(
                prompt=sc["prompt"],
                output_path=sb_img_path,
                seed=42 + idx * 11,
                scene_idx=idx,
                action_desc=sc.get("action_desc", ""),
                category=category,
                visual_engine=visual_engine,
                style_reference_path=style_reference_path,
                force_regenerate=hash_changed,
                progress_callback=progress_callback,
            )
            try:
                shutil.copyfile(sb_img_path, sc_img_path)
            except Exception:
                pass

            effective_mode = sc.get("effective_mode", "keyframe")
            if effective_mode == "omni_video" and self.fal_key:
                # For the final scene, pass Scene 1's keyframe as last_image_path for a seamless visual loop
                first_scene_img = os.path.join(storyboard_dir, "scene_01.png")
                loop_last_img = first_scene_img if (idx == total_scenes - 1 and os.path.exists(first_scene_img)) else None

                ok, next_inter_id = self.generate_ai_video_clip(
                    scene_prompt=sc.get("omni_prompt", sc["prompt"]),
                    start_image_path=sb_img_path,
                    output_clip_path=omni_clip_target,
                    duration_sec=float(sc.get("duration", 8.0)),
                    last_image_path=loop_last_img,
                    previous_interaction_id=prev_interaction_id if render_mode == "full_omni" else None,
                    force_regenerate=hash_changed,
                    progress_callback=progress_callback,
                )
                if ok:
                    sc["video_clip_path"] = omni_clip_target
                    if next_inter_id:
                        prev_interaction_id = next_inter_id
            else:
                if progress_callback:
                    progress_callback(
                        f"[Token Saver] Scene {idx_1based}/{total_scenes}: Using Nano Banana keyframe + 30fps 2.5D motion."
                    )
                sc["video_clip_path"] = (
                    omni_clip_target
                    if (not hash_changed and os.path.exists(omni_clip_target) and os.path.getsize(omni_clip_target) > 20000 and effective_mode == "omni_video")
                    else ""
                )

        # Save updated storyboard metadata with hashes
        with open(sb_json_path, "w", encoding="utf-8") as f:
            json.dump(prompted_scenes, f, indent=2)

        # 7. Animate scenes into continuous 1080x1920 30fps video pass
        if progress_callback:
            progress_callback("[Compositor] Rendering continuous 30fps storyboard video pass...")

        self.animate_storyboard(
            scenes_data=prompted_scenes,
            output_mp4_path=output_mp4_path,
            fps=30,
            progress_callback=progress_callback,
        )
        return output_mp4_path

    def _write_flow_prompts_file(self, project_dir: str, prompted_scenes: List[Dict[str, Any]]) -> None:
        omni_prompts_file = os.path.join(project_dir, "flow_omni_prompts.txt")
        veo_prompts_file = os.path.join(project_dir, "veo_prompts.txt")
        omni_lines = [
            "=== GEMINI OMNI 1.1 FLASH MULTI-TURN & TIMECODED PROMPTS ===",
            f"Project: {os.path.basename(project_dir)}",
            f"Total Scenes: {len(prompted_scenes)}\n",
        ]
        for sc in prompted_scenes:
            idx = int(sc["scene_idx"]) + 1
            mode_tag = sc.get("effective_mode", "keyframe").upper()
            omni_lines.append(f"--- SCENE {idx} [{mode_tag}] ({sc['start_time']}s - {sc['end_time']}s) ---")
            omni_lines.append(sc.get("omni_prompt", sc["prompt"]))
            omni_lines.append("")

        prompt_txt = "\n".join(omni_lines)
        for path in (omni_prompts_file, veo_prompts_file):
            try:
                with open(path, "w", encoding="utf-8") as f:
                    f.write(prompt_txt)
            except Exception:
                pass

    def _ingest_continuous_flow_video_if_present(
        self,
        storyboard_dir: str,
        prompted_scenes: List[Dict[str, Any]],
        progress_callback: Optional[Callable[[str], None]] = None,
    ) -> None:
        continuous_clip = None
        for fname in os.listdir(storyboard_dir):
            if fname.lower().endswith(".mp4") and not fname.lower().startswith(("clip_", "scene_")):
                cand = os.path.join(storyboard_dir, fname)
                try:
                    if os.path.getsize(cand) > 300000:
                        continuous_clip = cand
                        break
                except Exception:
                    pass

        if continuous_clip:
            if progress_callback:
                progress_callback(f"[Director] Splitting imported continuous video: {os.path.basename(continuous_clip)}...")
            for sc in prompted_scenes:
                idx_1based = int(sc["scene_idx"]) + 1
                target_clip = os.path.join(storyboard_dir, f"clip_{idx_1based:02d}.mp4")
                if not os.path.exists(target_clip) or os.path.getsize(target_clip) < 10000:
                    cmd = [
                        self.ffmpeg_path,
                        "-y",
                        "-ss",
                        str(sc["start_time"]),
                        "-i",
                        continuous_clip,
                        "-t",
                        str(sc["duration"]),
                        "-c",
                        "copy",
                        target_clip,
                    ]
                    try:
                        subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=False)
                    except Exception:
                        pass
