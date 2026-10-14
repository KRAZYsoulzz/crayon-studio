import os
import sys
import json
import glob
import math
import shutil
import subprocess
from typing import Callable, Dict, List, Optional, Tuple, Any


class BlenderOrchestrator:
    """
    Bulletproof Blender 4.x / 5.0 2D Crayon Animation Engine.
    Uses native 3D beveled Curve primitives with Emission Crayon Shaders and
    bevel_factor_end draw-on keyframes on a continuous 5-zone canvas.
    Eliminates SVG import scaling/material bugs 100%.
    """

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

    def parse_word_cues(
        self,
        words_json_path: str,
        default_duration: float = 65.0,
    ) -> Tuple[float, List[Dict[str, Any]]]:
        words: List[Dict[str, Any]] = []
        if os.path.exists(words_json_path):
            try:
                with open(words_json_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    words = data if isinstance(data, list) else data.get("words", [])
            except Exception:
                words = []

        total_duration = default_duration
        if words:
            last_end = float(words[-1].get("end", default_duration))
            total_duration = max(last_end + 0.5, 10.0)

        act_ratios = [0.0, 0.16, 0.36, 0.58, 0.80]
        scenes = []
        act_names = [
            "Act1_Hook_Incomplete",
            "Act2_Core_Mechanism",
            "Act3_Obstacle_Friction",
            "Act4_Trigger_Action",
            "Act5_Resolution_Bridge",
        ]

        for i in range(5):
            start_s = round(total_duration * act_ratios[i], 2)
            end_s = round(total_duration * act_ratios[i + 1], 2) if i < 4 else total_duration
            start_frame = 1 if i == 0 else max(2, int(round(start_s * self.fps)))
            end_frame = max(start_frame + 20, int(round(end_s * self.fps)))
            scenes.append({
                "index": i,
                "name": act_names[i],
                "start_frame": start_frame,
                "end_frame": end_frame,
                "draw_frames": min(40, max(15, int((end_frame - start_frame) * 0.25))),
            })

        return total_duration, scenes

    def _build_headless_blender_script(
        self,
        scenes: List[Dict[str, Any]],
        output_mp4_path: str,
        total_duration: float,
        category: str = "Architecture",
    ) -> str:
        payload = {
            "fps": self.fps,
            "total_frames": int(math.ceil(total_duration * self.fps)),
            "output_mp4_path": os.path.abspath(output_mp4_path),
            "scenes": scenes,
            "category": category,
        }
        payload_json = json.dumps(payload, indent=2)

        return f'''# Headless Blender 5.0 Native Curve Crayon Engine (Zero-SVG)
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

    # Warm Cream Sketchbook Paper World
    world = bpy.data.worlds.new("PaperWorld")
    scene.world = world
    world.use_nodes = True
    bg = world.node_tree.nodes.get("Background")
    if bg:
        bg.inputs[0].default_value = (0.96, 0.94, 0.89, 1.0)
        bg.inputs[1].default_value = 1.0

    # 9:16 Orthographic Camera (Width = 3.2 units -> X spans -1.6 to +1.6, Y spans -2.84 to +2.84)
    cam_data = bpy.data.cameras.new("CrayonOrthoCam")
    cam_data.type = 'ORTHO'
    cam_data.ortho_scale = 3.2
    cam_obj = bpy.data.objects.new("CrayonOrthoCam", cam_data)
    scene.collection.objects.link(cam_obj)
    scene.camera = cam_obj
    cam_obj.location = (0.0, 0.0, 10.0)
    return scene, cam_obj

def make_crayon_mat(name, rgba):
    mat = bpy.data.materials.new(name=name)
    mat.use_nodes = True
    nodes = mat.node_tree.nodes
    links = mat.node_tree.links
    nodes.clear()

    out = nodes.new(type='ShaderNodeOutputMaterial')
    emis = nodes.new(type='ShaderNodeEmission')
    emis.inputs["Color"].default_value = rgba
    emis.inputs["Strength"].default_value = 1.0
    links.new(emis.outputs["Emission"], out.inputs["Surface"])
    return mat

def add_crayon_curve(name, strokes, mat, base_loc=(0.0, 0.0, 0.0), thickness=0.034, cyclic=False):
    """Creates a bold, visible 3D beveled Curve object from a list of 2D/3D point lists."""
    curve_data = bpy.data.curves.new(name=name, type='CURVE')
    curve_data.dimensions = '3D'
    curve_data.bevel_depth = thickness
    curve_data.bevel_resolution = 4
    curve_data.use_fill_caps = True
    curve_data.materials.append(mat)

    for pts in strokes:
        spline = curve_data.splines.new(type='POLY')
        spline.points.add(len(pts) - 1)
        for i, pt in enumerate(pts):
            x, y = pt[0], pt[1]
            z = pt[2] if len(pt) > 2 else 0.0
            spline.points[i].co = (x, y, z, 1.0)
        spline.use_cyclic_u = cyclic

    obj = bpy.data.objects.new(name, curve_data)
    bpy.context.scene.collection.objects.link(obj)
    obj.location = base_loc
    return obj

def circle_pts(cx, cy, r, n=28):
    return [(cx + r * math.cos(2 * math.pi * i / n), cy + r * math.sin(2 * math.pi * i / n)) for i in range(n + 1)]

def rect_pts(cx, cy, w, h):
    hw, hh = w / 2.0, h / 2.0
    return [(cx - hw, cy - hh), (cx + hw, cy - hh), (cx + hw, cy + hh), (cx - hw, cy + hh), (cx - hw, cy - hh)]

def wave_pts(x0, x1, y_base, amp, freq, n=32):
    pts = []
    for i in range(n + 1):
        t = i / float(n)
        x = x0 + (x1 - x0) * t
        y = y_base + amp * math.sin(t * math.pi * 2.0 * freq)
        pts.append((x, y))
    return pts

def keyframe_draw_in(obj, start_f, draw_frames):
    cd = obj.data
    if start_f > 1:
        cd.bevel_factor_end = 0.0
        cd.keyframe_insert(data_path="bevel_factor_end", frame=1)
        cd.keyframe_insert(data_path="bevel_factor_end", frame=max(1, start_f - 1))
    else:
        # Frame 1 Visual Incomplete Rule: already 55% drawn on Frame 1!
        cd.bevel_factor_end = 0.55
        cd.keyframe_insert(data_path="bevel_factor_end", frame=1)

    cd.bevel_factor_end = 1.0
    cd.keyframe_insert(data_path="bevel_factor_end", frame=start_f + draw_frames)

def keyframe_continuous_motion(obj, motion, start_f, end_f, base_loc):
    bx, by, bz = base_loc
    step = 6
    for f in range(start_f, end_f + step, step):
        t = (f - start_f) / max(1.0, float(end_f - start_f))
        if motion == "wave_slosh":
            obj.location = (bx + 0.14 * math.sin(f * 0.15), by + 0.07 * math.cos(f * 0.15), bz)
            obj.keyframe_insert(data_path="location", frame=f)
        elif motion == "pulse_grow":
            s = 1.0 + 0.12 * math.sin(f * 0.18)
            obj.scale = (s, s, 1.0)
            obj.keyframe_insert(data_path="scale", frame=f)
        elif motion == "hinge_rock":
            obj.rotation_euler = (0.0, 0.0, math.radians(16.0 * math.sin(f * 0.14)))
            obj.keyframe_insert(data_path="rotation_euler", frame=f)
        elif motion == "fall_in":
            drop = max(0.0, 1.0 - min(1.0, t * 2.2)) * 0.65
            bob = 0.05 * math.sin(f * 0.2)
            obj.location = (bx, by + drop + bob, bz)
            obj.keyframe_insert(data_path="location", frame=f)
        elif motion == "converge_lock":
            squeeze = min(1.0, t * 1.5) * 0.22
            obj.scale = (1.0 - squeeze * 0.3, 1.0 + squeeze * 0.3, 1.0)
            obj.keyframe_insert(data_path="scale", frame=f)

def build_act_geometry(act_idx, zone_x, zone_y, s_frame, e_frame, d_frames, mats):
    """Builds bold, multi-part diagrams filling X: [-1.15, +1.15], Y: [-0.15, +1.35] around zone center."""
    # Draw subtle notebook frame card + grid lines so canvas always looks rich
    frame_strokes = [
        rect_pts(0.0, 0.55, 2.55, 1.85),
        [(-1.27, 1.25), (1.27, 1.25)],
    ]
    card = add_crayon_curve(f"Card_Act{{act_idx}}", frame_strokes, mats["charcoal"], (zone_x, zone_y, -0.1), thickness=0.016)
    keyframe_draw_in(card, s_frame, 10)

    if act_idx == 0:
        # ACT 1: Roman Harbor Seawall vs Crashing Ocean Waves (Hook)
        seawall = [
            rect_pts(-0.48, 0.45, 0.82, 1.15),
            [(-0.89, 0.75), (-0.07, 0.75)],
            [(-0.89, 0.45), (-0.07, 0.45)],
            [(-0.89, 0.15), (-0.07, 0.15)],
            [(-0.48, 1.02), (-0.48, -0.12)],
        ]
        o1 = add_crayon_curve("Act1_Seawall", seawall, mats["charcoal"], (zone_x, zone_y, 0.0), thickness=0.036)
        keyframe_draw_in(o1, 1, 12)

        waves = [
            wave_pts(0.05, 1.15, 0.75, 0.14, 2.0),
            wave_pts(0.05, 1.15, 0.42, 0.14, 2.0),
            wave_pts(0.05, 1.15, 0.10, 0.14, 2.0),
        ]
        o2 = add_crayon_curve("Act1_Waves", waves, mats["blue"], (zone_x, zone_y, 0.05), thickness=0.038)
        keyframe_draw_in(o2, s_frame + 4, d_frames)
        keyframe_continuous_motion(o2, "wave_slosh", s_frame, e_frame, (zone_x, zone_y, 0.05))

        impact_arrows = [
            [(0.55, 1.05), (0.02, 0.85)],
            [(0.20, 0.98), (0.02, 0.85), (0.22, 0.76)],
            [(0.55, 0.55), (0.02, 0.55)],
            [(0.20, 0.65), (0.02, 0.55), (0.20, 0.45)],
        ]
        o3 = add_crayon_curve("Act1_Impact", impact_arrows, mats["red"], (zone_x, zone_y, 0.08), thickness=0.034)
        keyframe_draw_in(o3, s_frame + 10, d_frames)
        keyframe_continuous_motion(o3, "pulse_grow", s_frame, e_frame, (zone_x, zone_y, 0.08))

    elif act_idx == 1:
        # ACT 2: Electron Microscope & Volcanic Ash / Quicklime Mix
        micro_ring = [circle_pts(0.0, 0.55, 0.72, 36), circle_pts(0.0, 0.55, 0.82, 36)]
        o1 = add_crayon_curve("Act2_ScopeRing", micro_ring, mats["blue"], (zone_x, zone_y, 0.0), thickness=0.032)
        keyframe_draw_in(o1, s_frame, d_frames)

        ash_clasts = [
            circle_pts(-0.32, 0.75, 0.18, 7),
            circle_pts(0.28, 0.72, 0.21, 6),
            circle_pts(-0.18, 0.30, 0.19, 8),
            circle_pts(0.26, 0.32, 0.16, 7),
        ]
        o2 = add_crayon_curve("Act2_VolcanicAsh", ash_clasts, mats["red"], (zone_x, zone_y, 0.05), thickness=0.036)
        keyframe_draw_in(o2, s_frame + 8, d_frames)
        keyframe_continuous_motion(o2, "pulse_grow", s_frame, e_frame, (zone_x, zone_y, 0.05))

        lime_sparks = [
            [(-0.32, 1.08), (-0.32, 0.96)],
            [(0.28, 1.08), (0.28, 0.96)],
            [(-0.62, 0.55), (0.62, 0.55)],
        ]
        o3 = add_crayon_curve("Act2_Quicklime", lime_sparks, mats["gold"], (zone_x, zone_y, 0.08), thickness=0.032)
        keyframe_draw_in(o3, s_frame + 14, d_frames)
        keyframe_continuous_motion(o3, "hinge_rock", s_frame, e_frame, (zone_x, zone_y, 0.08))

    elif act_idx == 2:
        # ACT 3: Seawater Infiltrating Micro-Cracks
        cracked_block = [
            rect_pts(0.0, 0.55, 1.95, 1.25),
            [(-0.15, 1.17), (0.12, 0.82), (-0.22, 0.52), (0.18, 0.22), (-0.08, -0.07)],
        ]
        o1 = add_crayon_curve("Act3_CrackedWall", cracked_block, mats["charcoal"], (zone_x, zone_y, 0.0), thickness=0.036)
        keyframe_draw_in(o1, s_frame, d_frames)

        water_streams = [
            wave_pts(-0.85, 0.85, 0.85, 0.09, 3.0),
            wave_pts(-0.85, 0.85, 0.55, 0.09, 3.0),
            wave_pts(-0.85, 0.85, 0.25, 0.09, 3.0),
        ]
        o2 = add_crayon_curve("Act3_SeawaterFlow", water_streams, mats["blue"], (zone_x, zone_y, 0.05), thickness=0.034)
        keyframe_draw_in(o2, s_frame + 6, d_frames)
        keyframe_continuous_motion(o2, "wave_slosh", s_frame, e_frame, (zone_x, zone_y, 0.05))

        reaction_nodes = [
            circle_pts(0.12, 0.82, 0.14, 16),
            circle_pts(-0.22, 0.52, 0.14, 16),
            circle_pts(0.18, 0.22, 0.14, 16),
        ]
        o3 = add_crayon_curve("Act3_ReactionZones", reaction_nodes, mats["gold"], (zone_x, zone_y, 0.08), thickness=0.036)
        keyframe_draw_in(o3, s_frame + 12, d_frames)
        keyframe_continuous_motion(o3, "pulse_grow", s_frame, e_frame, (zone_x, zone_y, 0.08))

    elif act_idx == 3:
        # ACT 4: Aluminous Tobermorite Crystal Lattice Growing Across the Void
        gap_walls = [
            [(-0.75, 1.15), (-0.55, -0.05)],
            [(0.75, 1.15), (0.55, -0.05)],
        ]
        o1 = add_crayon_curve("Act4_PoreWalls", gap_walls, mats["charcoal"], (zone_x, zone_y, 0.0), thickness=0.042)
        keyframe_draw_in(o1, s_frame, d_frames)

        crystals = [
            [(-0.65, 0.95), (0.65, 0.72), (-0.60, 0.48), (0.60, 0.25), (-0.55, 0.05)],
            [(0.65, 0.95), (-0.65, 0.72), (0.60, 0.48), (-0.60, 0.25), (0.55, 0.05)],
            circle_pts(0.0, 0.83, 0.15, 6),
            circle_pts(0.0, 0.60, 0.17, 6),
            circle_pts(0.0, 0.36, 0.15, 6),
        ]
        o2 = add_crayon_curve("Act4_TobermoriteCrystals", crystals, mats["green"], (zone_x, zone_y, 0.06), thickness=0.036)
        keyframe_draw_in(o2, s_frame + 6, d_frames)
        keyframe_continuous_motion(o2, "pulse_grow", s_frame, e_frame, (zone_x, zone_y, 0.06))

        bonds = [
            [(-0.35, 0.83), (0.35, 0.83)],
            [(-0.38, 0.60), (0.38, 0.60)],
            [(-0.35, 0.36), (0.35, 0.36)],
        ]
        o3 = add_crayon_curve("Act4_CrystalBonds", bonds, mats["gold"], (zone_x, zone_y, 0.09), thickness=0.032)
        keyframe_draw_in(o3, s_frame + 12, d_frames)
        keyframe_continuous_motion(o3, "converge_lock", s_frame, e_frame, (zone_x, zone_y, 0.09))

    else:
        # ACT 5: Self-Healing Roman Arch Locked Solid Under Load
        arch_stones = [
            circle_pts(0.0, 0.25, 0.88, 12),
            circle_pts(0.0, 0.25, 0.52, 12),
            [(-0.95, 0.25), (0.95, 0.25)],
        ]
        o1 = add_crayon_curve("Act5_RomanArch", arch_stones, mats["blue"], (zone_x, zone_y, 0.0), thickness=0.038)
        keyframe_draw_in(o1, s_frame, d_frames)

        keystone = [
            rect_pts(0.0, 0.96, 0.36, 0.38),
            [(-0.45, 1.32), (0.0, 1.15), (0.45, 1.32)],
        ]
        o2 = add_crayon_curve("Act5_Keystone", keystone, mats["gold"], (zone_x, zone_y, 0.06), thickness=0.040)
        keyframe_draw_in(o2, s_frame + 6, d_frames)
        keyframe_continuous_motion(o2, "fall_in", s_frame, e_frame, (zone_x, zone_y, 0.06))

        shield_check = [
            [(-0.28, 0.52), (-0.05, 0.30), (0.38, 0.76)],
        ]
        o3 = add_crayon_curve("Act5_Checkmark", shield_check, mats["green"], (zone_x, zone_y, 0.09), thickness=0.044)
        keyframe_draw_in(o3, s_frame + 14, d_frames)
        keyframe_continuous_motion(o3, "pulse_grow", s_frame, e_frame, (zone_x, zone_y, 0.09))

def build_full_animation():
    scene, cam_obj = setup_scene()
    cam_data = cam_obj.data

    mats = {{
        "blue": make_crayon_mat("CrayonBlue", (0.10, 0.36, 0.84, 1.0)),
        "red": make_crayon_mat("CrayonRed", (0.86, 0.16, 0.18, 1.0)),
        "gold": make_crayon_mat("CrayonGold", (0.90, 0.58, 0.04, 1.0)),
        "green": make_crayon_mat("CrayonGreen", (0.12, 0.66, 0.30, 1.0)),
        "charcoal": make_crayon_mat("CrayonCharcoal", (0.16, 0.16, 0.18, 1.0)),
    }}

    # Continuous Canvas Zone Coordinates (Camera pans smoothly across the giant sheet)
    zones = [
        (0.0, 0.0),
        (4.2, 0.35),
        (8.4, -0.25),
        (12.6, 0.30),
        (16.8, 0.0),
    ]

    scenes = PAYLOAD["scenes"]
    for sc in scenes:
        idx = sc["index"]
        zx, zy = zones[idx]
        s_frame = sc["start_frame"]
        e_frame = sc["end_frame"]
        d_frames = sc["draw_frames"]

        build_act_geometry(idx, zx, zy, s_frame, e_frame, d_frames, mats)

        # Draw connector trail to next zone on continuous canvas
        if idx < len(zones) - 1:
            nx, ny = zones[idx + 1]
            trail = [[(zx + 1.32, zy + 0.55), (nx - 1.32, ny + 0.55)]]
            tr_obj = add_crayon_curve(f"Trail_{{idx}}", trail, mats["gold"], (0.0, 0.0, -0.05), thickness=0.022)
            keyframe_draw_in(tr_obj, max(1, e_frame - 18), 18)

        # Keyframe smooth camera glide and subtle zoom-in per Act
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

    print(f"[CrayonStudio] Rendering {{PAYLOAD['total_frames']}} frames to {{PAYLOAD['output_mp4_path']}}...")
    bpy.ops.render.render(animation=True)
    print("[CrayonStudio] Render finished successfully.")

if __name__ == "__main__":
    build_full_animation()
'''

    def render_project(
        self,
        project_dir: str,
        words_json_path: str,
        output_mp4_path: str,
        category: str = "Architecture",
        duration_override: Optional[float] = None,
        progress_callback: Optional[Callable[[str], None]] = None,
    ) -> str:
        os.makedirs(project_dir, exist_ok=True)
        total_duration, scenes = self.parse_word_cues(
            words_json_path=words_json_path,
            default_duration=duration_override or 65.0,
        )

        script_path = os.path.join(project_dir, "_run_blender_scene.py")
        script_content = self._build_headless_blender_script(
            scenes=scenes,
            output_mp4_path=output_mp4_path,
            total_duration=total_duration,
            category=category,
        )
        with open(script_path, "w", encoding="utf-8") as f:
            f.write(script_content)

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
            progress_callback(f"[Blender] Rendering {int(total_duration * self.fps)} frames across 5 continuous zones...")

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
    blender_path: Optional[str] = None,
    progress_callback: Optional[Callable[[str], None]] = None,
) -> str:
    orchestrator = BlenderOrchestrator(blender_path=blender_path)
    return orchestrator.render_project(
        project_dir=project_dir,
        words_json_path=words_json_path,
        output_mp4_path=output_mp4_path,
        category=category,
        progress_callback=progress_callback,
    )
