"""
CRAYON STUDIO — AI Storyboard & Sketch-Reveal Engine
Generates 1080x1920 educational storybook illustrations synced to script cues,
and animates them with progressive hand-drawn sketch-reveals, color bloom,
and 2.5D camera push-ins at 150+ fps via OpenCV.
"""

import os
import re
import json
import math
import time
import shutil
import urllib.parse
import urllib.request
from typing import Callable, Dict, List, Optional, Tuple, Any

import cv2
import numpy as np
from PIL import Image, ImageDraw, ImageFont


class AIStoryboardEngine:
    """
    Universal AI Storyboard & Sketch-Reveal Engine for CrayonStudio.
    Replaces slow Blender math-curve generation with high-fidelity,
    style-consistent 1080x1920 educational illustrations rendered
    and animated via OpenCV in ~15-20 seconds.
    """

    DEFAULT_STYLE_DNA = (
        "Rich educational textbook storybook illustration style, hand-drawn wax crayon and fine ink strokes "
        "on textured warm cream parchment paper. Vibrant accent colors (Prussian blue, gold ochre, terracotta red, "
        "sage green) against clean charcoal structural outlines. Detailed diagrammatic cross-section and cutaway view "
        "with bold arrows and technical callouts. Soft warm studio lighting. Clear visual hierarchy."
    )

    TEARDOWN_STYLE_DNA = (
        "Exploded-view 3D CAD technical teardown, isometric mechanical engineering cutaway illustration. "
        "Precision technical linework with subtle graphite shading, isolated on clean parchment grid paper. "
        "Internal components detached along expansion axes with cyan and amber callout badges, "
        "dimension leader lines, and cross-section material hatches."
    )

    def __init__(self, config_path: str = "config.json", gemini_api_key: Optional[str] = None):
        self.config_path = config_path
        self.gemini_api_key = gemini_api_key or os.environ.get("GEMINI_API_KEY", "")
        if not self.gemini_api_key and os.path.exists(config_path):
            try:
                with open(config_path, "r", encoding="utf-8") as f:
                    cfg = json.load(f)
                    self.gemini_api_key = cfg.get("gemini_api_key", "")
            except Exception:
                pass

    def extract_style_dna(
        self,
        style_image_path: Optional[str] = None,
        progress_callback: Optional[Callable[[str], None]] = None,
    ) -> str:
        """
        Analyzes a style reference image using Gemini Vision if an API key is available,
        or returns the high-fidelity default Style DNA.
        """
        if not style_image_path or not os.path.exists(style_image_path):
            return self.DEFAULT_STYLE_DNA

        # Check for cached DNA next to reference image
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
                    progress_callback("🔍 Analyzing reference screenshot style with Gemini Vision...")
                from google import genai

                client = genai.Client(api_key=self.gemini_api_key)
                img = Image.open(style_image_path)
                prompt = (
                    "Analyze the visual artistic aesthetic of this reference image. "
                    "In 3 concise sentences, describe its: 1) color palette and lighting, "
                    "2) line texture / artistic medium (e.g. crayon, pencil, blueprint, watercolor), "
                    "3) background paper/surface texture and diagrammatic typography. "
                    "Output only the concise descriptive style prompt."
                )
                response = client.models.generate_content(
                    model="gemini-2.5-flash",
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
                    progress_callback(f"⚠️ Gemini Vision analysis skipped ({e}). Using default style DNA.")

        return self.DEFAULT_STYLE_DNA

    def segment_script_into_scenes(
        self,
        script_text: str,
        words_json_path: str,
        target_count: int = 6,
        default_duration: float = 65.0,
    ) -> List[Dict[str, Any]]:
        """
        Segments script text and Whisper word timestamps into 5 to 8 timed visual scenes.
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
            # Fallback when timestamps are absent: split by sentence
            sentences = [s.strip() for s in re.split(r"(?<=[.!?])\s+", script_text) if s.strip()]
            if not sentences:
                sentences = [script_text]

            chunk_size = max(1, math.ceil(len(sentences) / target_count))
            scenes = []
            dur_per_scene = total_duration / max(1, len(sentences))
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

        # When Whisper word timestamps are available: split at natural sentence / clause boundaries
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

                # Heavily prioritize sentence endings (. ! ?)
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

        # Slice words into scenes
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
        Creates concrete, highly-specific illustration prompts for each timed scene.
        """
        dna = style_dna or (self.TEARDOWN_STYLE_DNA if visual_engine == "3D_Teardown" else self.DEFAULT_STYLE_DNA)
        enhanced_scenes = []

        for sc in scenes:
            excerpt = sc.get("script_excerpt", "")
            idx = sc.get("scene_idx", 0)
            total = len(scenes)

            # Extract subject and core physical concept
            clean_excerpt = re.sub(r'["\']', '', excerpt)
            subject_snippet = " ".join(clean_excerpt.split()[:14])

            # Composition and safe zone instructions
            if visual_engine == "3D_Teardown":
                concept_prompt = (
                    f"Exploded-view 3D mechanical teardown illustration depicting: {subject_snippet}. "
                    f"Context: {clean_excerpt[:180]}. "
                    f"Isometric perspective, internal parts separated along guide rails with cyan and gold accent badges. "
                    f"Vertical 9:16 layout, central mechanism prominently framed in upper 70% of canvas, "
                    f"leaving bottom 30% clean for subtitles. {dna}"
                )
            else:
                concept_prompt = (
                    f"Rich educational storybook diagram depicting: {subject_snippet}. "
                    f"Detailed context: {clean_excerpt[:180]}. "
                    f"Anatomical cross-section cutaway with bold charcoal pencil outlines, vibrant wax crayon fills, "
                    f"and technical arrow callouts on warm cream parchment paper. "
                    f"Vertical 9:16 layout, main subject framed in upper 70% of canvas, "
                    f"leaving bottom 30% clean for subtitles. {dna}"
                )

            sc_copy = dict(sc)
            sc_copy["prompt"] = concept_prompt
            sc_copy["concept_title"] = f"Act {idx + 1}/{total}: {subject_snippet[:32]}"
            enhanced_scenes.append(sc_copy)

        return enhanced_scenes

    def generate_procedural_fallback_card(
        self,
        prompt: str,
        output_path: str,
        scene_idx: int = 0,
        title: str = "Educational Diagram",
        category: str = "STEM",
    ) -> str:
        """
        Offline fallback: Generates a high-resolution 1080x1920 textured architectural
        diagrammatic card with guaranteed non-black/non-blank luminance.
        """
        w, h = 1080, 1920
        # Warm cream parchment background (BGR: 238, 244, 248 -> RGB: 248, 244, 238)
        img = Image.new("RGB", (w, h), color=(248, 244, 238))
        draw = ImageDraw.Draw(img)

        # Subtle drafting grid
        grid_color = (235, 230, 222)
        for x in range(60, w - 60, 48):
            draw.line([(x, 80), (x, h - 80)], fill=grid_color, width=1)
        for y in range(80, h - 80, 48):
            draw.line([(60, y), (w - 60, y)], fill=grid_color, width=1)

        # Architectural double frame
        draw.rectangle([(50, 70), (w - 50, h - 180)], outline=(40, 40, 40), width=4)
        draw.rectangle([(58, 78), (w - 58, h - 188)], outline=(210, 160, 20), width=2)

        # Title Banner
        draw.rectangle([(80, 110), (w - 80, 220)], fill=(28, 32, 42), outline=(210, 160, 20), width=2)
        try:
            font_title = ImageFont.truetype("arial.ttf", 36)
            font_sub = ImageFont.truetype("arial.ttf", 24)
            font_body = ImageFont.truetype("arial.ttf", 26)
        except Exception:
            font_title = font_sub = font_body = None

        draw.text((110, 130), f"PHASE {scene_idx + 1} — {category.upper()} SCHEMATIC", fill=(245, 190, 40), font=font_title)
        draw.text((110, 175), title[:42], fill=(230, 235, 240), font=font_sub)

        # Central Visual Diagram (Arches, Cutaway Lattice, Dynamic Stress Lines)
        cx, cy = w // 2, 850
        # Main cross-section block
        draw.rounded_rectangle([(cx - 380, cy - 340), (cx + 380, cy + 340)], radius=24, fill=(238, 232, 220), outline=(35, 35, 35), width=4)

        # Internal geological / chemical crystal lattice
        for row in range(-3, 4):
            for col in range(-3, 4):
                px = cx + col * 100
                py = cy + row * 85
                if row % 2 == 0:
                    draw.ellipse([(px - 26, py - 26), (px + 26, py + 26)], fill=(215, 80, 45), outline=(30, 30, 30), width=3)
                else:
                    draw.regular_polygon((px, py, 28), 6, fill=(30, 120, 210), outline=(30, 30, 30), width=3)

        # Directional Flow Arrows & Callout Ribbons
        draw.line([(cx - 320, cy - 380), (cx - 100, cy - 380)], fill=(30, 120, 210), width=8)
        draw.polygon([(cx - 90, cy - 380), (cx - 130, cy - 395), (cx - 130, cy - 365)], fill=(30, 120, 210))
        draw.text((cx - 320, cy - 425), "INCOMING SEA BRINE / FLOW", fill=(30, 120, 210), font=font_sub)

        draw.line([(cx + 100, cy + 390), (cx + 320, cy + 390)], fill=(215, 80, 45), width=8)
        draw.polygon([(cx + 330, cy + 390), (cx + 290, cy + 375), (cx + 290, cy + 405)], fill=(215, 80, 45))
        draw.text((cx + 80, cy + 405), "CRYSTALLINE INTERLOCK MATRIX", fill=(215, 80, 45), font=font_sub)

        # Descriptive technical annotation card
        draw.rectangle([(90, 1340), (w - 90, 1540)], fill=(255, 255, 255), outline=(180, 180, 180), width=2)
        words = prompt.split()[:26]
        line1 = " ".join(words[:13])
        line2 = " ".join(words[13:])
        draw.text((120, 1370), f"• {line1}", fill=(40, 40, 40), font=font_body)
        draw.text((120, 1420), f"  {line2}", fill=(40, 40, 40), font=font_body)

        os.makedirs(os.path.dirname(os.path.abspath(output_path)), exist_ok=True)
        img.save(output_path, "PNG")
        return output_path

    def generate_scene_image(
        self,
        prompt: str,
        output_path: str,
        seed: int = 42,
        scene_idx: int = 0,
        title: str = "",
        category: str = "STEM",
        progress_callback: Optional[Callable[[str], None]] = None,
    ) -> str:
        """
        3-Tier Robust Image Generation Pipeline:
          - Tier 1: Gemini / Imagen 3 (if API key available)
          - Tier 2: Pollinations Flux Zero-Key API
          - Tier 3: Procedural Offline Architectural Card
        """
        # Reuse existing valid image if already present
        if os.path.exists(output_path) and os.path.getsize(output_path) > 8000:
            return output_path

        os.makedirs(os.path.dirname(os.path.abspath(output_path)), exist_ok=True)

        # Tier 1: Gemini / Imagen 3
        if self.gemini_api_key:
            try:
                if progress_callback:
                    progress_callback(f"[AI Storyboard] Generating Scene {scene_idx + 1} with Imagen 3...")
                from google import genai
                from google.genai import types

                client = genai.Client(api_key=self.gemini_api_key)
                # Clean prompt to safe character length
                clean_prompt = prompt[:950]
                result = client.models.generate_images(
                    model="imagen-3.0-generate-002",
                    prompt=clean_prompt,
                    config=types.GenerateImagesConfig(
                        number_of_images=1,
                        aspect_ratio="9:16",
                        output_mime_type="image/png",
                    ),
                )
                if result.generated_images:
                    img_bytes = result.generated_images[0].image.image_bytes
                    with open(output_path, "wb") as f:
                        f.write(img_bytes)

                    # Ensure exact 1080x1920
                    with Image.open(output_path) as im:
                        if im.size != (1080, 1920):
                            im = im.resize((1080, 1920), Image.Resampling.LANCZOS)
                            im.save(output_path)
                    return output_path
            except Exception as e:
                if progress_callback:
                    progress_callback(f"[AI Storyboard] Tier 1 Imagen 3 skipped ({e}). Falling back to Tier 2 Flux...")

        # Tier 2: Pollinations Flux Zero-Key Endpoint
        try:
            if progress_callback:
                progress_callback(f"[AI Storyboard] Generating Scene {scene_idx + 1} with Flux Zero-Key Engine...")

            # Clean and encode prompt
            safe_prompt = re.sub(r'[^a-zA-Z0-9 ,.-]', '', prompt)[:280]
            encoded = urllib.parse.quote(safe_prompt)
            url = f"https://image.pollinations.ai/prompt/{encoded}?width=1080&height=1920&model=flux&nologo=true&seed={seed}"

            req = urllib.request.Request(url, headers={"User-Agent": "CrayonStudio/2.0"})
            with urllib.request.urlopen(req, timeout=30) as resp:
                data = resp.read()
                if len(data) > 8000:
                    with open(output_path, "wb") as f:
                        f.write(data)

                    # Normalize resolution to 1080x1920
                    with Image.open(output_path) as im:
                        if im.size != (1080, 1920):
                            im = im.resize((1080, 1920), Image.Resampling.LANCZOS)
                            im.save(output_path)
                    return output_path
        except Exception as e:
            if progress_callback:
                progress_callback(f"[AI Storyboard] Tier 2 Flux unavailable ({e}). Using Tier 3 Procedural Fallback.")

        # Tier 3: Procedural Offline Fallback Card
        return self.generate_procedural_fallback_card(
            prompt=prompt,
            output_path=output_path,
            scene_idx=scene_idx,
            title=title or "Diagrammatic Cross-Section",
            category=category,
        )

    def animate_storyboard(
        self,
        scenes_data: List[Dict[str, Any]],
        output_mp4_path: str,
        fps: int = 30,
        progress_callback: Optional[Callable[[str], None]] = None,
    ) -> str:
        """
        Renders a continuous 1080x1920 30fps animation pass from scene illustrations using OpenCV:
          - 1.2s progressive pencil sketch reveal wipe (top to bottom)
          - 1.2s color bloom / watercolor soak
          - 2.5D camera push-in (1.00 -> 1.05 zoom)
          - 12-frame continuous horizontal whip-slide transition between scenes
        """
        w, h = 1080, 1920
        os.makedirs(os.path.dirname(os.path.abspath(output_mp4_path)), exist_ok=True)

        fourcc = cv2.VideoWriter_fourcc(*"mp4v")
        writer = cv2.VideoWriter(output_mp4_path, fourcc, float(fps), (w, h))

        if not writer.isOpened():
            raise RuntimeError(f"Could not open OpenCV VideoWriter for: {output_mp4_path}")

        # Preload and resize all scene images
        loaded_scenes = []
        for sc in scenes_data:
            img_path = sc.get("image_path")
            img = None
            if img_path and os.path.exists(img_path):
                img = cv2.imread(img_path)

            if img is None:
                # Emergency procedural card
                proc_path = img_path or os.path.join(os.path.dirname(output_mp4_path), f"fallback_{sc.get('scene_idx', 0)}.png")
                self.generate_procedural_fallback_card(
                    prompt=sc.get("prompt", "Diagram"),
                    output_path=proc_path,
                    scene_idx=sc.get("scene_idx", 0),
                    title=sc.get("concept_title", ""),
                )
                img = cv2.imread(proc_path)

            if img.shape[0] != h or img.shape[1] != w:
                img = cv2.resize(img, (w, h), interpolation=cv2.INTER_LANCZOS4)

            # Generate artistic pencil sketch on warm cream paper
            gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
            inv = 255 - gray
            blur = cv2.GaussianBlur(inv, (25, 25), 0)
            sketch = cv2.divide(gray, 255 - blur, scale=256)
            sketch_bgr = cv2.cvtColor(sketch, cv2.COLOR_GRAY2BGR)

            paper = np.full((h, w, 3), (238, 244, 248), dtype=np.uint8)  # Warm cream parchment (BGR)
            paper_sketch = cv2.multiply(paper, sketch_bgr, scale=1.0 / 255.0)

            dur = max(2.0, sc.get("duration", 8.0))
            total_frames = int(round(dur * fps))

            loaded_scenes.append({
                "img": img,
                "paper_sketch": paper_sketch,
                "paper": paper,
                "total_frames": total_frames,
                "scene_idx": sc.get("scene_idx", 0),
            })

        total_project_frames = sum(s["total_frames"] for s in loaded_scenes)
        frames_rendered = 0
        wipe_len = int(fps * 1.2)  # ~36 frames
        bloom_len = int(fps * 1.2)  # ~36 frames
        slide_len = 12

        t_start = time.time()
        for idx, sc in enumerate(loaded_scenes):
            img = sc["img"]
            paper_sketch = sc["paper_sketch"]
            paper = sc["paper"]
            num_frames = sc["total_frames"]
            next_img = loaded_scenes[idx + 1]["img"] if idx < len(loaded_scenes) - 1 else None

            for f in range(num_frames):
                # 1. Sketch Wipe Phase
                if f < wipe_len:
                    progress = f / float(wipe_len)
                    # Ease-out wipe line
                    ease_p = 1.0 - math.pow(1.0 - progress, 2.5)
                    wipe_y = int(ease_p * h)

                    frame_canvas = paper.copy()
                    if wipe_y > 0:
                        frame_canvas[:wipe_y, :] = paper_sketch[:wipe_y, :]

                    # Golden pencil lead highlight line
                    if 4 < wipe_y < h - 4:
                        frame_canvas[wipe_y - 2 : wipe_y + 3, :] = (20, 180, 245)

                # 2. Color Bloom Phase
                elif f < (wipe_len + bloom_len):
                    bloom_p = (f - wipe_len) / float(bloom_len)
                    frame_canvas = cv2.addWeighted(img, bloom_p, paper_sketch, 1.0 - bloom_p, 0)

                # 3. 2.5D Camera Push-in
                else:
                    zoom = 1.0 + 0.05 * (f / float(num_frames))
                    M = cv2.getRotationMatrix2D((540, 750), 0.0, zoom)
                    frame_canvas = cv2.warpAffine(
                        img, M, (w, h), flags=cv2.INTER_LINEAR, borderMode=cv2.BORDER_REFLECT
                    )

                # 4. Continuous Whip-Slide Transition
                if next_img is not None and f >= (num_frames - slide_len):
                    trans_f = f - (num_frames - slide_len)
                    t_norm = trans_f / float(slide_len)
                    ease = t_norm * t_norm * (3.0 - 2.0 * t_norm)
                    shift_x = int(w * ease)

                    trans_canvas = np.empty_like(frame_canvas)
                    trans_canvas[:, : w - shift_x] = frame_canvas[:, shift_x:]
                    trans_canvas[:, w - shift_x :] = next_img[:, :shift_x]
                    frame_canvas = trans_canvas

                writer.write(frame_canvas)
                frames_rendered += 1

                if frames_rendered % 90 == 0 and progress_callback:
                    pct = int((frames_rendered / total_project_frames) * 100)
                    progress_callback(f"[OpenCV Engine] Animating sketch-reveal frames: {pct}% ({frames_rendered}/{total_project_frames})")

        writer.release()
        elapsed = time.time() - t_start
        fps_actual = frames_rendered / max(0.1, elapsed)

        if progress_callback:
            progress_callback(f"[OpenCV Engine] Render complete: {frames_rendered} frames in {elapsed:.1f}s ({fps_actual:.1f} fps) -> {output_mp4_path}")

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
        End-to-end storyboard pipeline:
          1. Segment script into timed scenes (~8-12s each)
          2. Extract Style DNA from reference screenshot
          3. Generate or retrieve 1080x1920 scene illustrations
          4. Render 30fps continuous sketch-reveal & camera motion video
        """
        os.makedirs(project_dir, exist_ok=True)
        scenes_dir = os.path.join(project_dir, "scenes")
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
            progress_callback(f"🎬 Segmenting script into timed storyboard scenes...")

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

        # 4. Formulate vivid prompts for each scene
        prompted_scenes = self.build_scene_prompts(
            scenes=scenes,
            category=category,
            visual_engine=visual_engine,
            style_dna=style_dna,
        )

        # 5. Generate scene illustrations
        if progress_callback:
            progress_callback(f"🎨 Generating {len(prompted_scenes)} high-resolution storybook illustrations...")

        for sc in prompted_scenes:
            idx = sc["scene_idx"]
            scene_img_path = os.path.join(scenes_dir, f"scene_{idx}.png")
            sc["image_path"] = scene_img_path

            self.generate_scene_image(
                prompt=sc["prompt"],
                output_path=scene_img_path,
                seed=42 + idx * 7,
                scene_idx=idx,
                title=sc.get("concept_title", ""),
                category=category,
                progress_callback=progress_callback,
            )

        # Save storyboard metadata for review
        with open(os.path.join(project_dir, "storyboard.json"), "w", encoding="utf-8") as f:
            json.dump(prompted_scenes, f, indent=2)

        # 6. Animate scenes via OpenCV
        if progress_callback:
            progress_callback(f"⚡ Compositing progressive sketch-reveal animation...")

        self.animate_storyboard(
            scenes_data=prompted_scenes,
            output_mp4_path=output_mp4_path,
            fps=30,
            progress_callback=progress_callback,
        )

        return output_mp4_path
