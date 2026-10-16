"""Spoken-length planning and the monetization floor.

The studio meter used to divide word count by 145 WPM and ignore the speech
speed. Measured Edge-TTS documentary voices are faster than that, and the
silence trimmer makes GuyNeural faster still. A script the meter called
60 seconds (145 words) is about 46 seconds in GuyNeural at 1.05x, which is
the quartz-watch shortfall.

Planning uses the measured rate. After synthesis the real wav is checked, and
a short read is extended and synthesized again. The picture timeline is then
stretched to that wav so FFmpeg's shorter-stream cut cannot pull the file
back under 60 seconds.
"""

from __future__ import annotations

import logging
import math
import os
import re
import shutil
import subprocess
import wave
from typing import Callable, Dict, List, Optional, Sequence

logger = logging.getLogger("crayon_studio.duration_guard")

# Hard floor for YouTube / TikTok monetization length. Planning aims higher
# (DEFAULT_TARGET_SECONDS) so trimming and a slightly faster read still clear it.
MIN_PUBLISH_SECONDS = 60.0
DEFAULT_TARGET_SECONDS = 69.0

# Effective words per minute at speed 1.0, after silence trimming.
# Measured on the 175-word lighter script with Edge-TTS (October 2026):
#   GuyNeural +0% trimmed 58.50s -> 179.5 WPM; +5% trimmed 55.84s -> 188 WPM.
#   AndrewMultilingualNeural +5% trimmed 66.05s -> 159 WPM, so ~151 WPM at 1.0x.
# Unknown voices use GuyNeural's rate, the fastest of the documentary set,
# so the word budget is long rather than short.
VOICE_WPM_AT_1X: Dict[str, float] = {
    "en-US-GuyNeural": 180.0,
    "en-US-ChristopherNeural": 170.0,
    "en-US-AndrewMultilingualNeural": 152.0,
    "en-US-BrianMultilingualNeural": 175.0,
    "en-US-AvaMultilingualNeural": 175.0,
    "en-US-JennyNeural": 170.0,
    "af_heart": 180.0,
    "am_adam": 170.0,
}
DEFAULT_PLANNING_WPM = 180.0

# Extra words for the half-second the scene cutter and `-shortest` used to drop.
PLANNING_MARGIN = 1.10

Synthesizer = Callable[[str, str, str, float], float]


class DurationShortfall(RuntimeError):
    """Raised when a voiceover or final render is under the monetization floor."""


def planning_wpm(voice: str) -> float:
    """Return the trimmed 1.0x words-per-minute used to budget a script."""
    if not voice:
        return DEFAULT_PLANNING_WPM
    if voice in VOICE_WPM_AT_1X:
        return VOICE_WPM_AT_1X[voice]
    for key, wpm in VOICE_WPM_AT_1X.items():
        if key.lower() in voice.lower() or voice.lower() in key.lower():
            return wpm
    return DEFAULT_PLANNING_WPM


def estimate_spoken_seconds(word_count: int, speed: float = 1.0, voice: str = "") -> float:
    """Estimate spoken seconds at the measured neural rate, including speed."""
    rate = planning_wpm(voice) * max(0.5, float(speed))
    if word_count <= 0 or rate <= 0:
        return 0.0
    return word_count / rate * 60.0


def words_required(
    target_seconds: float,
    speed: float = 1.0,
    voice: str = "",
    margin: float = PLANNING_MARGIN,
) -> int:
    """Word count that should speak for at least ``target_seconds``."""
    target = max(MIN_PUBLISH_SECONDS, float(target_seconds))
    rate = planning_wpm(voice) * max(0.5, float(speed))
    return max(1, int(math.ceil(target * rate / 60.0 * margin)))


def _subject_name(topic: str) -> str:
    cleaned = re.sub(r"\([^)]*\)", "", topic or "")
    cleaned = re.sub(r"^(how|why|what)\s+(a|an|the|do|does|is|are)?\s*", "", cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r"[#@][\w]+", "", cleaned)
    cleaned = " ".join(cleaned.split()).strip(".,;:!- ")
    words = cleaned.split()
    if len(words) > 6:
        words = words[:6]
    return " ".join(words).strip() or "this mechanism"


def _expansion_beats(subject: str) -> List[str]:
    """Extra narration beats. Each one is a real step, not padding syllables."""
    return [
        (
            f"Freeze {subject} one stage at a time and it stops looking like a single trick. "
            f"It is a chain of small parts, and each part is waiting on the one before it."
        ),
        (
            f"The first stage only stores energy. Inside {subject} that energy may be mechanical, "
            f"electrical, or chemical, and it does not become the result you notice until a later stage lets it go."
        ),
        (
            f"The middle stage is the conversion. A shape changes, a contact closes, or a field flips, "
            f"and the stored energy has to take a new form because the geometry of {subject} leaves it no other path."
        ),
        (
            f"High-speed imaging shows why the everyday version of {subject} feels instant. "
            f"The parts are tiny, so a handoff that would take a full second in a machine the size of a room "
            f"is over before your eye can separate the steps."
        ),
        (
            f"Engineers do not trust the outside of the object. They measure each stage of {subject} on its own, "
            f"because if one handoff is late or weak, the final effect never happens."
        ),
        (
            f"A diagram is more honest than a glance. Follow the energy through {subject} from the first push "
            f"to the last result, and the mystery turns into a sequence you can check."
        ),
        (
            f"Watch the cutaway of {subject} again and count the handoffs. "
            f"Energy enters, a part moves, a second part answers, and only then does the effect you came for appear."
        ),
        (
            f"That count is the whole explanation of {subject}. "
            f"Nothing in the chain is decorative, and skipping a stage is the same as breaking the effect."
        ),
    ]


def ensure_script_word_count(
    script: str,
    *,
    topic: str = "",
    target_seconds: float = DEFAULT_TARGET_SECONDS,
    speed: float = 1.0,
    voice: str = "",
) -> str:
    """Lengthen ``script`` until its word count can carry ``target_seconds``."""
    needed = words_required(target_seconds, speed=speed, voice=voice)
    text = " ".join((script or "").split())
    if not text:
        text = f"Here is what actually happens inside {_subject_name(topic)}."
    if len(text.split()) >= needed:
        return text

    subject = _subject_name(topic)
    sentences = [s.strip() for s in re.split(r"(?<=[.!?])\s+", text) if s.strip()]
    if not sentences:
        sentences = [text]
    closing = sentences[-1]
    body = sentences[:-1]
    beats = _expansion_beats(subject)
    cursor = 0
    guard = 0
    while len(" ".join(body + [closing]).split()) < needed and guard < 24:
        beat = beats[cursor % len(beats)]
        if beat not in body:
            body.append(beat)
        else:
            body.append(
                f"Look at stage {guard + 1} of {subject} on its own. "
                f"The part that moves here only moves because the previous stage finished its handoff."
            )
        cursor += 1
        guard += 1
    return " ".join(body + [closing]).strip()


def probe_wav_duration(path: str) -> float:
    """Duration of a wav file, preferring the stdlib so tests need no codec."""
    with wave.open(path, "rb") as wf:
        frames = wf.getnframes()
        rate = wf.getframerate() or 1
        return frames / float(rate)


def probe_media_duration(path: str, ffmpeg_path: Optional[str] = None) -> float:
    """Duration of an audio or video file via the wav header or ffprobe."""
    if not path or not os.path.exists(path):
        raise FileNotFoundError(path)
    if path.lower().endswith(".wav"):
        try:
            return probe_wav_duration(path)
        except Exception:
            pass
    try:
        import soundfile as sf

        info = sf.info(path)
        if info.duration and info.duration > 0:
            return float(info.duration)
    except Exception:
        pass

    ffprobe = shutil.which("ffprobe")
    if not ffprobe and ffmpeg_path:
        sibling = os.path.join(os.path.dirname(ffmpeg_path), "ffprobe")
        if os.path.exists(sibling):
            ffprobe = sibling
    if not ffprobe:
        ffprobe = "ffprobe"
    result = subprocess.run(
        [
            ffprobe,
            "-v",
            "error",
            "-show_entries",
            "format=duration",
            "-of",
            "default=nw=1:nk=1",
            path,
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    text = (result.stdout or "").strip()
    if result.returncode != 0 or not text:
        raise RuntimeError(f"Could not probe duration of {path}: {result.stderr.strip()}")
    return float(text)


def video_pad_filter(video_seconds: float, audio_seconds: float) -> str:
    """FFmpeg filter prefix that holds the last frame until the voiceover ends."""
    pad = float(audio_seconds) - float(video_seconds)
    if pad > 0.05:
        return f"tpad=stop_mode=clone:stop_duration={pad:.3f},"
    return ""


def assert_publishable_duration(
    seconds: float,
    minimum: float = MIN_PUBLISH_SECONDS,
) -> None:
    """Raise when a finished file is under the monetization floor."""
    if float(seconds) + 1e-3 < float(minimum):
        raise DurationShortfall(
            f"Final duration {float(seconds):.2f}s is under the {float(minimum):.0f}s monetization floor."
        )


def cover_audio_duration(
    scenes: Sequence[Dict],
    audio_duration: float,
) -> List[Dict]:
    """Close gaps between scenes and hold the last scene through the end of the wav.

    Scene cuts used to span only the words inside each slice, dropping the pause
    at every boundary and the tail after the last word. The picture was then
    shorter than the voiceover, and the mux kept the picture.
    """
    if not scenes:
        return []
    ordered = [dict(scene) for scene in scenes]
    ordered.sort(key=lambda scene: float(scene.get("start_time", 0.0)))
    ordered[0]["start_time"] = 0.0
    for index in range(len(ordered) - 1):
        ordered[index]["end_time"] = float(ordered[index + 1].get("start_time", 0.0))
    tail = max(float(ordered[-1].get("end_time", 0.0)), float(audio_duration))
    ordered[-1]["end_time"] = tail
    for scene in ordered:
        start = float(scene["start_time"])
        end = max(start + 0.4, float(scene["end_time"]))
        scene["start_time"] = round(start, 3)
        scene["end_time"] = round(end, 3)
        scene["duration"] = round(end - start, 3)
    if ordered[-1]["end_time"] + 0.05 < float(audio_duration):
        ordered[-1]["end_time"] = round(float(audio_duration), 3)
        ordered[-1]["duration"] = round(
            ordered[-1]["end_time"] - ordered[-1]["start_time"],
            3,
        )
    return ordered


def render_voiceover_until_publishable(
    script: str,
    output_path: str,
    *,
    voice: str,
    speed: float,
    target_seconds: float,
    topic: str = "",
    synthesize: Synthesizer,
    max_attempts: int = 3,
) -> tuple[str, float, float]:
    """Synthesize, measure, and extend until the wav clears the target.

    ``synthesize(text, path, voice, speed)`` must write ``path`` and return the
    duration in seconds. The last attempt may slow the voice if extending the
    script was not enough. Returns ``(script, duration, speed_used)``.
    """
    target = max(MIN_PUBLISH_SECONDS, float(target_seconds))
    speed_used = max(0.8, float(speed))
    current = ensure_script_word_count(
        script,
        topic=topic,
        target_seconds=target,
        speed=speed_used,
        voice=voice,
    )
    duration = 0.0
    attempts = max(1, int(max_attempts))

    for attempt in range(1, attempts + 1):
        duration = float(synthesize(current, output_path, voice, speed_used))
        logger.info(
            "Voiceover attempt %d: %.2fs, %d words, speed %.2fx, target %.1fs",
            attempt,
            duration,
            len(current.split()),
            speed_used,
            target,
        )
        if duration + 0.05 >= target:
            return current, duration, speed_used
        # Scale the word budget by how far this real read fell short.
        stretch = (target / max(duration, 1.0)) * PLANNING_MARGIN
        needed = int(math.ceil(len(current.split()) * stretch))
        current = ensure_script_word_count(
            current,
            topic=topic,
            target_seconds=target * stretch,
            speed=speed_used,
            voice=voice,
        )
        if len(current.split()) < needed:
            current = ensure_script_word_count(
                current + " " + _expansion_beats(_subject_name(topic))[attempt % 8],
                topic=topic,
                target_seconds=target * stretch,
                speed=speed_used,
                voice=voice,
            )

    if duration + 0.05 < target:
        slower = max(0.8, speed_used * (duration / target) * 0.98)
        if slower < speed_used - 0.01:
            logger.info("Voiceover still %.2fs. Retrying at %.2fx.", duration, slower)
            speed_used = slower
            duration = float(synthesize(current, output_path, voice, speed_used))

    if duration + 1e-3 < MIN_PUBLISH_SECONDS:
        raise DurationShortfall(
            f"Voiceover is {duration:.2f}s after {attempts} extensions "
            f"({len(current.split())} words at {speed_used:.2f}x). "
            f"Need at least {MIN_PUBLISH_SECONDS:.0f}s."
        )
    return current, duration, speed_used
