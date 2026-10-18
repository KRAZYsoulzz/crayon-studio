"""Duration planning, stock matching, layout widths, and picture-mode cost."""

import os
import sys
import wave

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.ai_modifier import MASTER_SCRIPTS, modify_script
from core.duration_guard import (
    MIN_PUBLISH_SECONDS,
    assert_publishable_duration,
    cover_audio_duration,
    estimate_spoken_seconds,
    render_voiceover_until_publishable,
    video_pad_filter,
    words_required,
    DurationShortfall,
)
from core.layout_policy import split_widths
from core.stock_footage import accepts_stock, score_stock_match, search_query, specific_terms
from core.visual_costs import estimate_short_cost


def _write_wav(path: str, seconds: float, rate: int = 8000) -> None:
    frames = max(1, int(seconds * rate))
    with wave.open(path, "wb") as handle:
        handle.setnchannels(1)
        handle.setsampwidth(2)
        handle.setframerate(rate)
        handle.writeframes(b"\x00\x00" * frames)


def test_meter_that_said_60_seconds_is_about_46_in_guy_neural():
    """145 words at 145 WPM was the old '60 second' script. GuyNeural reads it in ~46s."""
    spoken = estimate_spoken_seconds(145, speed=1.05, voice="en-US-GuyNeural")
    assert 44.0 < spoken < 48.0


def test_lighter_script_misses_60s_on_the_recommended_voice():
    words = len(MASTER_SCRIPTS["engineering_piezo_lighter"].split())
    spoken = estimate_spoken_seconds(words, speed=1.05, voice="en-US-GuyNeural")
    assert spoken < MIN_PUBLISH_SECONDS
    assert words_required(69, speed=1.05, voice="en-US-GuyNeural") > words


def test_quartz_watch_is_not_the_lighter_script_and_is_long_enough():
    script = modify_script(
        "",
        topic="How a quartz watch keeps time",
        category="Engineering",
        target_duration=69,
        speech_speed=1.05,
        voice="en-US-GuyNeural",
    )
    lowered = script.lower()
    assert "push-button lighter" not in lowered
    assert "tuning fork" in lowered
    assert len(script.split()) >= words_required(69, speed=1.05, voice="en-US-GuyNeural")
    assert estimate_spoken_seconds(len(script.split()), 1.05, "en-US-GuyNeural") >= 69


def test_fireworks_and_headphones_keep_their_mechanisms():
    fireworks = modify_script("", topic="How fireworks are made", category="STEM", target_duration=69, speech_speed=1.05, voice="en-US-GuyNeural")
    phones = modify_script("", topic="How noise-canceling headphones work", category="Engineering", target_duration=69, speech_speed=1.05, voice="en-US-GuyNeural")
    assert "black powder" in fireworks.lower() or "burst charge" in fireworks.lower()
    assert "push-button lighter" not in phones.lower()
    assert "opposing wave" in phones.lower() or "backwards" in phones.lower()


def test_short_voiceover_is_extended_until_the_floor(tmp_path):
    calls = {"n": 0}

    def synthesize(text, path, voice, speed):
        calls["n"] += 1
        # Faster than the planning table, so the first budget still comes up short.
        duration = len(text.split()) / 230.0 * 60.0
        _write_wav(path, duration)
        return duration

    script, duration, _speed = render_voiceover_until_publishable(
        "A quartz watch ticks. " * 20,
        str(tmp_path / "voice.wav"),
        voice="en-US-GuyNeural",
        speed=1.05,
        target_seconds=69,
        topic="quartz watch",
        synthesize=synthesize,
    )
    assert calls["n"] >= 2
    assert duration >= 69
    assert os.path.exists(tmp_path / "voice.wav")


def test_publish_floor_rejects_the_45_second_file():
    with pytest.raises(DurationShortfall):
        assert_publishable_duration(45.2)
    assert_publishable_duration(60.0)
    assert_publishable_duration(69.4)


def test_picture_timeline_covers_the_whole_voiceover():
    scenes = [
        {"start_time": 0.4, "end_time": 10.0, "duration": 9.6, "scene_idx": 0},
        {"start_time": 10.6, "end_time": 44.0, "duration": 33.4, "scene_idx": 1},
    ]
    covered = cover_audio_duration(scenes, 62.0)
    assert covered[0]["start_time"] == 0
    assert covered[-1]["end_time"] == 62.0
    assert abs(sum(scene["duration"] for scene in covered) - 62.0) < 0.2


def test_short_picture_is_held_to_the_voiceover():
    assert video_pad_filter(45.0, 69.0).startswith("tpad=stop_mode=clone:stop_duration=24.000")
    assert video_pad_filter(70.0, 69.0) == ""


def test_generic_stock_is_rejected_for_niche_mechanisms():
    watch = "The quartz tuning fork oscillates and a stepper motor advances the seconds hand."
    fireworks = "Black powder lifts the aerial shell and the burst charge throws the stars."
    phones = "The feedback microphone builds an opposing wave so the driver cancels the engine rumble."

    assert not accepts_stock(watch, "wrist watch on a wooden table", ["watch", "time", "accessory"])
    assert accepts_stock(watch, "macro of a quartz tuning fork crystal oscillator", ["tuning fork", "oscillator", "stepper"])
    assert not accepts_stock(fireworks, "fireworks celebration in the night sky", ["fireworks", "party", "festival"])
    assert accepts_stock(fireworks, "pyrotechnic aerial shell cross section with black powder", ["aerial shell", "black powder", "burst"])
    assert not accepts_stock(phones, "woman wearing headphones and smiling", ["headphones", "music", "portrait"])
    assert accepts_stock(phones, "noise cancelling headphone microphone and driver cutaway", ["microphone", "driver", "cancelling"])

    # A reused fireworks clip must not score as a watch mechanism.
    score, overlap = score_stock_match(watch, "aerial shell black powder burst charge", ["aerial shell"])
    assert "tuning fork" not in overlap
    assert "aerial" not in specific_terms(watch)
    query = search_query(watch)
    assert "tuning" in query or "fork" in query
    assert "table" not in query


def test_narrow_window_drops_the_preview_and_widths_never_overlap():
    content, preview = split_widths(640, preview_enabled=True)
    assert preview == 0
    assert content == 640

    content, preview = split_widths(1280, preview_enabled=True)
    assert preview > 0
    assert content >= 480
    assert content + preview == 1280

    content, preview = split_widths(1600, preview_enabled=False)
    assert preview == 0
    assert content == 1600

    for width in (400, 720, 900, 1100, 1400, 1920):
        content, preview = split_widths(width, True)
        assert content + preview == width
        assert content >= 0 and preview >= 0
        if preview:
            assert content >= 480


def test_hybrid_costs_less_than_generative_video():
    hybrid = estimate_short_cost("hybrid_stock")
    stills = estimate_short_cost("image_motion")
    lite = estimate_short_cost("veo_lite")
    generative = estimate_short_cost("generative_video")
    standard = estimate_short_cost("veo_standard_reference")
    assert hybrid["high"] < lite["low"]
    assert stills["high"] < lite["low"]
    assert lite["high"] < generative["low"] or lite["typical"] < generative["typical"]
    assert generative["high"] < standard["low"]
    # The old "$15–$20" checkbox was the standard tier, not the Fast model the code calls.
    assert 15 <= standard["typical"] <= 25
    assert hybrid["typical"] < 1
