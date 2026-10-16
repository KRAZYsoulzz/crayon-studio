"""Foley Sound Overlay Generator — Style-Adaptive Zero-Hum Edition.

Synthesizes subtle, crisp transition sound cues matched to the active visual style preset:
- 3D_Teardown: Precision mechanical servo click & pneumatic air whoosh
- 3D_Pixar / Custom_Style: Warm cinematic transition whoosh & tactile pop
- 2D_Kurzgesagt / 2D_Crayon: Crisp high-passed paper/sketch transition texture
100% digital silence between transitions so voiceover clarity is never compromised.
"""

from __future__ import annotations

import json
import logging
import os
from typing import List, Optional
import numpy as np
import soundfile as sf

logger = logging.getLogger("crayon_studio.foley_mixer")
DEFAULT_SAMPLE_RATE = 24000


def _synthesize_transition_cue(
    duration: float,
    sr: int = DEFAULT_SAMPLE_RATE,
    style: str = "3D_Pixar",
) -> np.ndarray:
    """Synthesizes a clean, hum-free transition sound effect tailored to the visual style."""
    num_samples = int(duration * sr)
    if num_samples <= 10:
        return np.zeros(0, dtype=np.float32)

    t = np.linspace(0.0, duration, num_samples, endpoint=False, dtype=np.float32)
    rng = np.random.default_rng(42)

    if style == "3D_Teardown":
        # Crisp mechanical click transient + high-passed pneumatic air sweep
        click_len = min(int(0.035 * sr), num_samples // 3)
        cue = np.zeros(num_samples, dtype=np.float32)
        if click_len > 0:
            ct = np.linspace(0.0, 1.0, click_len, dtype=np.float32)
            click = np.sin(2.0 * np.pi * 1850.0 * ct) * np.exp(-ct * 18.0)
            cue[:click_len] += click * 0.7

        raw_noise = rng.normal(0.0, 1.0, num_samples + 2).astype(np.float32)
        air = np.diff(raw_noise, n=2)
        env = np.sin(np.pi * (t / duration)) ** 1.8
        cue += air * env * 0.45

    elif style in ("2D_Kurzgesagt", "2D_Crayon"):
        # High-passed crisp sketch/vector whoosh
        raw = rng.normal(0.0, 1.0, num_samples + 2).astype(np.float32)
        high_passed = np.diff(raw, n=2)
        stroke_env = np.abs(np.sin(np.pi * 3.2 * t)) ** 2.0
        cue = high_passed * stroke_env

    else:
        # 3D_Pixar / Custom_Style: Smooth frequency-swept air whoosh + gentle harmonic chime
        raw = rng.normal(0.0, 1.0, num_samples + 1).astype(np.float32)
        whoosh_noise = np.diff(raw, n=1)
        env = np.sin(np.pi * (t / duration)) ** 2.2
        shimmer = 0.25 * np.sin(2.0 * np.pi * (520.0 + 280.0 * (t / duration)) * t) * np.exp(-t * 5.5)
        cue = (whoosh_noise * 0.55 + shimmer) * env

    fade_len = min(int(0.04 * sr), num_samples // 4)
    if fade_len > 0:
        cue[:fade_len] *= np.linspace(0.0, 1.0, fade_len, dtype=np.float32)
        cue[-fade_len:] *= np.linspace(1.0, 0.0, fade_len, dtype=np.float32)

    peak = float(np.max(np.abs(cue)))
    if peak > 0:
        cue = (cue / peak) * 0.12
    return cue.astype(np.float32)


def ensure_default_sfx_assets(sfx_dir: str) -> None:
    """Ensure baseline SFX files exist."""
    os.makedirs(sfx_dir, exist_ok=True)
    scribble_file = os.path.join(sfx_dir, "crayon_scribble.wav")
    rustle_file = os.path.join(sfx_dir, "paper_rustle.wav")

    if not os.path.exists(scribble_file):
        sf.write(scribble_file, _synthesize_transition_cue(0.55, DEFAULT_SAMPLE_RATE, "3D_Pixar"), DEFAULT_SAMPLE_RATE, subtype="PCM_16")
    if not os.path.exists(rustle_file):
        sf.write(rustle_file, np.zeros(DEFAULT_SAMPLE_RATE, dtype=np.float32), DEFAULT_SAMPLE_RATE, subtype="PCM_16")


def _extract_scene_cue_times(project_dir: str, duration: float) -> List[float]:
    """Reads actual scene transition timestamps from storyboard.json if available."""
    sb_path = os.path.join(project_dir, "storyboard.json")
    if os.path.exists(sb_path):
        try:
            with open(sb_path, "r", encoding="utf-8") as f:
                scenes = json.load(f)
                if isinstance(scenes, list) and scenes:
                    times = [float(sc.get("start_time", 0.0)) for sc in scenes if 0.0 <= float(sc.get("start_time", 0.0)) < duration - 0.5]
                    if times:
                        return times
        except Exception:
            pass
    return [duration * r for r in (0.0, 0.16, 0.33, 0.50, 0.67, 0.84)]


def generate_foley_track(
    words_json_path: str,
    output_sfx_path: str,
    duration: float,
    sfx_dir: Optional[str] = None,
    sample_rate: int = DEFAULT_SAMPLE_RATE,
    visual_engine: str = "3D_Pixar",
) -> str:
    """Generates a Foley track that is 100% silent except during scene transition boundaries."""
    output_sfx_path = os.path.abspath(output_sfx_path)
    proj_dir = os.path.dirname(output_sfx_path)
    os.makedirs(proj_dir, exist_ok=True)

    total_samples = max(sample_rate, int(duration * sample_rate))
    foley_mix = np.zeros(total_samples, dtype=np.float32)

    cue_times = _extract_scene_cue_times(proj_dir, duration)
    burst_dur = 0.55
    burst = _synthesize_transition_cue(burst_dur, sample_rate, style=visual_engine)

    for start_sec in cue_times:
        start_idx = int(start_sec * sample_rate)
        if start_idx >= total_samples:
            continue
        end_idx = min(total_samples, start_idx + len(burst))
        foley_mix[start_idx:end_idx] = burst[: end_idx - start_idx]

    sf.write(output_sfx_path, foley_mix, sample_rate, subtype="PCM_16")
    logger.info("Style-adaptive Foley track rendered (%s): %s (%.2fs)", visual_engine, output_sfx_path, duration)
    return output_sfx_path
