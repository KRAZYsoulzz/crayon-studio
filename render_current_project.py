import os
import sys
import json
import shutil
import subprocess

# Ensure UTF-8 output on Windows
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass

from core.engine_router import VisualEngineRouter
from core.ffmpeg_compositor import FFmpegCompositor

def main():
    slug = "the-2-000-year-ancient-roman-concrete-secret"
    proj_dir = os.path.join("projects", slug)
    words_json = os.path.join(proj_dir, "words_timestamp.json")
    script_txt = os.path.join(proj_dir, "script.txt")
    vo_path = os.path.join(proj_dir, "voiceover.wav")
    foley_path = os.path.join(proj_dir, "foley_track.wav")
    raw_video = os.path.join(proj_dir, "scene_raw.mp4")
    final_mp4 = os.path.join(proj_dir, f"{slug}_final.mp4")

    with open(script_txt, "r", encoding="utf-8") as f:
        script = f.read().strip()

    print(f"[Main] Starting render for project '{slug}'...")

    router = VisualEngineRouter(
        visual_engine="2D_Crayon",
        ffmpeg_path="ffmpeg",
    )

    render_res = router.render_project(
        project_dir=proj_dir,
        words_json_path=words_json,
        output_mp4_path=raw_video,
        category="STEM",
        script_text=script,
        style_reference_path=None,
        progress_callback=lambda msg: print(f"[Progress] {msg}"),
    )

    print("[Main] Raw animation pass completed:", render_res.get("video_path"))

    print("[Main] Multiplexing with FFmpegCompositor...")
    comp = FFmpegCompositor(ffmpeg_path="ffmpeg")
    final_path = comp.composite_video(
        video_path=raw_video,
        voiceover_path=vo_path,
        words_json_path=words_json,
        output_mp4_path=final_mp4,
        foley_path=foley_path,
        progress_callback=lambda msg: print(f"[Compositor] {msg}"),
    )
    print(f"[Main] Final video generated: {final_path}")

    # Extract verification snapshots at key timestamps
    timestamps = [
        ("snapshot_turn_1_3s.png", 3.0),
        ("snapshot_turn_2_12s.png", 12.0),
        ("snapshot_turn_3_22s.png", 22.0),
        ("snapshot_turn_4_32s.png", 32.0),
        ("snapshot_turn_5_42s.png", 42.0),
        ("snapshot_turn_6_52s.png", 52.0),
    ]

    snap_dir = os.path.join(proj_dir, "preview_snapshots")
    os.makedirs(snap_dir, exist_ok=True)

    print("[Main] Extracting scene verification snapshots...")
    for snap_name, ts in timestamps:
        out_snap = os.path.join(snap_dir, snap_name)
        cmd = [
            "ffmpeg", "-y",
            "-ss", str(ts),
            "-i", final_path,
            "-vframes", "1",
            "-q:v", "2",
            out_snap,
        ]
        try:
            subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=True)
            print(f"  [Snap] Extracted {snap_name} at t={ts}s ({os.path.getsize(out_snap)} bytes)")
        except Exception as e:
            print(f"  [Snap] Failed for {snap_name}: {e}")

    # Copy to artifacts directory
    artifact_snap_dir = r"C:\Users\gagee\.gemini\antigravity\brain\ff31cf57-e3fa-475d-9649-62b68a4f7767\snapshots"
    os.makedirs(artifact_snap_dir, exist_ok=True)
    for snap_name, _ in timestamps:
        src = os.path.join(snap_dir, snap_name)
        if os.path.exists(src):
            shutil.copyfile(src, os.path.join(artifact_snap_dir, snap_name))

    print("[Main] Render and verification finished successfully!")

if __name__ == "__main__":
    main()
