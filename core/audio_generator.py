"""Natural Documentary Voiceover Engine using Edge-TTS Neural Speech & Kokoro-82M.

Synthesizes high-fidelity 24kHz human voiceover WAV files for short-form video scripts.
Supports warm, natural storytelling voices (Andrew, Brian, Ava, Christopher) with
micro-breath pauses and natural prosody formatting.
"""

from __future__ import annotations

import asyncio
import logging
import os
import re
import subprocess
import tempfile
from typing import Optional
import numpy as np
import soundfile as sf

from core.ffmpeg_compositor import FFmpegCompositor

logger = logging.getLogger("crayon_studio.audio_generator")
SAMPLE_RATE = 24000  # 24kHz target sample rate

# Check Edge-TTS availability
try:
    import edge_tts
    HAS_EDGE_TTS = True
except ImportError:
    HAS_EDGE_TTS = False

# Check Kokoro availability
try:
    from kokoro import KPipeline
    HAS_KOKORO = True
except ImportError:
    HAS_KOKORO = False

DOCUMENTARY_VOICES = {
    "en-US-GuyNeural": "en-US-GuyNeural",                                    # Smooth, authoritative documentary narrator (Recommended Default)
    "en-US-ChristopherNeural": "en-US-ChristopherNeural",                    # Deep cinematic baritone narrator
    "en-US-AndrewMultilingualNeural": "en-US-AndrewMultilingualNeural",      # Warm, natural viral storyteller
    "en-US-BrianMultilingualNeural": "en-US-BrianMultilingualNeural",        # Energetic STEM / How-It's-Made explainer
    "en-US-AvaMultilingualNeural": "en-US-AvaMultilingualNeural",            # Expressive, clear female narrator
    "en-US-JennyNeural": "en-US-JennyNeural",                                # Warm, engaging female narrator
}

VOICE_MAP = {
    **DOCUMENTARY_VOICES,
    # Legacy & Kokoro aliases mapped to high-expressiveness documentary neural models
    "af_heart": "en-US-GuyNeural",
    "am_adam": "en-US-ChristopherNeural",
    "af_bella": "en-US-AvaMultilingualNeural",
    "af_nicole": "en-US-JennyNeural",
    "am_michael": "en-US-ChristopherNeural",
    "bf_emma": "en-US-AvaMultilingualNeural",
}

DEFAULT_VOICE = "en-US-GuyNeural"


def clean_script_for_speech(text: str) -> str:
    """Formats raw script text so numbers, hyphens, and pauses are spoken naturally.

    - Replaces hyphenated numbers like '2,000-year' with '2,000 year'
    - Replaces 'A vs B' with 'A versus B'
    - Replaces ranges '50-75' with '50 to 75'
    - Normalizes dashes and adds natural breathing cadence between clauses and sentences.
    """
    cleaned = text.strip()
    # Replace em-dashes and long hyphens with comma pauses
    cleaned = re.sub(r"[—–]", ", ", cleaned)
    # Replace 'vs' or 'vs.' with 'versus'
    cleaned = re.sub(r"\bvs\.?\b", "versus", cleaned, flags=re.IGNORECASE)
    # Replace hyphenated years/compounds like '2,000-year' -> '2,000 year'
    cleaned = re.sub(r"(\d+(?:,\d+)?)-year", r"\1 year", cleaned, flags=re.IGNORECASE)
    # Replace number ranges '155-170' -> '155 to 170'
    cleaned = re.sub(r"(\d+)-(\d+)", r"\1 to \2", cleaned)
    # Normalize double spaces or double commas
    cleaned = re.sub(r",\s*,", ",", cleaned)
    cleaned = re.sub(r"\s+", " ", cleaned)
    # Ensure natural pause spacing after sentence terminators
    cleaned = re.sub(r"([.!?])\s*", r"\1 ", cleaned)
    return cleaned.strip()


def _trim_long_silences(
    audio_array: np.ndarray,
    sr: int = SAMPLE_RATE,
    max_silence_sec: float = 0.48,
) -> np.ndarray:
    """Compress dead pauses longer than max_silence_sec down to max_silence_sec.

    Preserves natural 400-500ms human breath and rhetorical pauses with smooth
    cosine cross-fades to eliminate digital clicks and abrupt cuts.
    """
    if len(audio_array) == 0:
        return audio_array

    max_silence_len = int(sr * max_silence_sec)
    frame_len = int(sr * 0.02)  # 20ms frames
    fade_len = int(sr * 0.025)  # 25ms smooth crossfade
    if frame_len <= 0 or len(audio_array) < frame_len:
        return audio_array

    num_frames = len(audio_array) // frame_len
    if num_frames == 0:
        return audio_array

    reshaped = audio_array[: num_frames * frame_len].reshape(num_frames, frame_len)
    rms = np.sqrt(np.mean(reshaped ** 2, axis=1))

    peak = np.max(np.abs(audio_array))
    if peak <= 1e-6:
        return audio_array[:max_silence_len]

    silence_thresh = max(0.012 * peak, 0.0015)
    is_silent = rms < silence_thresh

    output_chunks = []
    current_run_silent = bool(is_silent[0])
    run_start_frame = 0

    for i in range(1, num_frames):
        if is_silent[i] != current_run_silent:
            run_samples = audio_array[run_start_frame * frame_len : i * frame_len]
            if current_run_silent and len(run_samples) > max_silence_len:
                # Retain max_silence_len with smooth cosine fade-out of breath decay
                trimmed = np.zeros(max_silence_len, dtype=np.float32)
                lead_fade = min(fade_len, len(run_samples) // 4, max_silence_len // 2)
                if lead_fade > 0:
                    fade_curve = 0.5 * (1.0 + np.cos(np.linspace(0, np.pi, lead_fade)))
                    trimmed[:lead_fade] = run_samples[:lead_fade] * fade_curve
                run_samples = trimmed
            output_chunks.append(run_samples)
            current_run_silent = bool(is_silent[i])
            run_start_frame = i

    last_samples = audio_array[run_start_frame * frame_len :]
    if current_run_silent and len(last_samples) > max_silence_len:
        last_samples = np.zeros(max_silence_len, dtype=np.float32)
    output_chunks.append(last_samples)

    trimmed_audio = np.concatenate(output_chunks).astype(np.float32)
    return trimmed_audio


def _generate_synthetic_speech_placeholder(
    text: str,
    output_path: str,
    speed: float = 1.05,
    sample_rate: int = SAMPLE_RATE,
) -> float:
    """Offline emergency placeholder that produces speech-cadenced audio when completely disconnected."""
    words = [w.strip() for w in text.split() if w.strip()]
    if not words:
        words = ["Blank", "audio", "script"]

    word_duration = (60.0 / (145.0 * speed))
    pause_duration = 0.08 / speed

    audio_segments = []
    base_freqs = [150.0, 180.0, 220.0, 195.0, 160.0]

    for idx, word in enumerate(words):
        dur = max(0.18, word_duration * (len(word) / 5.2))
        t = np.linspace(0, dur, int(sample_rate * dur), endpoint=False)
        f0 = base_freqs[idx % len(base_freqs)]

        envelope = np.sin(np.pi * (t / dur)) ** 1.5
        carrier = 0.35 * np.sin(2 * np.pi * f0 * t) + 0.15 * np.sin(4 * np.pi * f0 * t)
        noise = 0.04 * np.random.normal(0, 1, len(t))
        segment = (carrier + noise) * envelope
        audio_segments.append(segment)

        pause_len = pause_duration
        if word.endswith((".", "!", "?")):
            pause_len = pause_duration * 3.5
        elif word.endswith((",", ";", ":")):
            pause_len = pause_duration * 1.8

        if pause_len > 0:
            silence = np.zeros(int(sample_rate * pause_len), dtype=np.float32)
            audio_segments.append(silence)

    full_audio = np.concatenate(audio_segments).astype(np.float32)
    full_audio = _trim_long_silences(full_audio, sample_rate, max_silence_sec=0.28)
    peak = np.max(np.abs(full_audio))
    if peak > 0:
        full_audio = full_audio / peak * 0.89

    os.makedirs(os.path.dirname(os.path.abspath(output_path)), exist_ok=True)
    sf.write(output_path, full_audio, sample_rate, subtype="PCM_16")
    return len(full_audio) / sample_rate


async def _synthesize_edge_tts(
    text: str,
    output_path: str,
    voice: str = DEFAULT_VOICE,
    speed: float = 1.00,
) -> float:
    """Synthesizes human neural voice via Edge-TTS and converts to 24kHz single-channel WAV."""
    mapped_voice = VOICE_MAP.get(voice, voice if "Neural" in voice else DEFAULT_VOICE)
    pct = int(round((speed - 1.0) * 100))
    rate_str = f"+{pct}%" if pct >= 0 else f"{pct}%"

    clean_text = clean_script_for_speech(text)

    with tempfile.NamedTemporaryFile(suffix=".mp3", delete=False) as tf:
        tmp_mp3 = tf.name

    try:
        communicate = edge_tts.Communicate(clean_text, mapped_voice, rate=rate_str)
        await communicate.save(tmp_mp3)

        ffmpeg_bin = FFmpegCompositor.find_ffmpeg_executable()
        cmd = [
            ffmpeg_bin,
            "-y",
            "-i",
            tmp_mp3,
            "-ar",
            str(SAMPLE_RATE),
            "-ac",
            "1",
            output_path,
        ]
        subprocess.run(cmd, check=True, capture_output=True)

        audio_data, sr = sf.read(output_path)
        if audio_data.ndim > 1:
            audio_data = audio_data.mean(axis=1)

        # Preserve natural human breathing room (480ms threshold with smooth crossfade)
        audio_data = _trim_long_silences(audio_data, sr=sr, max_silence_sec=0.48)
        # Normalize to -1.0 dBFS
        peak = np.max(np.abs(audio_data))
        if peak > 0:
            audio_data = audio_data / peak * 0.92

        sf.write(output_path, audio_data, sr, subtype="PCM_16")
        duration = len(audio_data) / sr
        return duration

    finally:
        if os.path.exists(tmp_mp3):
            try:
                os.remove(tmp_mp3)
            except Exception:
                pass


def generate_voiceover(
    text: str,
    output_path: str,
    voice: str = DEFAULT_VOICE,
    speed: float = 1.00,
) -> str:
    """Synthesize voiceover WAV file at 24kHz using Edge-TTS Neural speech or Kokoro.

    Args:
        text: Script text to be spoken.
        output_path: Target .wav file path.
        voice: Voice identity (default: 'en-US-AndrewMultilingualNeural').
        speed: Speech rate multiplier (default: 1.05 for viral pacing).

    Returns:
        Absolute path to the created WAV file.
    """
    if not text.strip():
        raise ValueError("Script text cannot be empty.")

    output_path = os.path.abspath(output_path)
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    total_duration = 0.0

    if HAS_EDGE_TTS:
        try:
            target_voice = VOICE_MAP.get(voice, voice if "Neural" in voice else DEFAULT_VOICE)
            logger.info("Synthesizing documentary neural voiceover [Voice: %s, Speed: %.2fx]...", target_voice, speed)
            total_duration = asyncio.run(_synthesize_edge_tts(text, output_path, voice=target_voice, speed=speed))
            logger.info("Documentary neural synthesis complete: %s (%.2fs)", output_path, total_duration)
        except Exception as e:
            logger.warning("Edge-TTS synthesis error (%s). Checking alternative engines...", e)
            total_duration = 0.0

    if total_duration == 0.0 and HAS_KOKORO:
        try:
            logger.info("Initializing Kokoro KPipeline for voiceover fallback...")
            pipeline = KPipeline(lang_code="a")
            generator = pipeline(text, voice=voice, speed=speed, split_pattern=r"\n+")
            chunks = []
            for _, _, audio_chunk in generator:
                if audio_chunk is not None and len(audio_chunk) > 0:
                    chunks.append(np.asarray(audio_chunk, dtype=np.float32))

            if chunks:
                full_audio = np.concatenate(chunks)
                full_audio = _trim_long_silences(full_audio, SAMPLE_RATE, max_silence_sec=0.48)
                sf.write(output_path, full_audio, SAMPLE_RATE, subtype="PCM_16")
                total_duration = len(full_audio) / SAMPLE_RATE
                logger.info("Kokoro synthesis complete: %s (%.2fs)", output_path, total_duration)
        except Exception as e:
            logger.warning("Kokoro synthesis error: %s", e)

    if total_duration == 0.0:
        logger.warning("Falling back to emergency audio synthesis engine for '%s'", output_path)
        total_duration = _generate_synthetic_speech_placeholder(text, output_path, speed, SAMPLE_RATE)

    # Validate viral pacing (>60s requirement)
    if total_duration < 61.0:
        logger.warning(
            "CRITICAL DURATION WARNING: Audio duration is %.2fs (< 61.0s target). "
            "TikTok Creator Rewards and YouTube engagement metrics favor scripts >= 61.0 seconds.",
            total_duration,
        )
    else:
        logger.info("Pacing check passed: duration %.2fs meets viral 61s+ target.", total_duration)

    return output_path
