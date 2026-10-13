import os
import sys
import json
import glob
import shutil
import subprocess
from typing import Callable, Dict, List, Optional, Any


class FFmpegCompositor:
    """
    Production FFmpeg compositor & kinetic .ass subtitle engine for CrayonStudio.
    Handles word-level active highlighting, Foley audio ducking, sample-rate locking
    (-ar 44100 + async=1), and constant frame rate (30fps) H.264 multiplexing.
    """

    def __init__(self, ffmpeg_path: Optional[str] = None, fps: int = 30):
        self.fps = fps
        self.ffmpeg_path = ffmpeg_path or self.find_ffmpeg_executable()

    def validate_ffmpeg_binary(self) -> bool:
        """Check whether the configured FFmpeg binary is accessible."""
        try:
            result = subprocess.run(
                [self.ffmpeg_path, "-version"],
                capture_output=True,
                text=True,
                check=False,
                timeout=5,
            )
            return result.returncode == 0
        except Exception:
            return False

    @staticmethod
    def find_ffmpeg_executable(config_path: str = "config.json") -> str:
        """Locates the FFmpeg executable via config.json, system PATH, or common Windows install locations."""
        if os.path.exists(config_path):
            try:
                with open(config_path, "r", encoding="utf-8") as f:
                    cfg = json.load(f)
                    custom = cfg.get("ffmpeg_path", "")
                    if custom and os.path.exists(custom):
                        return custom
            except Exception:
                pass

        path_bin = shutil.which("ffmpeg")
        if path_bin:
            return path_bin

        if sys.platform == "win32":
            search_patterns = [
                os.path.expandvars(r"%LOCALAPPDATA%\Microsoft\WinGet\Packages\*ffmpeg*\*\bin\ffmpeg.exe"),
                r"C:\ffmpeg\bin\ffmpeg.exe",
                r"C:\Program Files\ffmpeg\bin\ffmpeg.exe",
                r"C:\ProgramData\chocolatey\bin\ffmpeg.exe",
            ]
            candidates = []
            for pattern in search_patterns:
                candidates.extend(glob.glob(pattern))
            if candidates:
                return candidates[0]

        return "ffmpeg"

    @staticmethod
    def _format_ass_time(seconds: float) -> str:
        """Converts float seconds into SubStation Alpha timestamp format (H:MM:SS.cc)."""
        seconds = max(0.0, float(seconds))
        hours = int(seconds // 3600)
        minutes = int((seconds % 3600) // 60)
        secs = int(seconds % 60)
        centiseconds = int(round((seconds - int(seconds)) * 100))
        if centiseconds >= 100:
            secs += 1
            centiseconds = 0
            if secs >= 60:
                minutes += 1
                secs = 0
        return f"{hours}:{minutes:02d}:{secs:02d}.{centiseconds:02d}"

    @staticmethod
    def _escape_ass_text(text: str) -> str:
        """Sanitizes raw word strings so they never break ASS override tags."""
        return (
            str(text)
            .replace("\\", "")
            .replace("{", "(")
            .replace("}", ")")
            .strip()
        )

    def generate_kinetic_ass(
        self,
        words_json_path: str,
        output_ass_path: str,
        max_words_per_group: int = 3,
    ) -> str:
        """
        Parses faster-whisper word timestamps and writes a 1080x1920 kinetic .ass file.
        - Groups words into snappy 2-3 word phrases.
        - Highlights the currently spoken word in warm Crayon Gold (&H00D7FF&) with a 112% pop scale.
        - Positions captions at MarginV=440 (safe zone above TikTok Shop anchor links & captions).
        """
        words: List[Dict[str, Any]] = []
        if os.path.exists(words_json_path):
            try:
                with open(words_json_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    words = data if isinstance(data, list) else data.get("words", [])
            except Exception:
                words = []

        # ASS Header configured for 1080x1920 vertical video
        # Note: ASS colors use &HAABBGGRR& hex order
        # Primary: Off-white (&H00F0F6F8), Highlight override: Gold (&H0014D7FF), Outline: Charcoal (&H00141414)
        ass_lines = [
            "[Script Info]",
            "Title: CrayonStudio Kinetic Captions",
            "ScriptType: v4.00+",
            "WrapStyle: 0",
            "ScaledBorderAndShadow: yes",
            "YCbCr Matrix: TV.709",
            "PlayResX: 1080",
            "PlayResY: 1920",
            "",
            "[V4+ Styles]",
            "Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, "
            "Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, "
            "Alignment, MarginL, MarginR, MarginV, Encoding",
            "Style: CrayonKinetic,Arial Rounded MT Bold,74,&H00F0F6F8,&H0014D7FF,&H00141414,&H80000000,"
            "-1,0,0,0,100,100,1.5,0,1,6.5,3.0,2,70,70,440,1",
            "",
            "[Events]",
            "Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text",
        ]

        if not words:
            os.makedirs(os.path.dirname(os.path.abspath(output_ass_path)), exist_ok=True)
            with open(output_ass_path, "w", encoding="utf-8") as f:
                f.write("\n".join(ass_lines) + "\n")
            return output_ass_path

        # Group words into punchy phrases (break on punctuation or max_words_per_group)
        groups: List[List[Dict[str, Any]]] = []
        current_group: List[Dict[str, Any]] = []

        for w in words:
            w_text = self._escape_ass_text(w.get("word", ""))
            if not w_text:
                continue
            item = {
                "word": w_text,
                "start": float(w.get("start", 0.0)),
                "end": float(w.get("end", 0.0)),
            }
            current_group.append(item)

            ends_sentence = any(w_text.endswith(p) for p in (".", "!", "?", ",", ";", ":"))
            if len(current_group) >= max_words_per_group or ends_sentence:
                groups.append(current_group)
                current_group = []

        if current_group:
            groups.append(current_group)

        # Build gapless word-highlight dialogue events for each group
        for g_idx, group in enumerate(groups):
            for w_idx, active_word in enumerate(group):
                start_t = active_word["start"]
                # Prevent micro-flickering between words inside the same phrase
                if w_idx < len(group) - 1:
                    next_start = group[w_idx + 1]["start"]
                    end_t = next_start if (next_start - active_word["end"]) < 0.25 else active_word["end"]
                else:
                    end_t = max(active_word["end"], start_t + 0.12)
                    if g_idx < len(groups) - 1:
                        next_group_start = groups[g_idx + 1][0]["start"]
                        end_t = min(end_t, next_group_start)

                if end_t <= start_t:
                    end_t = start_t + 0.10

                start_str = self._format_ass_time(start_t)
                end_str = self._format_ass_time(end_t)

                formatted_tokens = []
                for idx, token in enumerate(group):
                    upper_word = token["word"].upper()
                    if idx == w_idx:
                        # Active spoken word: Crayon Gold color + 114% scale pop
                        formatted_tokens.append(
                            f"{{\\1c&H0014D7FF&\\fscx114\\fscy114}}{upper_word}{{\\1c&H00F0F6F8&\\fscx100\\fscy100}}"
                        )
                    else:
                        formatted_tokens.append(upper_word)

                line_text = " ".join(formatted_tokens)
                ass_lines.append(
                    f"Dialogue: 0,{start_str},{end_str},CrayonKinetic,,0,0,0,,{line_text}"
                )

        os.makedirs(os.path.dirname(os.path.abspath(output_ass_path)), exist_ok=True)
        with open(output_ass_path, "w", encoding="utf-8") as f:
            f.write("\n".join(ass_lines) + "\n")

        return output_ass_path

    def composite_video(
        self,
        video_path: str,
        voiceover_path: str,
        words_json_path: str,
        output_mp4_path: str,
        foley_path: Optional[str] = None,
        foley_volume: float = 0.18,
        progress_callback: Optional[Callable[[str], None]] = None,
    ) -> str:
        """
        Multiplexes the rendered Blender video pass, Kokoro voiceover, optional Foley audio track,
        and kinetic .ass captions into the final 9:16 H.264 MP4 with strict audio/video sync locking.
        """
        if not os.path.exists(video_path):
            raise FileNotFoundError(f"Rendered video pass not found: {video_path}")
        if not os.path.exists(voiceover_path):
            raise FileNotFoundError(f"Voiceover audio file not found: {voiceover_path}")

        project_dir = os.path.dirname(os.path.abspath(output_mp4_path))
        os.makedirs(project_dir, exist_ok=True)

        # Write captions.ass directly inside project_dir and run with cwd=project_dir
        # This completely avoids Windows drive-letter colon escaping bugs in FFmpeg's libass filter
        local_ass_filename = "captions.ass"
        ass_full_path = os.path.join(project_dir, local_ass_filename)

        if progress_callback:
            progress_callback("[FFmpeg] Generating kinetic word-highlight .ass subtitles...")

        self.generate_kinetic_ass(
            words_json_path=words_json_path,
            output_ass_path=ass_full_path,
        )

        has_foley = bool(foley_path and os.path.exists(foley_path) and os.path.getsize(foley_path) > 128)

        # Construct filter_complex with 44.1kHz sample-rate locking and async timestamp drift correction
        if has_foley:
            filter_complex = (
                f"[0:v]fps={self.fps},ass={local_ass_filename}[vout];"
                f"[1:a]aresample=44100:async=1:first_pts=0,pan=stereo|c0=c0|c1=c0,volume=1.0[vo];"
                f"[2:a]aresample=44100:async=1:first_pts=0,volume={foley_volume:.2f}[sfx];"
                f"[vo][sfx]amix=inputs=2:duration=first:dropout_transition=2[aout]"
            )
        else:
            filter_complex = (
                f"[0:v]fps={self.fps},ass={local_ass_filename}[vout];"
                f"[1:a]aresample=44100:async=1:first_pts=0,pan=stereo|c0=c0|c1=c0,volume=1.0[aout]"
            )

        cmd = [
            self.ffmpeg_path,
            "-y",
            "-i", os.path.abspath(video_path),
            "-i", os.path.abspath(voiceover_path),
        ]
        if has_foley and foley_path:
            cmd.extend(["-i", os.path.abspath(foley_path)])

        cmd.extend([
            "-filter_complex", filter_complex,
            "-map", "[vout]",
            "-map", "[aout]",
            "-c:v", "libx264",
            "-preset", "medium",
            "-crf", "18",
            "-pix_fmt", "yuv420p",
            "-fps_mode", "cfr",
            "-r", str(self.fps),
            "-c:a", "aac",
            "-b:a", "192k",
            "-ar", "44100",
            "-movflags", "+faststart",
            "-shortest",
            os.path.abspath(output_mp4_path),
        ])

        if progress_callback:
            progress_callback(f"[FFmpeg] Multiplexing final 9:16 video and burning captions...")

        process = subprocess.Popen(
            cmd,
            cwd=project_dir,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            encoding="utf-8",
            errors="replace",
        )

        error_tail: List[str] = []
        if process.stdout:
            for line in process.stdout:
                clean = line.strip()
                if clean:
                    error_tail.append(clean)
                    if len(error_tail) > 25:
                        error_tail.pop(0)
                    if progress_callback and ("frame=" in clean or "Error" in clean):
                        progress_callback(f"[FFmpeg] {clean}")

        return_code = process.wait()
        if return_code != 0 or not os.path.exists(output_mp4_path):
            err_msg = "\n".join(error_tail[-10:])
            raise RuntimeError(f"FFmpeg compositor failed (exit code {return_code}):\n{err_msg}")

        if progress_callback:
            progress_callback(f"[FFmpeg] Final video exported: {output_mp4_path}")

        return output_mp4_path


# Top-level functional aliases so any function name generated in app.py connects seamlessly
def composite_final_video(
    video_path: str,
    voiceover_path: str,
    words_json_path: str,
    output_mp4_path: str,
    foley_path: Optional[str] = None,
    ffmpeg_path: Optional[str] = None,
    progress_callback: Optional[Callable[[str], None]] = None,
) -> str:
    compositor = FFmpegCompositor(ffmpeg_path=ffmpeg_path)
    return compositor.composite_video(
        video_path=video_path,
        voiceover_path=voiceover_path,
        words_json_path=words_json_path,
        output_mp4_path=output_mp4_path,
        foley_path=foley_path,
        progress_callback=progress_callback,
    )


compose_video = composite_final_video
burn_subtitles_and_merge = composite_final_video
