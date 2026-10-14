"""Universal Storybook Blender Orchestrator.

Renders 9:16 vertical educational short-form animations using:
- Procedural sketchbook watercolor paper shader (TexNoise + TexVoronoi)
- Textured wax crayon materials with organic pigment grain
- Smooth Cubic Bezier splines (type='BEZIER' with AUTO handles)
- Dynamic 3D callout labels derived from the script's actual words
- Purposeful process animations (draw progressive, pour along arc, fracture/fall, crystal growth)
- Continuous 5-zone camera navigation
- Automated 4-keyframe Visual Critic snapshot extraction
"""

from __future__ import annotations

import glob
import json
import logging
import math
import os
import shutil
import subprocess
import sys
from typing import Any, Callable, Dict, List, Optional, Tuple

from core.scene_choreographer import SceneChoreographer

logger = logging.getLogger("crayon_studio.blender_orchestrator")


class BlenderOrchestrator:
    """Bulletproof Blender 5.0 Visual Orchestrator using Bezier curves and procedural shaders."""

    def __init__(self, blender_path: Optional[str] = None, fps: int = 30):
        self.fps = fps
        if blender_path and (os.path.exists(blender_path) or shutil.which(blender_path)):
            self.blender_path = blender_path
        else:
            self.blender_path = self.find_blender_executable()

    def validate_blender_binary(self) -> bool:
        try:
            res = subprocess.run(
                [self.blender_path, "--version"],
                capture_output=True,
                text=True,
                check=False,
                timeout=5,
            )
            return res.returncode == 0
        except Exception:
            return False

    @staticmethod
    def find_blender_executable(config_path: str = "config.json") -> str:
        if os.path.exists(config_path):
            try:
                with open(config_path, "r", encoding="utf-8") as f:
                    cfg = json.load(f)
                    custom = cfg.get("blender_path", "")
                    if custom and os.path.exists(custom):
                        return custom
            except Exception:
                pass

        path_bin = shutil.which("blender")
        if path_bin:
            return path_bin

        if sys.platform == "win32":
            patterns = [
                r"C:\Program Files\Blender Foundation\Blender *\blender.exe",
                r"C:\Program Files (x86)\Blender Foundation\Blender *\blender.exe",
                os.path.expandvars(r"%LOCALAPPDATA%\Programs\Blender Foundation\Blender *\blender.exe"),
            ]
            candidates = []
            for p in patterns:
                candidates.extend(glob.glob(p))
            if candidates:
                candidates.sort(reverse=True)
                return candidates[0]
        elif sys.platform == "darwin":
            mac_path = "/Applications/Blender.app/Contents/MacOS/Blender"
            if os.path.exists(mac_path):
                return mac_path

        return "blender"

    def _build_headless_blender_script(
        self,
        blueprint: Dict[str, Any],
        output_mp4_path: str,
        preview_snapshots_dir: Optional[str] = None,
    ) -> str:
        """Constructs the complete standalone Python script executed inside headless Blender."""
        payload = {
            "fps": self.fps,
            "total_frames": blueprint["total_frames"],
            "total_duration": blueprint["total_duration"],
            "output_mp4_path": os.path.abspath(output_mp4_path),
            "preview_snapshots_dir": os.path.abspath(preview_snapshots_dir) if preview_snapshots_dir else "",
            "blueprint": blueprint,
        }
        payload_json = json.dumps(payload, indent=2)

        return f'''# Headless Blender 5.0 Universal Storybook Crayon Engine
import bpy
import os
import json
import math

PAYLOAD = json.loads(r"""{payload_json}""")

def setup_scene():
    bpy.ops.wm.read_factory_settings(use_empty=True)
    scene = bpy.context.scene
    scene.render.resolution_x = 1080
    scene.render.resolution_y = 1920
    scene.render.resolution_percentage = 100
    scene.render.fps = PAYLOAD["fps"]
    scene.frame_start = 1
    scene.frame_end = PAYLOAD["total_frames"]

    for eng in ["BLENDER_EEVEE", "BLENDER_EEVEE_NEXT", "BLENDER_WORKBENCH"]:
        try:
            scene.render.engine = eng
            break
        except Exception:
            pass

    if hasattr(scene.render.image_settings, "media_type"):
        try:
            scene.render.image_settings.media_type = 'VIDEO'
        except Exception:
            pass

    scene.render.image_settings.file_format = 'FFMPEG'
    scene.render.ffmpeg.format = 'MPEG4'
    scene.render.ffmpeg.codec = 'H264'
    scene.render.ffmpeg.constant_rate_factor = 'HIGH'
    scene.render.ffmpeg.ffmpeg_preset = 'GOOD'
    scene.render.filepath = PAYLOAD["output_mp4_path"]

    try:
        scene.view_settings.view_transform = 'Standard'
    except Exception:
        pass

    # Procedural Watercolor Sketchbook Paper World Shader
    world = bpy.data.worlds.new("PaperWorld")
    scene.world = world
    world.use_nodes = True
    nodes = world.node_tree.nodes
    links = world.node_tree.links
    nodes.clear()

    out = nodes.new(type='ShaderNodeOutputWorld')
    bg = nodes.new(type='ShaderNodeBackground')
    noise = nodes.new(type='ShaderNodeTexNoise')
    noise.inputs['Scale'].default_value = 450.0
    noise.inputs['Detail'].default_value = 8.0

    try:
        mix = nodes.new(type='ShaderNodeMix')
        mix.data_type = 'RGBA'
        mix.inputs['Factor'].default_value = 0.07
        mix.inputs[6].default_value = (0.96, 0.94, 0.89, 1.0)
        links.new(noise.outputs['Color'], mix.inputs[7])
        links.new(mix.outputs[2], bg.inputs['Color'])
    except Exception:
        bg.inputs['Color'].default_value = (0.96, 0.94, 0.89, 1.0)

    links.new(bg.outputs['Background'], out.inputs['Surface'])

    # 9:16 Orthographic Camera (Width = 3.2 units -> X spans -1.6 to +1.6, Y spans -2.84 to +2.84)
    cam_data = bpy.data.cameras.new("CrayonOrthoCam")
    cam_data.type = 'ORTHO'
    cam_data.ortho_scale = 3.2
    cam_obj = bpy.data.objects.new("CrayonOrthoCam", cam_data)
    scene.collection.objects.link(cam_obj)
    scene.camera = cam_obj
    cam_obj.location = (0.0, 0.0, 10.0)
    return scene, cam_obj

def make_textured_crayon_mat(name, rgba):
    """Creates an authentic wax crayon material with procedural pigment grain."""
    mat = bpy.data.materials.new(name=name)
    mat.use_nodes = True
    nodes = mat.node_tree.nodes
    links = mat.node_tree.links
    nodes.clear()

    out = nodes.new(type='ShaderNodeOutputMaterial')
    emis = nodes.new(type='ShaderNodeEmission')
    emis.inputs["Strength"].default_value = 1.0

    noise = nodes.new(type='ShaderNodeTexNoise')
    noise.inputs["Scale"].default_value = 180.0
    noise.inputs["Detail"].default_value = 6.0
    noise.inputs["Roughness"].default_value = 0.75

    ramp = nodes.new(type='ShaderNodeValToRGB')
    ramp.color_ramp.elements[0].position = 0.25
    ramp.color_ramp.elements[0].color = (0.75, 0.75, 0.75, 1.0)
    ramp.color_ramp.elements[1].position = 0.85
    ramp.color_ramp.elements[1].color = (1.0, 1.0, 1.0, 1.0)
    links.new(noise.outputs["Fac"], ramp.inputs["Fac"])

    try:
        mix = nodes.new(type='ShaderNodeMix')
        mix.data_type = 'RGBA'
        mix.blend_type = 'MULTIPLY'
        mix.inputs["Factor"].default_value = 0.40
        mix.inputs[6].default_value = rgba
        links.new(ramp.outputs["Color"], mix.inputs[7])
        links.new(mix.outputs[2], emis.inputs["Color"])
    except Exception:
        emis.inputs["Color"].default_value = rgba

    links.new(emis.outputs["Emission"], out.inputs["Surface"])
    return mat

def add_crayon_spline_object(name, strokes, mat, base_loc=(0.0, 0.0, 0.0), thickness=0.034, spline_type="BEZIER"):
    """Creates a 3D beveled Curve with smooth Cubic Bezier or crisp Poly points."""
    curve_data = bpy.data.curves.new(name=name, type='CURVE')
    curve_data.dimensions = '3D'
    curve_data.bevel_depth = thickness
    curve_data.bevel_resolution = 4
    curve_data.use_fill_caps = True
    curve_data.materials.append(mat)

    for pts in strokes:
        if spline_type == "BEZIER":
            spline = curve_data.splines.new(type='BEZIER')
            spline.resolution_u = 24
            spline.bezier_points.add(len(pts) - 1)
            for i, pt in enumerate(pts):
                bp = spline.bezier_points[i]
                bp.co = (pt[0], pt[1], pt[2] if len(pt) > 2 else 0.0)
                bp.handle_left_type = 'AUTO'
                bp.handle_right_type = 'AUTO'
        else:
            spline = curve_data.splines.new(type='POLY')
            spline.points.add(len(pts) - 1)
            for i, pt in enumerate(pts):
                spline.points[i].co = (pt[0], pt[1], pt[2] if len(pt) > 2 else 0.0, 1.0)

    obj = bpy.data.objects.new(name, curve_data)
    bpy.context.scene.collection.objects.link(obj)
    obj.location = base_loc
    return obj

def add_crayon_label(text, loc, mat, size=0.14):
    """Creates a clean 3D typography callout label beside diagrams."""
    clean_text = str(text).upper()[:22]
    font_data = bpy.data.curves.new(name=f"Lbl_{{clean_text[:6]}}", type='FONT')
    font_data.body = clean_text
    font_data.size = size
    font_data.extrude = 0.008
    font_data.materials.append(mat)

    obj = bpy.data.objects.new(name=f"Lbl_{{clean_text[:6]}}", object_data=font_data)
    bpy.context.scene.collection.objects.link(obj)
    obj.location = loc
    return obj

def keyframe_process_animation(obj, anim_spec, s_frame, e_frame, d_frames, base_loc):
    """Applies purposeful, one-directional cause-and-effect keyframe animations."""
    anim_type = anim_spec.get("type", "draw_stroke_progressive")
    start_offset = anim_spec.get("start_offset", 0)
    dur = anim_spec.get("duration", d_frames)

    act_start = s_frame + start_offset
    act_end = min(e_frame, act_start + dur)
    cd = obj.data

    if anim_type == "draw_stroke_progressive":
        if hasattr(cd, "bevel_factor_end"):
            if s_frame <= 1 and start_offset == 0:
                # Frame 1 Visual Incomplete Hook rule: 55% already drawn on frame 1
                cd.bevel_factor_end = 0.55
                cd.keyframe_insert(data_path="bevel_factor_end", frame=1)
            else:
                cd.bevel_factor_end = 0.0
                cd.keyframe_insert(data_path="bevel_factor_end", frame=1)
                cd.keyframe_insert(data_path="bevel_factor_end", frame=max(1, act_start - 1))

            cd.bevel_factor_end = 1.0
            cd.keyframe_insert(data_path="bevel_factor_end", frame=act_end)

    elif anim_type == "pour_along_arc":
        if hasattr(cd, "bevel_factor_start") and hasattr(cd, "bevel_factor_end"):
            cd.bevel_factor_start = 0.0
            cd.bevel_factor_end = 0.0
            cd.keyframe_insert(data_path="bevel_factor_start", frame=max(1, act_start - 1))
            cd.keyframe_insert(data_path="bevel_factor_end", frame=max(1, act_start - 1))

            # Stream stretches down
            mid_f = int((act_start + act_end) / 2)
            cd.bevel_factor_start = 0.0
            cd.bevel_factor_end = 1.0
            cd.keyframe_insert(data_path="bevel_factor_end", frame=mid_f)

            # Tail follows into vessel
            cd.bevel_factor_start = 1.0
            cd.keyframe_insert(data_path="bevel_factor_start", frame=act_end)

    elif anim_type == "fracture_and_fall":
        # Draw crack line first
        if hasattr(cd, "bevel_factor_end"):
            cd.bevel_factor_end = 0.0
            cd.keyframe_insert(data_path="bevel_factor_end", frame=max(1, act_start - 1))
            cd.bevel_factor_end = 1.0
            cd.keyframe_insert(data_path="bevel_factor_end", frame=act_start + 8)

        # Then accelerate detached piece downward (gravity)
        bx, by, bz = base_loc
        fall_start = act_start + 8
        fall_dur = max(6, act_end - fall_start)
        for f in range(fall_start, act_end + 1, 3):
            t = (f - fall_start) / float(fall_dur)
            drop = 0.45 * (t ** 2)  # Parabolic gravitational drop
            obj.location = (bx, by - drop, bz)
            obj.keyframe_insert(data_path="location", frame=f)

    elif anim_type == "grow_and_interlock":
        # Structure scales outward and locks still
        obj.scale = (0.05, 1.0, 1.0)
        obj.keyframe_insert(data_path="scale", frame=max(1, act_start - 1))
        obj.scale = (1.0, 1.0, 1.0)
        obj.keyframe_insert(data_path="scale", frame=act_end)

    elif anim_type == "flow_through_channel":
        if hasattr(cd, "bevel_factor_start") and hasattr(cd, "bevel_factor_end"):
            cd.bevel_factor_start = 0.0
            cd.bevel_factor_end = 0.0
            cd.keyframe_insert(data_path="bevel_factor_start", frame=max(1, act_start - 1))
            cd.keyframe_insert(data_path="bevel_factor_end", frame=max(1, act_start - 1))

            mid_f = int((act_start + act_end) / 2)
            cd.bevel_factor_end = 1.0
            cd.keyframe_insert(data_path="bevel_factor_end", frame=mid_f)

            cd.bevel_factor_start = 0.2
            cd.keyframe_insert(data_path="bevel_factor_start", frame=act_end)

def capture_snapshots_if_requested(scene, snapshot_dir):
    """Captures 4 keyframe PNG snapshots at 5%, 30%, 60%, and 88% timeline for Visual Critic."""
    if not snapshot_dir:
        return
    os.makedirs(snapshot_dir, exist_ok=True)

    total_f = PAYLOAD["total_frames"]
    checkpoints = [
        ("frame_1_closed.png", max(1, int(total_f * 0.05))),
        ("frame_2_exploded.png", max(2, int(total_f * 0.30))),
        ("frame_3_action.png", max(3, int(total_f * 0.60))),
        ("frame_4_cutaway.png", max(4, int(total_f * 0.88))),
    ]

    orig_format = scene.render.image_settings.file_format
    if hasattr(scene.render.image_settings, "media_type"):
        try:
            scene.render.image_settings.media_type = 'IMAGE'
        except Exception:
            pass
    scene.render.image_settings.file_format = 'PNG'

    for fname, f_num in checkpoints:
        out_path = os.path.join(snapshot_dir, fname)
        scene.frame_set(f_num)
        scene.render.filepath = out_path
        try:
            bpy.ops.render.render(write_still=True)
            print(f"[CrayonStudio] Visual Critic snapshot saved: {{out_path}} (frame {{f_num}})")
        except Exception as e:
            print(f"[CrayonStudio] Snapshot failed for frame {{f_num}}: {{e}}")

    # Restore video format
    if hasattr(scene.render.image_settings, "media_type"):
        try:
            scene.render.image_settings.media_type = 'VIDEO'
        except Exception:
            pass
    scene.render.image_settings.file_format = orig_format
    scene.render.filepath = PAYLOAD["output_mp4_path"]

def build_full_story():
    scene, cam_obj = setup_scene()
    cam_data = cam_obj.data

    mats = {{
        "blue": make_textured_crayon_mat("CrayonBlue", (0.12, 0.42, 0.88, 1.0)),
        "red": make_textured_crayon_mat("CrayonRed", (0.88, 0.18, 0.20, 1.0)),
        "gold": make_textured_crayon_mat("CrayonGold", (0.92, 0.62, 0.06, 1.0)),
        "green": make_textured_crayon_mat("CrayonGreen", (0.14, 0.70, 0.32, 1.0)),
        "charcoal": make_textured_crayon_mat("CrayonCharcoal", (0.18, 0.18, 0.20, 1.0)),
        "cyan": make_textured_crayon_mat("CrayonCyan", (0.06, 0.75, 0.88, 1.0)),
        "white": make_textured_crayon_mat("CrayonWhite", (0.95, 0.95, 0.95, 1.0)),
    }}

    blueprint = PAYLOAD["blueprint"]
    acts = blueprint.get("acts", [])
    zones = blueprint.get("canvas_zones", [])

    for act in acts:
        idx = act["act_index"]
        zx, zy = act["zone_coords"]
        s_frame = act["start_frame"]
        e_frame = act["end_frame"]
        d_frames = act["draw_frames"]

        # Build each component curve
        for comp in act.get("components", []):
            c_name = f"Act{{idx}}_{{comp['name']}}"
            c_type = comp.get("spline_type", "BEZIER")
            c_mat = mats.get(comp.get("color", "charcoal"), mats["charcoal"])
            c_thick = comp.get("thickness", 0.034)
            strokes = comp.get("strokes", [])

            c_obj = add_crayon_spline_object(
                name=c_name,
                strokes=strokes,
                mat=c_mat,
                base_loc=(zx, zy, 0.0),
                thickness=c_thick,
                spline_type=c_type,
            )

            anim = comp.get("animation", {{}})
            keyframe_process_animation(c_obj, anim, s_frame, e_frame, d_frames, (zx, zy, 0.0))

        # Add 3D Typography Callout Labels
        labels = act.get("labels", {{}})
        if "left" in labels and "right" in labels:
            lbl_l = add_crayon_label(labels["left"], (zx - 1.10, zy - 0.25, 0.05), mats["charcoal"], size=0.13)
            lbl_r = add_crayon_label(labels["right"], (zx + 0.18, zy - 0.25, 0.05), mats["charcoal"], size=0.13)
            if "center" in labels:
                add_crayon_label(labels["center"], (zx - 0.12, zy + 0.45, 0.06), mats["gold"], size=0.18)
        elif "title" in labels:
            add_crayon_label(labels["title"], (zx - 0.85, zy + 1.25, 0.05), mats["green"], size=0.15)
            if "status" in labels:
                add_crayon_label(labels["status"], (zx - 0.65, zy - 0.28, 0.05), mats["gold"], size=0.13)
        elif "arch" in labels:
            add_crayon_label(labels["arch"], (zx - 0.70, zy - 0.22, 0.05), mats["blue"], size=0.14)
            if "keystone" in labels:
                add_crayon_label(labels["keystone"], (zx - 0.60, zy + 1.25, 0.05), mats["gold"], size=0.13)
        elif "vault" in labels:
            add_crayon_label(labels["vault"], (zx - 0.90, zy + 1.25, 0.05), mats["charcoal"], size=0.14)
            if "status" in labels:
                add_crayon_label(labels["status"], (zx - 0.45, zy - 0.25, 0.05), mats["green"], size=0.13)

        # Connector trails between zones on continuous giant sheet
        if idx < len(zones) - 1:
            nx, ny = zones[idx + 1]
            trail = [[(zx + 1.35, zy + 0.55), (nx - 1.35, ny + 0.55)]]
            tr_obj = add_crayon_spline_object(
                name=f"Trail_{{idx}}",
                strokes=trail,
                mat=mats["gold"],
                base_loc=(0.0, 0.0, -0.05),
                thickness=0.022,
                spline_type="BEZIER",
            )
            cd = tr_obj.data
            cd.bevel_factor_end = 0.0
            cd.keyframe_insert(data_path="bevel_factor_end", frame=max(1, e_frame - 18))
            cd.bevel_factor_end = 1.0
            cd.keyframe_insert(data_path="bevel_factor_end", frame=e_frame)

        # Continuous camera glide with subtle ease and zoom
        pan_in_f = max(1, s_frame + 12) if idx > 0 else 1
        hold_f = max(pan_in_f + 5, e_frame - 12)
        mid_f = int((pan_in_f + hold_f) / 2)

        cam_obj.location = (zx, zy, 10.0)
        cam_obj.keyframe_insert(data_path="location", frame=pan_in_f)
        cam_obj.keyframe_insert(data_path="location", frame=hold_f)

        cam_data.ortho_scale = 3.2
        cam_data.keyframe_insert(data_path="ortho_scale", frame=pan_in_f)
        cam_data.ortho_scale = 2.85
        cam_data.keyframe_insert(data_path="ortho_scale", frame=mid_f)
        cam_data.ortho_scale = 3.2
        cam_data.keyframe_insert(data_path="ortho_scale", frame=hold_f)

    # Capture 4-keyframe snapshots for Visual Critic before animation render
    capture_snapshots_if_requested(scene, PAYLOAD.get("preview_snapshots_dir"))

    print(f"[CrayonStudio] Rendering {{PAYLOAD['total_frames']}} frames to {{PAYLOAD['output_mp4_path']}}...")
    bpy.ops.render.render(animation=True)
    print("[CrayonStudio] Render finished successfully.")

if __name__ == "__main__":
    build_full_story()
'''

    def render_project(
        self,
        project_dir: str,
        words_json_path: str,
        output_mp4_path: str,
        category: str = "STEM",
        script_text: Optional[str] = None,
        duration_override: Optional[float] = None,
        progress_callback: Optional[Callable[[str], None]] = None,
    ) -> str:
        """Executes full storyboard choreography and headless Blender render."""
        os.makedirs(project_dir, exist_ok=True)

        # 1. Recover script text if not directly passed
        if not script_text:
            script_txt_path = os.path.join(project_dir, "script.txt")
            if os.path.exists(script_txt_path):
                with open(script_txt_path, "r", encoding="utf-8") as f:
                    script_text = f.read().strip()
            elif os.path.exists(words_json_path):
                try:
                    with open(words_json_path, "r", encoding="utf-8") as f:
                        data = json.load(f)
                        words = data if isinstance(data, list) else data.get("words", [])
                        script_text = " ".join(w.get("word", "") for w in words).strip()
                except Exception:
                    script_text = "Educational storybook animation"
            else:
                script_text = "Educational storybook animation"

        # 2. Choreograph universal 5-act visual blueprint
        if progress_callback:
            progress_callback("🎨 Choreographing dynamic visual blueprint with Bezier splines...")

        choreographer = SceneChoreographer(fps=self.fps)
        blueprint = choreographer.choreograph_project(
            project_dir=project_dir,
            script_text=script_text,
            words_json_path=words_json_path,
            category=category,
            duration_override=duration_override,
        )

        # 3. Generate headless Blender scene script
        script_path = os.path.join(project_dir, "_run_blender_scene.py")
        snapshots_dir = os.path.join(project_dir, "preview_snapshots")
        script_content = self._build_headless_blender_script(
            blueprint=blueprint,
            output_mp4_path=output_mp4_path,
            preview_snapshots_dir=snapshots_dir,
        )
        with open(script_path, "w", encoding="utf-8") as f:
            f.write(script_content)

        # 4. Execute headless Blender render
        cmd = [
            self.blender_path,
            "--background",
            "--factory-startup",
            "--python-exit-code",
            "1",
            "--python",
            script_path,
        ]

        if progress_callback:
            progress_callback(f"[Blender] Rendering {blueprint['total_frames']} frames with textured paper & Bezier crayon...")

        process = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            encoding="utf-8",
            errors="replace",
        )

        output_tail: List[str] = []
        if process.stdout:
            for line in process.stdout:
                clean_line = line.strip()
                if clean_line:
                    output_tail.append(clean_line)
                    if len(output_tail) > 25:
                        output_tail.pop(0)
                    if progress_callback and (
                        "Fra:" in clean_line
                        or "[CrayonStudio]" in clean_line
                        or "Error" in clean_line
                        or "Traceback" in clean_line
                    ):
                        progress_callback(f"[Blender] {clean_line}")

        return_code = process.wait()
        if return_code != 0 or not os.path.exists(output_mp4_path):
            tb = "\n".join(output_tail[-15:])
            raise RuntimeError(f"Blender exited with code {return_code}:\n{tb}")

        return output_mp4_path


def render_crayon_animation(
    project_dir: str,
    words_json_path: str,
    output_mp4_path: str,
    category: str = "Architecture",
    script_text: Optional[str] = None,
    blender_path: Optional[str] = None,
    progress_callback: Optional[Callable[[str], None]] = None,
) -> str:
    orchestrator = BlenderOrchestrator(blender_path=blender_path)
    return orchestrator.render_project(
        project_dir=project_dir,
        words_json_path=words_json_path,
        output_mp4_path=output_mp4_path,
        category=category,
        script_text=script_text,
        progress_callback=progress_callback,
    )
