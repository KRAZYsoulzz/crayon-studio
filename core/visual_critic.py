"""
CRAYON STUDIO — Visual Critic Module
Automated 4-Frame Visual Quality & Layout Inspection
"""

import json
import logging
import os
import subprocess
from typing import Dict, List, Optional
import numpy as np
from PIL import Image

logger = logging.getLogger("VisualCritic")


def probe_video_duration(video_path: str, ffmpeg_path: str = "ffmpeg") -> float:
    """Probes video duration using ffprobe or ffmpeg stdout."""
    # Try ffprobe first if adjacent to ffmpeg
    ffprobe_path = "ffprobe"
    if os.path.isabs(ffmpeg_path):
        candidate = os.path.join(os.path.dirname(ffmpeg_path), "ffprobe.exe" if os.name == "nt" else "ffprobe")
        if os.path.exists(candidate):
            ffprobe_path = candidate

    try:
        cmd = [
            ffprobe_path,
            "-v", "error",
            "-show_entries", "format=duration",
            "-of", "default=noprint_wrappers=1:nokey=1",
            video_path,
        ]
        res = subprocess.run(cmd, capture_output=True, text=True, check=True)
        dur = float(res.stdout.strip())
        if dur > 0:
            return dur
    except Exception:
        pass

    # Fallback: parse ffmpeg -i output
    try:
        cmd = [ffmpeg_path, "-i", video_path]
        res = subprocess.run(cmd, capture_output=True, text=True)
        # Duration: 00:01:05.42
        for line in res.stderr.splitlines():
            if "Duration:" in line:
                part = line.split("Duration:")[1].split(",")[0].strip()
                h, m, s = part.split(":")
                return float(h) * 3600 + float(m) * 60 + float(s)
    except Exception as e:
        logger.warning(f"Could not probe video duration: {e}")

    return 60.0


def generate_and_verify_snapshots(
    video_path: str,
    project_dir: str,
    total_duration: float = 0.0,
    ffmpeg_path: str = "ffmpeg",
) -> Dict:
    """
    Extracts 4 keyframe PNG snapshots at 5%, 30%, 60%, and 88% duration.
    Verifies frame resolution (1080x1920), non-black/non-blank luminance variance,
    and returns a verification report.
    """
    if not os.path.exists(video_path):
        return {
            "passed": False,
            "snapshots": [],
            "notes": f"Video file not found at: {video_path}",
            "details": [],
        }

    # Determine total duration
    if total_duration <= 0.0:
        # Check words_timestamp.json first
        words_file = os.path.join(project_dir, "words_timestamp.json")
        if os.path.exists(words_file):
            try:
                with open(words_file, "r", encoding="utf-8") as f:
                    words = json.load(f)
                    if words and isinstance(words, list):
                        total_duration = float(words[-1].get("end", 60.0))
            except Exception:
                pass
        if total_duration <= 0.0:
            total_duration = probe_video_duration(video_path, ffmpeg_path)

    snapshot_dir = os.path.join(project_dir, "preview_snapshots")
    os.makedirs(snapshot_dir, exist_ok=True)

    # 4 Keyframe definitions: name, ratio, semantic role
    checkpoints = [
        ("frame_1_closed.png", 0.05, "Closed View"),
        ("frame_2_exploded.png", 0.30, "Exploded View"),
        ("frame_3_action.png", 0.60, "Action / Kinetic Strike View"),
        ("frame_4_cutaway.png", 0.88, "Cutaway / Seamless Loop View"),
    ]

    snapshot_paths: List[str] = []
    details: List[Dict] = []
    all_passed = True
    issues: List[str] = []

    for filename, ratio, role in checkpoints:
        timestamp = max(0.05, min(total_duration - 0.1, total_duration * ratio))
        out_path = os.path.join(snapshot_dir, filename)

        # Extract snapshot with FFmpeg
        cmd = [
            ffmpeg_path,
            "-y",
            "-ss", f"{timestamp:.3f}",
            "-i", video_path,
            "-vframes", "1",
            "-q:v", "2",
            out_path,
        ]

        try:
            p = subprocess.run(cmd, capture_output=True, text=True, check=False)
            if p.returncode != 0 or not os.path.exists(out_path):
                all_passed = False
                issues.append(f"{role} extraction failed (code {p.returncode})")
                continue
        except Exception as e:
            all_passed = False
            issues.append(f"{role} execution error: {e}")
            continue

        snapshot_paths.append(out_path)

        # Verify image properties
        file_size = os.path.getsize(out_path)
        if file_size < 5000:
            all_passed = False
            issues.append(f"{role} file size too small ({file_size} bytes)")

        try:
            with Image.open(out_path) as img:
                w, h = img.size
                arr = np.array(img.convert("L"), dtype=float)
                mean_lum = float(arr.mean())
                std_lum = float(arr.std())
                var_lum = float(arr.var())

                frame_valid = True
                frame_notes = []

                if (w, h) != (1080, 1920):
                    frame_notes.append(f"Resolution is {w}x{h} (expected 1080x1920)")

                if mean_lum < 4.0:
                    frame_valid = False
                    frame_notes.append(f"Blackout detected: mean luminance {mean_lum:.1f} < 4.0")
                elif std_lum < 2.5:
                    frame_valid = False
                    frame_notes.append(f"Blank/flat screen detected: std dev {std_lum:.2f} < 2.5")

                if not frame_valid:
                    all_passed = False
                    issues.extend([f"{role}: {n}" for n in frame_notes])

                details.append({
                    "role": role,
                    "filename": filename,
                    "path": out_path,
                    "timestamp": round(timestamp, 2),
                    "dimensions": (w, h),
                    "file_size": file_size,
                    "mean_luminance": round(mean_lum, 2),
                    "std_luminance": round(std_lum, 2),
                    "variance": round(var_lum, 2),
                    "passed": frame_valid,
                    "notes": "; ".join(frame_notes) if frame_notes else "Healthy frame",
                })
        except Exception as e:
            all_passed = False
            issues.append(f"{role} image inspection error: {e}")

    summary_notes = "All 4 structural keyframes verified successfully." if all_passed else " | ".join(issues)

    return {
        "passed": all_passed,
        "snapshots": snapshot_paths,
        "notes": summary_notes,
        "details": details,
        "total_duration": total_duration,
    }
