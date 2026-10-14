"""Foley Sound Overlay Generator.

Generates synchronized ASMR crayon scribble and paper texture sound layers
aligned with word timestamps to heighten viewer immersion and retention.
"""

from __future__ import annotations

import json
import logging
import os
from typing import Optional
import numpy as np
import soundfile as sf

logger = logging.getLogger("crayon_studio.foley_mixer")
DEFAULT_SAMPLE_RATE = 24000


def _synthesize_crayon_stroke(duration: float, sr: int = DEFAULT_SAMPLE_RATE) -> np.ndarray:
    """Generate a realistic friction-textured crayon scratch waveform."""
    num_samples = int(duration * sr)
    if num_samples <= 0:
        return np.zeros(0, dtype=np.float32)

    # White noise base for friction
    noise = np.random.normal(0, 1.0, num_samples).astype(np.float32)

    # Modulate with 40-90Hz vibration (representing wax stick dragging across tooth of paper)
    t = np.linspace(0, duration, num_samples, endpoint=False)
    drag_mod = 0.5 + 0.5 * np.sin(2 * np.pi * np.random.uniform(40, 85) * t)

    # Envelope with soft attack and decay
    attack_len = min(int(0.02 * sr), num_samples // 4)
    decay_len = min(int(0.03 * sr), num_samples // 4)
    env = np.ones(num_samples, dtype=np.float32)
    if attack_len > 0:
        env[:attack_len] = np.linspace(0, 1, attack_len)
    if decay_len > 0:
        env[-decay_len:] = np.linspace(1, 0, decay_len)

    stroke = noise * drag_mod * env
    # Low-pass filter smoothing (simple moving average to simulate wax dampening)
    kernel_size = 7
    kernel = np.ones(kernel_size) / kernel_size
    smoothed = np.convolve(stroke, kernel, mode="same")
    return (smoothed * 0.18).astype(np.float32)


def _synthesize_paper_rustle(duration: float, sr: int = DEFAULT_SAMPLE_RATE) -> np.ndarray:
    """Generate subtle textured paper background room tone."""
    num_samples = int(duration * sr)
    noise = np.random.normal(0, 0.02, num_samples).astype(np.float32)
    # Slow gentle drift
    t = np.linspace(0, duration, num_samples, endpoint=False)
    drift = 0.8 + 0.2 * np.sin(2 * np.pi * 0.5 * t)
    return (noise * drift).astype(np.float32)


def _synthesize_studio_hum(duration: float, sr: int = DEFAULT_SAMPLE_RATE) -> np.ndarray:
    """Generate subtle dark studio hum with low-frequency resonance for 3D teardowns."""
    num_samples = int(duration * sr)
    t = np.linspace(0, duration, num_samples, endpoint=False)
    # 55Hz fundamental + 110Hz harmonic + warm floor noise
    hum = (
        0.015 * np.sin(2 * np.pi * 55.0 * t)
        + 0.008 * np.sin(2 * np.pi * 110.0 * t)
        + 0.005 * np.random.normal(0, 1.0, num_samples)
    ).astype(np.float32)
    return hum


def _synthesize_metallic_click(sr: int = DEFAULT_SAMPLE_RATE) -> np.ndarray:
    """Generate crisp high-frequency metallic ratchet / latch click (20ms)."""
    duration = 0.02
    num_samples = int(duration * sr)
    t = np.linspace(0, duration, num_samples, endpoint=False)
    decay_env = np.exp(-t * 220.0).astype(np.float32)
    # Multi-frequency metallic resonant modes (3200Hz, 5400Hz, 8100Hz)
    chime = (
        0.30 * np.sin(2 * np.pi * 3200.0 * t)
        + 0.20 * np.sin(2 * np.pi * 5400.0 * t)
        + 0.12 * np.sin(2 * np.pi * 8100.0 * t)
        + 0.08 * np.random.normal(0, 1.0, num_samples)
    )
    return (chime * decay_env * 0.45).astype(np.float32)


def _synthesize_servo_sweep(duration: float = 0.55, sr: int = DEFAULT_SAMPLE_RATE) -> np.ndarray:
    """Generate smooth pitch-chirping electric servo motor sweep during assembly/explosion."""
    num_samples = int(duration * sr)
    t = np.linspace(0, duration, num_samples, endpoint=False)
    # Frequency sweep 380Hz -> 1350Hz
    freqs = np.linspace(380.0, 1350.0, num_samples)
    phase = 2.0 * np.pi * np.cumsum(freqs) / sr
    env = (np.sin(np.pi * (t / duration)) ** 2).astype(np.float32)
    carrier = (
        0.10 * np.sin(phase)
        + 0.04 * np.sin(phase * 2.0)
        + 0.025 * np.random.normal(0, 1.0, num_samples)
    )
    return (carrier * env * 0.40).astype(np.float32)


def _synthesize_electrical_snap(sr: int = DEFAULT_SAMPLE_RATE) -> np.ndarray:
    """Generate sharp piezo spark / transient mechanical snap (15ms)."""
    duration = 0.015
    num_samples = int(duration * sr)
    t = np.linspace(0, duration, num_samples, endpoint=False)
    decay_env = np.exp(-t * 360.0).astype(np.float32)
    snap = (
        0.45 * np.sin(2 * np.pi * 6800.0 * t)
        + 0.25 * np.sin(2 * np.pi * 9200.0 * t)
        + 0.20 * np.random.normal(0, 1.0, num_samples)
    )
    return (snap * decay_env * 0.50).astype(np.float32)


def ensure_default_sfx_assets(sfx_dir: str) -> None:
    """Ensure baseline SFX samples exist in the sfx directory."""
    os.makedirs(sfx_dir, exist_ok=True)
    scribble_file = os.path.join(sfx_dir, "crayon_scribble.wav")
    rustle_file = os.path.join(sfx_dir, "paper_rustle.wav")

    if not os.path.exists(scribble_file):
        stroke_audio = _synthesize_crayon_stroke(0.6, DEFAULT_SAMPLE_RATE)
        sf.write(scribble_file, stroke_audio, DEFAULT_SAMPLE_RATE, subtype="PCM_16")
        logger.info("Generated default scribble asset: %s", scribble_file)

    if not os.path.exists(rustle_file):
        rustle_audio = _synthesize_paper_rustle(3.0, DEFAULT_SAMPLE_RATE)
        sf.write(rustle_file, rustle_audio, DEFAULT_SAMPLE_RATE, subtype="PCM_16")
        logger.info("Generated default rustle asset: %s", rustle_file)


def generate_foley_track(
    words_json_path: str,
    output_sfx_path: str,
    duration: float,
    sfx_dir: Optional[str] = None,
    sample_rate: int = DEFAULT_SAMPLE_RATE,
    visual_engine: str = "2D_Crayon",
) -> str:
    """Scan word timestamps and generate a synchronized Foley audio WAV file.

    When visual_engine is '2D_Crayon':
      Layers paper rustle room tone and synchronized crayon scribble friction.
    When visual_engine is '3D_Teardown':
      Layers dark studio hum, metallic ratchet clicks, servo sweeps during
      exploded-view transitions, and electrical/mechanical transient snaps.

    Args:
        words_json_path: Path to the JSON containing word timestamps.
        output_sfx_path: Target .wav path for the blended Foley track.
        duration: Total target duration in seconds.
        sfx_dir: Directory containing optional source samples (defaults to templates/sfx).
        sample_rate: Sample rate for the output WAV file.
        visual_engine: '2D_Crayon' or '3D_Teardown'.

    Returns:
        Absolute path to the rendered Foley WAV track.
    """
    output_sfx_path = os.path.abspath(output_sfx_path)
    os.makedirs(os.path.dirname(output_sfx_path), exist_ok=True)

    if sfx_dir is None:
        base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        sfx_dir = os.path.join(base_dir, "templates", "sfx")

    ensure_default_sfx_assets(sfx_dir)

    total_samples = int(duration * sample_rate)
    foley_mix = np.zeros(total_samples, dtype=np.float32)

    words: list = []
    if os.path.exists(words_json_path):
        try:
            with open(words_json_path, "r", encoding="utf-8") as f:
                words = json.load(f)
        except Exception as e:
            logger.warning("Could not read words JSON for Foley sync (%s). Using generic cadence.", e)

    is_3d = (visual_engine == "3D_Teardown")

    if is_3d:
        # 1. Dark studio baseline hum
        hum = _synthesize_studio_hum(duration, sample_rate)
        foley_mix[: len(hum)] += hum * 0.40

        # 2. Exploded-view transition servo sweeps (at 18%, 28%, and 78% of duration)
        sweep_timestamps = [duration * 0.18, duration * 0.28, duration * 0.78]
        for st in sweep_timestamps:
            sweep = _synthesize_servo_sweep(0.55, sample_rate)
            idx_start = int(st * sample_rate)
            idx_end = min(total_samples, idx_start + len(sweep))
            if idx_start < total_samples:
                foley_mix[idx_start:idx_end] += sweep[: idx_end - idx_start]

        # 3. Synchronized mechanical clicks and transient snaps aligned with words
        action_keywords = {"spark", "strike", "hit", "trigger", "volt", "piezo", "click", "lock",
                           "press", "release", "spring", "coil", "current", "flow", "gear", "torque",
                           "hammer", "crystal", "layer", "inside", "chamber", "core"}

        for i, item in enumerate(words):
            word_str = str(item.get("word", "")).lower().strip(".,!?;:\"'")
            start_sec = item.get("start", 0.0)
            start_idx = int(start_sec * sample_rate)
            if start_idx >= total_samples:
                continue

            # Check for spark / impact keyword or punctuation
            if word_str in action_keywords or any(p in str(item.get("word", "")) for p in (".", "!", "?")):
                snap = _synthesize_electrical_snap(sample_rate)
                end_idx = min(total_samples, start_idx + len(snap))
                foley_mix[start_idx:end_idx] += snap[: end_idx - start_idx]
            elif i % 4 == 0:
                # Ratchet click cadence
                click = _synthesize_metallic_click(sample_rate)
                end_idx = min(total_samples, start_idx + len(click))
                foley_mix[start_idx:end_idx] += click[: end_idx - start_idx]

    else:
        # 2D CRAYON ENGINE FOLEY
        # 1. Base paper room presence
        paper_ambient = _synthesize_paper_rustle(duration, sample_rate)
        foley_mix[: len(paper_ambient)] += paper_ambient * 0.35

        # 2. Layer scribble sound on words
        for item in words:
            start_sec = item.get("start", 0.0)
            end_sec = item.get("end", start_sec + 0.3)
            stroke_dur = max(0.12, end_sec - start_sec)

            start_idx = int(start_sec * sample_rate)
            if start_idx >= total_samples:
                continue

            stroke = _synthesize_crayon_stroke(stroke_dur, sample_rate)
            stroke_vol = np.random.uniform(0.65, 0.95)
            stroke = stroke * stroke_vol

            end_idx = min(total_samples, start_idx + len(stroke))
            actual_len = end_idx - start_idx
            if actual_len > 0:
                foley_mix[start_idx:end_idx] += stroke[:actual_len]

    # Prevent clipping
    peak = np.max(np.abs(foley_mix))
    if peak > 0.95:
        foley_mix = foley_mix / peak * 0.90

    sf.write(output_sfx_path, foley_mix, sample_rate, subtype="PCM_16")
    logger.info("Synchronized Foley track rendered to: %s (%.2fs, engine: %s)", output_sfx_path, duration, visual_engine)
    return output_sfx_path
