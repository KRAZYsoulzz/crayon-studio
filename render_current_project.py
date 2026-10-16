import os
import sys
import json

if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass

from database.db import init_db, get_all_projects
from core.engine_router import VisualEngineRouter
from core.ffmpeg_compositor import FFmpegCompositor
from app import load_app_config, PROJECTS_ROOT


def main():
    init_db()
    config = load_app_config()
    projects = get_all_projects()
    if not projects:
        print("[CLI Render] No projects found in database.")
        return

    proj = projects[0]
    slug = proj["project_slug"]
    proj_dir = os.path.join(PROJECTS_ROOT, slug)
    os.makedirs(proj_dir, exist_ok=True)

    words_json = os.path.join(proj_dir, "words_timestamp.json")
    vo_path = os.path.join(proj_dir, "voiceover.wav")
    foley_path = os.path.join(proj_dir, "foley_track.wav")
    raw_video = os.path.join(proj_dir, "scene_raw.mp4")
    final_mp4 = os.path.join(proj_dir, f"{slug}_final.mp4")

    scenes = []
    if proj.get("storyboard_json"):
        try:
            scenes = json.loads(proj["storyboard_json"])
        except Exception:
            scenes = []

    router = VisualEngineRouter(
        visual_engine=proj.get("visual_engine", "3D_Pixar"),
        ffmpeg_path=config.get("ffmpeg_path", "ffmpeg"),
    )
    render_res = router.render_project(
        project_dir=proj_dir,
        words_json_path=words_json,
        output_mp4_path=raw_video,
        category=proj.get("category", "STEM"),
        script_text=proj.get("script_text", ""),
        render_mode=proj.get("render_mode", "smart_hybrid"),
        style_reference_path=proj.get("style_reference_path") or None,
        custom_scenes=scenes or None,
        progress_callback=lambda msg: print(f"[Render] {msg}"),
    )

    comp = FFmpegCompositor(ffmpeg_path=config.get("ffmpeg_path", "ffmpeg"))
    comp.composite_video(
        video_path=raw_video,
        voiceover_path=vo_path,
        words_json_path=words_json,
        output_mp4_path=final_mp4,
        foley_path=foley_path if os.path.exists(foley_path) else None,
        progress_callback=lambda msg: print(f"[Compositor] {msg}"),
    )

    report = render_res.get("critic_report", {})
    print(f"[CLI Render] Done: {final_mp4} | Critic: {report.get('notes')}")


if __name__ == "__main__":
    main()
