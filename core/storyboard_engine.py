"""
CRAYON STUDIO — True AI Video & 3D Pixar Storyboard Engine
Supports:
1. True AI Video Generation via Veo 3.1 (veo-3.1-fast-generate-preview / veo-3.0)
2. Direct importation of pre-rendered clips (clip_01.mp4 ... clip_06.mp4 from Google Flow / Veo)
3. 3D Pixar / Zack D. Films / Kurzgesagt style keyframe generation with zero watermark
4. Active 30fps OpenCV physics layers (water waves/splashes, growing crystals, floating particles)
5. ZERO white flash resets & ZERO on-screen prompt text (bottom 38% reserved for captions)
"""

import os
import re
import json
import math
import time
import shutil
import base64
import subprocess
import urllib.parse
import urllib.request
from typing import Callable, Dict, List, Optional, Tuple, Any

import cv2
import numpy as np
from PIL import Image, ImageDraw, ImageFilter


class AIStoryboardEngine:
    """
    True AI Video & 3D Pixar Storyboard Engine for CrayonStudio.
    """

    PIXAR_STYLE_DNA = (
        "3D Pixar style and Zack D. Films style educational 3D animation, cute expressive mechanical cutaway, "
        "rich tactile clay and stone materials with subsurface scattering, cinematic volumetric lighting, vibrant saturated color palette, "
        "highly detailed 3D render, vertical 9:16 aspect ratio, immersive full-bleed scene composition, "
        "strictly no text, no words, no letters, no watermark, masterpiece 4k."
    )

    TEARDOWN_STYLE_DNA = (
        "Exploded-view 3D CAD mechanical engineering teardown animation, cute 3D isometric cutaway illustration, "
        "precision metallic and transparent glass materials, glowing cyan and amber energy paths, clean continuous background, "
        "vertical 9:16 aspect ratio, immersive full-bleed scene composition, "
        "strictly no text, no words, no letters, no watermark, masterpiece 4k."
    )

    def __init__(self, config_path: str = "config.json", gemini_api_key: Optional[str] = None):
        self.config_path = config_path
        self.gemini_api_key = gemini_api_key or os.environ.get("GEMINI_API_KEY", "")
        self.ffmpeg_path = "ffmpeg"
        if os.path.exists(config_path):
            try:
                with open(config_path, "r", encoding="utf-8") as f:
                    cfg = json.load(f)
                    if not self.gemini_api_key:
                        self.gemini_api_key = cfg.get("gemini_api_key", "")
                    self.ffmpeg_path = cfg.get("ffmpeg_path", "ffmpeg")
            except Exception:
                pass

    def extract_style_dna(
        self,
        style_image_path: Optional[str] = None,
        progress_callback: Optional[Callable[[str], None]] = None,
    ) -> str:
        """
        Analyzes a style reference image using Gemini Vision if an API key is available,
        or returns the 3D Pixar Style DNA.
        """
        if not style_image_path or not os.path.exists(style_image_path):
            return self.PIXAR_STYLE_DNA

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
                    progress_callback("[Director] Analyzing reference screenshot with Gemini Vision...")
                from google import genai

                client = genai.Client(api_key=self.gemini_api_key)
                img = Image.open(style_image_path)
                prompt = (
                    "Analyze the 3D visual artistic style of this image. "
                    "In 2 sentences, describe its lighting, 3D character/material rendering style, and color palette. "
                    "End with: 'no text, no words, no letters, vertical 9:16 aspect ratio'."
                )
                response = client.models.generate_content(
                    model="gemini-3.8-flash",
                    contents=[img, prompt],
                )
                if response.text:
                    dna = response.text.strip().replace("\n", " ")
                    try:
                        with open(cached_txt, "w", encoding="utf-8") as f:
                            f.write(dna)
                    except Exception:
                        pass
                    return dna
            except Exception as e:
                if progress_callback:
                    progress_callback(f"[Director] Gemini Vision analysis note ({e}). Using 3D Pixar style DNA.")

        return self.PIXAR_STYLE_DNA

    def segment_script_into_scenes(
        self,
        script_text: str,
        words_json_path: str,
        target_count: int = 6,
        default_duration: float = 65.0,
    ) -> List[Dict[str, Any]]:
        """
        Segments script text and Whisper word timestamps into 5 to 7 timed visual scenes.
        """
        words: List[Dict[str, Any]] = []
        if os.path.exists(words_json_path):
            try:
                with open(words_json_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    words = data if isinstance(data, list) else data.get("words", [])
            except Exception:
                words = []

        total_duration = float(words[-1].get("end", default_duration)) if words else default_duration
        target_count = max(4, min(8, target_count))

        if not words:
            sentences = [s.strip() for s in re.split(r"(?<=[.!?])\s+", script_text) if s.strip()]
            if not sentences:
                sentences = [script_text]

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
                    "duration": round(max(2.0, e_time - s_time), 2),
                    "script_excerpt": " ".join(chunk),
                })
            return scenes

        scenes: List[Dict[str, Any]] = []
        target_dur = total_duration / target_count
        boundary_indices = []

        curr_start = 0
        for s_idx in range(1, target_count):
            ideal_time = s_idx * target_dur
            best_idx = None
            best_diff = float("inf")

            for w_idx in range(curr_start + 8, len(words) - 8):
                w = words[w_idx]
                w_text = w.get("word", "")
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
            excerpt = " ".join(w.get("word", "").strip() for w in w_slice).strip()
            scenes.append({
                "scene_idx": len(scenes),
                "start_time": round(s_time, 2),
                "end_time": round(e_time, 2),
                "duration": round(max(2.0, e_time - s_time), 2),
                "script_excerpt": excerpt,
            })

        return scenes

    def build_scene_prompts(
        self,
        scenes: List[Dict[str, Any]],
        category: str = "STEM",
        visual_engine: str = "2D_Crayon",
        style_dna: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """
        Creates kid-friendly, concrete 3D Pixar / Kurzgesagt scene prompts for each beat of the script.
        Uses Gemini Flash AI Director to guarantee that every single scene depicts a completely
        DIFFERENT camera perspective, visual subject, and physical action.
        Enforces NO TEXT, NO WORDS, NO LETTERS, and leaves the bottom 38% empty for captions.
        """
        dna = style_dna or (self.TEARDOWN_STYLE_DNA if visual_engine == "3D_Teardown" else self.PIXAR_STYLE_DNA)
        total = len(scenes)

        # 1. Ask Gemini Flash AI Director for distinct scene descriptions if API key is active
        ai_action_descs = []
        if self.gemini_api_key:
            try:
                from google import genai
                client = genai.Client(api_key=self.gemini_api_key)
                excerpts = [sc.get("script_excerpt", "") for sc in scenes]
                prompt_ai = (
                    "You are a Pixar and Zack D Films 3D animation director. For each of these script excerpts, "
                    "provide a distinct, physical, visual action description showing what happens on screen. "
                    "CRITICAL: Each scene MUST show a completely DIFFERENT visual subject and camera angle "
                    "(e.g. wide exterior shot, microscope cutaway, internal crack canyon, growing crystals, chemical matrix, research lab). "
                    "Output ONLY a valid JSON list of strings.\n"
                    f"Excerpts: {json.dumps(excerpts)}"
                )
                resp = client.models.generate_content(model="gemini-3.8-flash", contents=prompt_ai)
                txt = resp.text.strip()
                if "```json" in txt:
                    txt = txt.split("```json")[1].split("```")[0].strip()
                elif "```" in txt:
                    txt = txt.split("```")[1].split("```")[0].strip()
                parsed = json.loads(txt)
                if isinstance(parsed, list) and len(parsed) == total:
                    ai_action_descs = [str(a).strip() for a in parsed]
            except Exception:
                pass

        enhanced_scenes = []
        for idx, sc in enumerate(scenes):
            excerpt = sc.get("script_excerpt", "")
            ex_lower = excerpt.lower()

            if idx < len(ai_action_descs) and ai_action_descs[idx]:
                action_desc = ai_action_descs[idx]
            else:
                # Prioritized, distinct topic matching (specific mechanisms FIRST)
                if any(w in ex_lower for w in ["crystal", "tobermorite", "stitch", "bone", "puzzle"]):
                    action_desc = "macro time-lapse of glowing emerald green tobermorite crystals sprouting and interlocking tightly like magic puzzle pieces, knitting the microcrack completely closed"
                elif any(w in ex_lower for w in ["infiltrate", "pore", "dissolve", "fissure", "canyon", "tunnel"]):
                    action_desc = "microscopic camera rushing into an internal crack tunnel within concrete where vibrant glowing turquoise seawater rushes in, dissolving chalky white quicklime lumps"
                elif any(w in ex_lower for w in ["quicklime", "volcanic", "ash", "pozzolana", "mortar", "camera", "microscope"]):
                    action_desc = "ultra close-up 3D laboratory cross-section slicing into concrete mortar showing white quicklime clasts and jagged red volcanic pozzolana ash particles"
                elif any(w in ex_lower for w in ["rebar", "rust", "steel", "crumble", "50 year", "survive"]):
                    action_desc = "split-screen comparison: on left, modern concrete crumbling with rusted orange rebar; on right, dense 2000-year-old Roman concrete standing rock-solid in surf"
                elif any(w in ex_lower for w in ["engineer", "architect", "lab", "model", "science", "formula"]):
                    action_desc = "modern engineers in a research lab admiring a glowing 3D holographic projection of the self-healing Roman crystal lattice"
                elif any(w in ex_lower for w in ["lock", "tight", "decade", "chemical", "fuel"]):
                    action_desc = "massive ancient Roman concrete seawall illuminated with glowing strength under dramatic Mediterranean sunset waves"
                elif any(w in ex_lower for w in ["ocean", "waves", "water", "sea"]):
                    action_desc = "giant ancient Roman concrete breakwater wall enduring massive splashing turquoise ocean waves with explosive white sea spray"
                else:
                    action_desc = f"cute 3D Pixar educational cutaway animation illustrating {excerpt[:60].strip()}"

            # Strict 3D animation prompt (NO TEXT, NO WORDS, NO LABELS)
            prompt = (
                f"3D Pixar style educational animation of {action_desc}. "
                f"Story context: {excerpt[:120]}. "
                f"{dna} "
                f"Full-bleed vertical 9:16 layout, rich continuous background, strictly no text, no words, no letters, no watermark."
            )

            # Standalone 3D Pixar video prompt for this specific scene cut
            omni_prompt = (
                f"Vertical 9:16 3D Pixar style educational animation of {action_desc}. "
                f"Story context: {excerpt[:100]}. "
                f"Cinematic atmospheric lighting, rich volumetric depth, clean cute 3D cartoon rendering, full-bleed vertical framing. "
                f"Strictly no text, no words, no letters, no logos, no watermark."
            )

            sc_copy = dict(sc)
            sc_copy["prompt"] = prompt
            sc_copy["omni_prompt"] = omni_prompt
            sc_copy["concept_title"] = f"Scene {idx + 1}/{total}"
            sc_copy["action_desc"] = action_desc
            enhanced_scenes.append(sc_copy)

        return enhanced_scenes

    def generate_clean_fallback_card(
        self,
        output_path: str,
        scene_idx: int = 0,
        category: str = "STEM",
        action_desc: str = "",
    ) -> str:
        """
        Clean 3D-styled geometric emergency card:
        - ZERO text, ZERO labels, ZERO prompt descriptions
        - Bottom 38% (y >= 1180) 100% clean
        - Soft gradients and modern 3D lighting
        """
        w, h = 1080, 1920
        # Background: rich oceanic twilight gradient
        base = np.zeros((h, w, 3), dtype=np.uint8)
        # Vertical gradient from deep navy (top) to warm twilight teal (middle)
        for y in range(h):
            ratio = y / float(h)
            r = int(14 + ratio * 20)
            g = int(24 + ratio * 50)
            b = int(48 + ratio * 70)
            base[y, :] = (b, g, r)  # BGR

        img = Image.fromarray(cv2.cvtColor(base, cv2.COLOR_BGR2RGB))
        draw = ImageDraw.Draw(img)

        # Draw soft 3D stylized central subject in upper 60% of frame (cx=540, cy=680)
        cx, cy = w // 2, 680

        # Draw stylized 3D layered blocks (seawall cutaway)
        colors = [(65, 85, 120), (80, 105, 145), (100, 130, 175), (45, 135, 195)]
        for i, col in enumerate(colors):
            bx = cx - 280 + i * 40
            by = cy - 240 + i * 50
            draw.rounded_rectangle([(bx, by), (bx + 480, by + 260)], radius=32, fill=col, outline=(220, 240, 255), width=3)

        # Glowing emerald crystalline cluster in center
        for a in range(8):
            ang = a * (math.pi / 4.0)
            px = int(cx + 120 * math.cos(ang))
            py = int(cy + 40 + 70 * math.sin(ang))
            draw.polygon([
                (px, py - 40),
                (px + 30, py),
                (px, py + 40),
                (px - 30, py),
            ], fill=(30, 215, 140), outline=(230, 255, 240))

        # Soft volumetric lighting glow
        img = img.filter(ImageFilter.SMOOTH_MORE)

        os.makedirs(os.path.dirname(os.path.abspath(output_path)), exist_ok=True)
        img.save(output_path, "PNG")
        return output_path

    def generate_ai_video_clip(
        self,
        scene_prompt: str,
        start_image_path: str,
        output_clip_path: str,
        duration_sec: float = 8.0,
        previous_interaction_id: Optional[str] = None,
        gemini_api_key: Optional[str] = None,
        progress_callback: Optional[Callable[[str], None]] = None,
    ) -> Tuple[bool, Optional[str]]:
        """
        True AI Video Generation via Google Gemini Omni Flash (`gemini-omni-flash-preview` / `gemini-omni-1.1-flash`)
        with Multi-Turn Continuity (`previous_interaction_id`), falling back to Veo 3.1.
        Returns: (success_bool, next_interaction_id)
        """
        if os.path.exists(output_clip_path) and os.path.getsize(output_clip_path) > 20000:
            if progress_callback:
                progress_callback(f"[OK] Reusing existing video clip: {os.path.basename(output_clip_path)}")
            return True, previous_interaction_id

        api_key = gemini_api_key or self.gemini_api_key
        if not api_key:
            return False, previous_interaction_id

        # 1. Primary: Gemini Omni Flash Interactions API (Fast, multi-turn continuous world model)
        try:
            from google import genai

            client = genai.Client(api_key=api_key)
            dur_int = max(3, min(10, int(round(duration_sec))))
            dur_str = f"{dur_int}s"

            turn_label = f" (Turn extension from {previous_interaction_id[:16]}...)" if previous_interaction_id else ""
            if progress_callback:
                progress_callback(f"[Omni Flash] Generating AI video clip ({dur_str}){turn_label}...")

            omni_models = ["gemini-omni-flash-preview", "gemini-omni-1.1-flash"]
            for m in omni_models:
                try:
                    create_kwargs = {
                        "model": m,
                        "input": [{"type": "text", "text": scene_prompt}],
                        "response_format": {
                            "type": "video",
                            "aspect_ratio": "9:16",
                            "duration": dur_str,
                        },
                    }
                    if previous_interaction_id:
                        create_kwargs["previous_interaction_id"] = previous_interaction_id

                    inter = client.interactions.create(**create_kwargs)
                    video_bytes = None
                    if hasattr(inter, "output_video") and inter.output_video:
                        if getattr(inter.output_video, "data", None):
                            d = inter.output_video.data
                            video_bytes = base64.b64decode(d) if isinstance(d, str) else d
                        elif getattr(inter.output_video, "uri", None):
                            video_bytes = client.files.download(file=inter.output_video.uri)

                    if video_bytes and len(video_bytes) > 10000:
                        os.makedirs(os.path.dirname(os.path.abspath(output_clip_path)), exist_ok=True)
                        with open(output_clip_path, "wb") as f:
                            f.write(video_bytes)
                        if progress_callback:
                            progress_callback(f"[OK] [Omni Flash] Generated {len(video_bytes) // 1024} KB clip: {os.path.basename(output_clip_path)}")
                        return True, inter.id
                except Exception as ex:
                    if progress_callback:
                        progress_callback(f"[Omni Flash] Model {m} note: {ex}")

        except Exception as e:
            if progress_callback:
                progress_callback(f"[Note] Omni Flash note: {e}")

        # 2. Secondary Fallback: Veo 3.1
        try:
            if progress_callback:
                progress_callback("[Veo 3.1 Fallback] Generating AI video clip...")
            from google import genai
            from google.genai import types

            client = genai.Client(api_key=api_key)
            image_source = None
            if os.path.exists(start_image_path):
                image_source = types.Image.from_file(location=start_image_path)

            video_prompt = f"3D Pixar and Zack D Films style educational animation in motion: {scene_prompt}. Smooth kinematic physics motion, clear cause-and-effect action, no text, no words, no watermark."

            config = types.GenerateVideosConfig(
                number_of_videos=1,
                duration_seconds=8,
                aspect_ratio="9:16",
            )
            source = types.GenerateVideosSource(
                prompt=video_prompt[:600],
                image=image_source,
            )
            op = client.models.generate_videos(
                model="veo-3.1-fast-generate-preview",
                source=source,
                config=config,
            )
            while not op.done:
                time.sleep(4)
                op = client.operations.get(op)

            if op.response and op.response.generated_videos:
                v_res = op.response.generated_videos[0].video
                os.makedirs(os.path.dirname(os.path.abspath(output_clip_path)), exist_ok=True)
                v_bytes = None
                try:
                    v_bytes = client.files.download(file=v_res)
                except Exception:
                    pass

                if v_bytes:
                    with open(output_clip_path, "wb") as f:
                        f.write(v_bytes)
                elif hasattr(v_res, "save"):
                    v_res.save(output_clip_path)

                if os.path.exists(output_clip_path) and os.path.getsize(output_clip_path) > 10000:
                    if progress_callback:
                        progress_callback(f"[OK] Veo 3.1 AI video clip generated: {os.path.basename(output_clip_path)}")
                    return True, None
        except Exception as e:
            if progress_callback:
                progress_callback(f"[Note] Veo fallback note: {e}")

        return False, previous_interaction_id

    def generate_scene_image(
        self,
        prompt: str,
        output_path: str,
        seed: int = 42,
        scene_idx: int = 0,
        action_desc: str = "",
        category: str = "STEM",
        progress_callback: Optional[Callable[[str], None]] = None,
    ) -> str:
        """
        High-reliability 3D Pixar / Kurzgesagt keyframe image generation:
        - Tier 1: Gemini Native Image Generation (`gemini-2.5-flash-image`)
        - Tier 2: Pollinations standard endpoint with bottom-60px crop (removes watermark)
        - Tier 3: Clean 3D vector emergency card (zero text, bottom 38% clean)
        """
        if os.path.exists(output_path) and os.path.getsize(output_path) > 10000:
            return output_path

        os.makedirs(os.path.dirname(os.path.abspath(output_path)), exist_ok=True)

        # Tier 1: Gemini Native Image Generation (gemini-2.5-flash-image)
        if self.gemini_api_key:
            try:
                if progress_callback:
                    progress_callback(f"[AI Storyboard] Generating Scene {scene_idx + 1} with Gemini Flash Image...")
                from google import genai
                from google.genai import types

                client = genai.Client(api_key=self.gemini_api_key)
                clean_prompt = prompt[:950]
                models_to_try = [
                    "gemini-2.5-flash-image",
                    "gemini-3.1-flash-image-preview",
                    "gemini-3.1-flash-image",
                    "gemini-3-pro-image-preview",
                ]
                for img_model in models_to_try:
                    try:
                        resp = client.models.generate_content(
                            model=img_model,
                            contents=clean_prompt,
                            config=types.GenerateContentConfig(
                                response_modalities=["IMAGE"],
                                image_config=types.ImageConfig(aspect_ratio="9:16"),
                            ),
                        )
                        for part in resp.parts:
                            if part.inline_data and part.inline_data.data:
                                img_bytes = part.inline_data.data
                                with open(output_path, "wb") as f:
                                    f.write(img_bytes)
                                with Image.open(output_path) as im:
                                    if im.size != (1080, 1920):
                                        im = im.resize((1080, 1920), Image.Resampling.LANCZOS)
                                        im.save(output_path)
                                return output_path
                    except Exception as mod_err:
                        if progress_callback:
                            progress_callback(f"[AI Storyboard] Image model {img_model} note: {mod_err}")
            except Exception as e:
                if progress_callback:
                    progress_callback(f"[AI Storyboard] Tier 1 Gemini Image skipped ({e}). Using Tier 2 Engine...")

        # Tier 2: Pollinations Engine (Requests 1080x1980 and crops bottom 60px to strip watermark)
        models_to_try = [None, "flux", "turbo"]
        for m in models_to_try:
            try:
                time.sleep(1.0)
                if progress_callback:
                    m_label = m or "standard"
                    progress_callback(f"[AI Storyboard] Generating Scene {scene_idx + 1} with {m_label.upper()} engine...")

                clean_p = re.sub(r'[^a-zA-Z0-9 ,.-]', '', prompt)[:260]
                encoded = urllib.parse.quote(clean_p)

                if m:
                    url = f"https://image.pollinations.ai/prompt/{encoded}?width=1080&height=1980&nologo=true&model={m}&seed={seed}"
                else:
                    url = f"https://image.pollinations.ai/prompt/{encoded}?width=1080&height=1980&nologo=true&seed={seed}"

                req = urllib.request.Request(
                    url,
                    headers={
                        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
                        "Accept": "image/webp,image/apng,image/*,*/*;q=0.8",
                    },
                )
                with urllib.request.urlopen(req, timeout=30) as resp:
                    data = resp.read()
                    if len(data) > 10000:
                        with open(output_path, "wb") as f:
                            f.write(data)

                        with Image.open(output_path) as im:
                            if im.height >= 1980:
                                im = im.crop((0, 0, 1080, 1920))
                            elif im.size != (1080, 1920):
                                im = im.resize((1080, 1920), Image.Resampling.LANCZOS)
                            im.save(output_path)
                        return output_path
            except Exception as ex:
                if progress_callback:
                    progress_callback(f"[Note] Pollinations {m or 'standard'} retry: {ex}")

        # Tier 3: Clean 3D Vector Emergency Card (Zero Text, Bottom 38% empty)
        if progress_callback:
            progress_callback(f"[AI Storyboard] Scene {scene_idx + 1}: Using clean textless 3D card.")
        return self.generate_clean_fallback_card(
            output_path=output_path,
            scene_idx=scene_idx,
            category=category,
            action_desc=action_desc,
        )

    def _render_physics_layer(
        self,
        frame: np.ndarray,
        f: int,
        scene_type: str,
        w: int = 1080,
        h: int = 1920,
    ) -> np.ndarray:
        """
        Draws dynamic 30fps active physics simulation layers strictly within the upper 60% of frame (y < 1180):
          - 'water': splashing droplets, rising spray, translucent undulating wave ribbons
          - 'crystal': growing emerald crystalline lattice facets with pulsing sparkles
          - 'ash': floating warm mineral/ash particles with Brownian motion
          - 'general': cinematic floating 3D bokeh orbs
        """
        out = frame.copy()
        safe_max_y = 1140  # Keep strictly above subtitles (y >= 1180 is clear)

        if scene_type == "water":
            # 1. Undulating translucent foam / wave ribbon across y = 880..1060
            wave_y = int(960 + 18.0 * math.sin(f * 0.12))
            pts = []
            for x in range(0, w + 40, 30):
                dy = int(14.0 * math.sin(f * 0.10 + x * 0.015) + 8.0 * math.cos(f * 0.07 + x * 0.03))
                pts.append((x, wave_y + dy))
            pts.append((w, safe_max_y))
            pts.append((0, safe_max_y))
            overlay = out.copy()
            cv2.fillPoly(overlay, [np.array(pts, dtype=np.int32)], (225, 175, 50))  # Translucent cyan water (BGR)
            cv2.addWeighted(overlay, 0.28, out, 0.72, 0, out)

            # 2. Dynamic splashing droplets
            np.random.seed((f // 3) * 7 + 101)
            for drop_id in range(16):
                t_rel = (f % 45) / 45.0
                vx = (drop_id - 8) * 1.8
                vy0 = -14.0 - (drop_id % 5) * 2.0
                x = int(540 + vx * (f % 45) + (drop_id * 37) % 200 - 100)
                y = int(920 + vy0 * (f % 45) * 0.7 + 0.45 * math.pow((f % 45), 2))
                if 200 < y < safe_max_y and 40 < x < w - 40:
                    r = max(2, int(5 - 3 * t_rel))
                    cv2.circle(out, (x, y), r, (255, 255, 255), -1)
                    cv2.circle(out, (x, y), r + 2, (240, 210, 80), 1)

        elif scene_type == "crystal":
            # Growing interlocking emerald facets in center (cx=540, cy=640)
            cx, cy = 540, 640
            growth = min(1.0, f / 90.0)
            np.random.seed(42)
            for cid in range(12):
                ang = cid * (math.pi / 6.0)
                dist = int((60 + (cid % 4) * 35) * growth)
                px = int(cx + dist * math.cos(ang))
                py = int(cy + dist * math.sin(ang))
                sz = int((24 + (cid % 3) * 12) * growth)

                pts = np.array([
                    [px, py - sz],
                    [px + int(sz * 0.8), py],
                    [px, py + sz],
                    [px - int(sz * 0.8), py],
                ], dtype=np.int32)

                glow_col = (130, 230, 40) if cid % 2 == 0 else (190, 220, 30)  # Emerald / Lime (BGR)
                overlay = out.copy()
                cv2.fillPoly(overlay, [pts], glow_col)
                cv2.addWeighted(overlay, 0.40, out, 0.60, 0, out)
                cv2.polylines(out, [pts], True, (240, 255, 230), 2)

                # Pulsing star sparkle at tip
                if (f + cid * 5) % 18 < 6:
                    cv2.circle(out, (px, py - sz), 4, (255, 255, 255), -1)

        elif scene_type == "ash":
            # Floating warm volcanic ash and lime particles
            np.random.seed(1234)
            for pid in range(28):
                drift_x = math.sin(f * 0.05 + pid) * 25
                y = int((950 - (f * 1.8 + pid * 38)) % 800 + 200)
                x = int((pid * 39 + drift_x) % (w - 120) + 60)
                if 180 < y < safe_max_y:
                    r = (pid % 3) + 2
                    col = (40, 160, 250) if pid % 2 == 0 else (220, 235, 245)  # Amber / Cream (BGR)
                    cv2.circle(out, (x, y), r, col, -1)

        else:
            # Ambient cinematic 3D bokeh spheres
            np.random.seed(999)
            for bid in range(14):
                bx = int((bid * 83 + math.sin(f * 0.03 + bid) * 30) % (w - 160) + 80)
                by = int((bid * 67 + math.cos(f * 0.02 + bid) * 25) % 750 + 200)
                br = int(18 + (bid % 4) * 8)
                overlay = out.copy()
                cv2.circle(overlay, (bx, by), br, (255, 220, 150), -1)
                cv2.addWeighted(overlay, 0.12, out, 0.88, 0, out)

        return out

    def animate_storyboard(
        self,
        scenes_data: List[Dict[str, Any]],
        output_mp4_path: str,
        fps: int = 30,
        progress_callback: Optional[Callable[[str], None]] = None,
    ) -> str:
        """
        Renders a continuous 1080x1920 30fps animation pass:
          - Plays native AI video clip (from Veo or Google Flow) if available
          - OR combines 2.5D camera push-in with 30fps active physics layers
          - ZERO white flash: smooth 15-frame cross-dissolve between scenes
          - Bottom 38% remains 100% clean for subtitles
        """
        w, h = 1080, 1920
        os.makedirs(os.path.dirname(os.path.abspath(output_mp4_path)), exist_ok=True)

        fourcc = cv2.VideoWriter_fourcc(*"mp4v")
        writer = cv2.VideoWriter(output_mp4_path, fourcc, float(fps), (w, h))

        if not writer.isOpened():
            raise RuntimeError(f"Could not open OpenCV VideoWriter for: {output_mp4_path}")

        # Preload scenes and check for custom video clips
        loaded_scenes = []
        for sc in scenes_data:
            dur = max(2.0, sc.get("duration", 8.0))
            num_frames = int(round(dur * fps))
            video_clip_path = sc.get("video_clip_path")
            img_path = sc.get("image_path")

            # Determine physics layer type from prompt / excerpt
            ex_text = (sc.get("script_excerpt", "") + " " + sc.get("action_desc", "")).lower()
            if any(k in ex_text for k in ["ocean", "wave", "water", "splash", "brine"]):
                phys_type = "water"
            elif any(k in ex_text for k in ["crystal", "tobermorite", "interlock", "grow"]):
                phys_type = "crystal"
            elif any(k in ex_text for k in ["ash", "lime", "pozzolana", "volcanic"]):
                phys_type = "ash"
            else:
                phys_type = "general"

            loaded_scenes.append({
                "scene_idx": sc.get("scene_idx", 0),
                "duration": dur,
                "total_frames": num_frames,
                "video_clip_path": video_clip_path if (video_clip_path and os.path.exists(video_clip_path)) else None,
                "img_path": img_path,
                "phys_type": phys_type,
            })

        total_project_frames = sum(s["total_frames"] for s in loaded_scenes)
        frames_rendered = 0
        trans_len = 15  # 0.5s seamless cross-dissolve

        t_start = time.time()
        for idx, sc in enumerate(loaded_scenes):
            num_frames = sc["total_frames"]
            phys_type = sc["phys_type"]

            # 1. If scene has a full AI video clip (Veo 3.1 or Google Flow import)
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

                # Look ahead for next scene's starting frame for smooth cross-dissolve
                next_start_frame = None
                if idx < len(loaded_scenes) - 1:
                    nxt = loaded_scenes[idx + 1]
                    if nxt.get("video_clip_path") and os.path.exists(nxt["video_clip_path"]):
                        ncap = cv2.VideoCapture(nxt["video_clip_path"])
                        nret, nfr = ncap.read()
                        ncap.release()
                        if nret:
                            if nfr.shape[0] != h or nfr.shape[1] != w:
                                nfr = cv2.resize(nfr, (w, h), interpolation=cv2.INTER_LANCZOS4)
                            next_start_frame = nfr
                    elif nxt.get("img_path") and os.path.exists(nxt["img_path"]):
                        nfr = cv2.imread(nxt["img_path"])
                        if nfr is not None:
                            if nfr.shape[0] != h or nfr.shape[1] != w:
                                nfr = cv2.resize(nfr, (w, h), interpolation=cv2.INTER_LANCZOS4)
                            next_start_frame = nfr

                for f in range(num_frames):
                    pos = int(f * (len(clip_frames) / float(num_frames)))
                    fr = clip_frames[min(len(clip_frames) - 1, pos)].copy()

                    # Seamless 15-frame cross-dissolve into next scene
                    if next_start_frame is not None and f >= (num_frames - trans_len):
                        alpha = (f - (num_frames - trans_len)) / float(trans_len)
                        fr = cv2.addWeighted(fr, 1.0 - alpha, next_start_frame, alpha, 0)

                    writer.write(fr)
                    frames_rendered += 1

                continue

            # 2. Otherwise: 3D Pixar Keyframe + Active 30fps Physics + 2.5D Push-In
            img_path = sc["img_path"]
            img = cv2.imread(img_path) if (img_path and os.path.exists(img_path)) else None
            if img is None:
                img = np.full((h, w, 3), (48, 24, 14), dtype=np.uint8)

            if img.shape[0] != h or img.shape[1] != w:
                img = cv2.resize(img, (w, h), interpolation=cv2.INTER_LANCZOS4)

            # Pre-read next image for seamless cross-dissolve transition
            next_img = None
            if idx < len(loaded_scenes) - 1:
                next_path = loaded_scenes[idx + 1]["img_path"]
                if next_path and os.path.exists(next_path):
                    next_img = cv2.imread(next_path)
                    if next_img is not None and (next_img.shape[0] != h or next_img.shape[1] != w):
                        next_img = cv2.resize(next_img, (w, h), interpolation=cv2.INTER_LANCZOS4)

            for f in range(num_frames):
                # 2.5D camera push-in (1.00 -> 1.05 zoom)
                zoom = 1.0 + 0.05 * (f / float(num_frames))
                M = cv2.getRotationMatrix2D((540, 680), 0.0, zoom)
                frame_canvas = cv2.warpAffine(img, M, (w, h), flags=cv2.INTER_LINEAR, borderMode=cv2.BORDER_REFLECT)

                # Render active physical motion layer (water, crystals, ash)
                frame_canvas = self._render_physics_layer(frame_canvas, f, phys_type, w=w, h=h)

                # Seamless 15-frame cross-dissolve to next scene (NO white flash!)
                if next_img is not None and f >= (num_frames - trans_len):
                    alpha = (f - (num_frames - trans_len)) / float(trans_len)
                    frame_canvas = cv2.addWeighted(frame_canvas, 1.0 - alpha, next_img, alpha, 0)

                writer.write(frame_canvas)
                frames_rendered += 1

                if frames_rendered % 90 == 0 and progress_callback:
                    pct = int((frames_rendered / total_project_frames) * 100)
                    progress_callback(f"[3D Pixar Engine] Rendering motion frames: {pct}% ({frames_rendered}/{total_project_frames})")

        writer.release()
        elapsed = time.time() - t_start
        fps_actual = frames_rendered / max(0.1, elapsed)

        if progress_callback:
            progress_callback(f"[3D Pixar Engine] Render complete: {frames_rendered} frames in {elapsed:.1f}s ({fps_actual:.1f} fps) -> {output_mp4_path}")

        return output_mp4_path

    def render_project(
        self,
        project_dir: str,
        words_json_path: str,
        output_mp4_path: str,
        category: str = "STEM",
        script_text: Optional[str] = None,
        visual_engine: str = "2D_Crayon",
        style_reference_path: Optional[str] = None,
        progress_callback: Optional[Callable[[str], None]] = None,
    ) -> str:
        """
        End-to-end True AI Video & 3D Pixar Storyboard Pipeline:
          1. Segment script into timed scenes (~8-11s each)
          2. Check for user-imported video clips (clip_01.mp4 ... clip_06.mp4 in storyboard/)
          3. Generate or retrieve 1080x1920 3D Pixar illustrations
          4. Try Veo 3.1 video generation if Gemini API key is configured
          5. Composite 30fps animation pass with zero white flash and clean subtitle zone
        """
        os.makedirs(project_dir, exist_ok=True)
        storyboard_dir = os.path.join(project_dir, "storyboard")
        scenes_dir = os.path.join(project_dir, "scenes")
        os.makedirs(storyboard_dir, exist_ok=True)
        os.makedirs(scenes_dir, exist_ok=True)

        # 1. Recover script text
        if not script_text:
            script_file = os.path.join(project_dir, "script.txt")
            if os.path.exists(script_file):
                with open(script_file, "r", encoding="utf-8") as f:
                    script_text = f.read().strip()
            elif os.path.exists(words_json_path):
                try:
                    with open(words_json_path, "r", encoding="utf-8") as f:
                        words = json.load(f)
                        script_text = " ".join(w.get("word", "") for w in words).strip()
                except Exception:
                    script_text = "Educational storybook animation"
            else:
                script_text = "Educational storybook animation"

        if progress_callback:
            progress_callback("[Director] Choreographing 3D Pixar storyboard timeline...")

        # 2. Segment script into 5 to 7 timed scenes
        scenes = self.segment_script_into_scenes(
            script_text=script_text,
            words_json_path=words_json_path,
            target_count=6,
        )

        # 3. Extract or resolve Style DNA
        style_dna = self.extract_style_dna(
            style_image_path=style_reference_path,
            progress_callback=progress_callback,
        )

        # 4. Formulate vivid 3D Pixar prompts
        prompted_scenes = self.build_scene_prompts(
            scenes=scenes,
            category=category,
            visual_engine=visual_engine,
            style_dna=style_dna,
        )

        # Check for single continuous video dropped into storyboard/
        continuous_clip = None
        for fname in os.listdir(storyboard_dir):
            if fname.lower().endswith(".mp4") and not fname.lower().startswith("clip_") and not fname.lower().startswith("scene_"):
                cand = os.path.join(storyboard_dir, fname)
                try:
                    if os.path.getsize(cand) > 300000:
                        continuous_clip = cand
                        break
                except Exception:
                    pass

        if continuous_clip:
            if progress_callback:
                progress_callback(f"[Director] Ingesting continuous Flow Omni video: {os.path.basename(continuous_clip)}...")
            for sc in prompted_scenes:
                idx_1based = sc["scene_idx"] + 1
                target_clip = os.path.join(storyboard_dir, f"scene_{idx_1based:02d}.mp4")
                if not os.path.exists(target_clip) or os.path.getsize(target_clip) < 10000:
                    cmd = [
                        self.ffmpeg_path, "-y",
                        "-ss", str(sc["start_time"]),
                        "-i", continuous_clip,
                        "-t", str(sc["duration"]),
                        "-c", "copy",
                        target_clip,
                    ]
                    try:
                        subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                    except Exception:
                        pass

        # Save Flow Omni multi-turn prompts and Veo prompts text
        omni_prompts_file = os.path.join(project_dir, "flow_omni_prompts.txt")
        veo_prompts_file = os.path.join(project_dir, "veo_prompts.txt")

        omni_lines = [
            "=== GOOGLE FLOW OMNI MULTI-TURN PROMPTS ===",
            f"Project: {os.path.basename(project_dir)}",
            f"Total Scenes: {len(prompted_scenes)}",
            "Tip: In Google Flow (flow.google) or Google AI Studio, paste Round 1 to start the world model,",
            "then paste each conversational round to extend the scene. Drop exported video(s) into 'storyboard/'!\n",
        ]
        for sc in prompted_scenes:
            idx = sc["scene_idx"] + 1
            round_hdr = "ROUND 1 (WORLD SETUP)" if idx == 1 else f"ROUND {idx} (SCENE EXTENSION)"
            omni_lines.append(f"--- {round_hdr} ({sc['start_time']}s - {sc['end_time']}s) ---")
            omni_lines.append(sc.get("omni_prompt", sc["prompt"]))
            omni_lines.append("")

        prompt_txt = "\n".join(omni_lines)
        with open(omni_prompts_file, "w", encoding="utf-8") as of:
            of.write(prompt_txt)
        with open(veo_prompts_file, "w", encoding="utf-8") as vf:
            vf.write(prompt_txt)

        # 5. Check for imported clips & generate scene assets
        if progress_callback:
            progress_callback(f"[Pixar 3D] Generating {len(prompted_scenes)} 3D Pixar scenes...")

        prev_interaction_id = None
        for sc in prompted_scenes:
            idx = sc["scene_idx"]
            idx_1based = idx + 1

            # Check for pre-rendered custom video clips (e.g. clip_01.mp4 ... clip_06.mp4)
            possible_clips = [
                os.path.join(storyboard_dir, f"clip_{idx_1based:02d}.mp4"),
                os.path.join(storyboard_dir, f"clip_{idx_1based}.mp4"),
                os.path.join(scenes_dir, f"clip_{idx_1based:02d}.mp4"),
                os.path.join(scenes_dir, f"clip_{idx_1based}.mp4"),
            ]
            custom_clip = next((cp for cp in possible_clips if os.path.exists(cp) and os.path.getsize(cp) > 20000), None)

            # Standardized scene image paths
            sb_img_path = os.path.join(storyboard_dir, f"scene_{idx_1based:02d}.png")
            sc_img_path = os.path.join(scenes_dir, f"scene_{idx_1based:02d}.png")
            sc["image_path"] = sb_img_path

            if custom_clip:
                if progress_callback:
                    progress_callback(f"[OK] Found custom AI video clip: {os.path.basename(custom_clip)}")
                sc["video_clip_path"] = custom_clip
            else:
                # Generate distinct 3D Pixar keyframe for this scene beat
                self.generate_scene_image(
                    prompt=sc["prompt"],
                    output_path=sb_img_path,
                    seed=42 + idx * 11,
                    scene_idx=idx,
                    action_desc=sc.get("action_desc", ""),
                    category=category,
                    progress_callback=progress_callback,
                )
                # Mirror in scenes/ for compatibility
                try:
                    shutil.copyfile(sb_img_path, sc_img_path)
                except Exception:
                    pass

                # Generate dedicated standalone Gemini Omni Flash video for this scene cut
                omni_clip_target = os.path.join(storyboard_dir, f"scene_{idx_1based:02d}.mp4")
                if self.gemini_api_key:
                    video_prompt = sc.get("omni_prompt", sc["prompt"])
                    ok, _ = self.generate_ai_video_clip(
                        scene_prompt=video_prompt,
                        start_image_path=sb_img_path,
                        output_clip_path=omni_clip_target,
                        duration_sec=sc["duration"],
                        previous_interaction_id=None,
                        progress_callback=progress_callback,
                    )
                    if ok:
                        sc["video_clip_path"] = omni_clip_target

        # Save metadata
        with open(os.path.join(project_dir, "storyboard.json"), "w", encoding="utf-8") as f:
            json.dump(prompted_scenes, f, indent=2)

        # 6. Animate scenes via OpenCV
        if progress_callback:
            progress_callback("[Compositor] Compositing continuous 3D Pixar animation pass...")

        self.animate_storyboard(
            scenes_data=prompted_scenes,
            output_mp4_path=output_mp4_path,
            fps=30,
            progress_callback=progress_callback,
        )

        return output_mp4_path
