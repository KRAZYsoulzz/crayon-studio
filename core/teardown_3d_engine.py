"""3D Hardware Teardown & Cutaway Engine for CrayonStudio (Engine B).

Headless Blender 5.0 execution engine for:
- Sleek engineering studio environment (#141820) with floor grid and 3-point lighting
- Procedural multi-part 3D assemblies (Piezo lighter/motor, Taipei 101 damper, vacuum chamber)
- Realistic PBR materials (translucent x-ray housing, brushed steel, copper/brass, emissive sparks)
- 4-Stage synchronized teardown choreography (Closed X-Ray -> Exploded -> Internal Action -> Cutaway Loop)
- Perspective 3D camera with orbital rotation, sweeps, and macro zoom tracked to CamTarget
"""

from __future__ import annotations

import json
import logging
import math
import os
import shutil
import subprocess
import sys
from typing import Any, Callable, Dict, List, Optional

from core.blender_orchestrator import BlenderOrchestrator

logger = logging.getLogger("crayon_studio.teardown_3d_engine")


class Teardown3DEngine:
    """Engine B: Generates and renders 3D physical mechanisms in exploded view."""

    def __init__(self, blender_path: Optional[str] = None, fps: int = 30):
        self.fps = fps
        self.blender_path = (
            blender_path
            if blender_path and (os.path.exists(blender_path) or shutil.which(blender_path))
            else BlenderOrchestrator.find_blender_executable()
        )

    def validate_blender_binary(self) -> bool:
        """Verify Blender binary availability."""
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

    def parse_word_stages(self, words_json_path: str, default_duration: float = 65.0) -> Dict[str, Any]:
        """Compute frame boundaries for the 4-stage teardown choreography."""
        total_duration = default_duration
        if os.path.exists(words_json_path):
            try:
                with open(words_json_path, "r", encoding="utf-8") as f:
                    words = json.load(f)
                    if isinstance(words, list) and words:
                        total_duration = max(float(words[-1].get("end", default_duration)) + 0.75, 10.0)
            except Exception:
                pass

        total_frames = int(math.ceil(total_duration * self.fps))

        # 4-Stage Choreography
        # Stage 1: 0% to 18% (Closed X-Ray Hero View / Incomplete Hook)
        # Stage 2: 18% to 45% (Automated Exploded View)
        # Stage 3: 45% to 78% (Internal Kinetic Action Pass)
        # Stage 4: 78% to 100% (Cutaway Reassembly & Loop)
        s1_end = int(round(total_frames * 0.18))
        s2_end = int(round(total_frames * 0.45))
        s3_end = int(round(total_frames * 0.78))
        s4_end = total_frames

        return {
            "total_duration": total_duration,
            "total_frames": total_frames,
            "stages": {
                "stage1_end": s1_end,
                "stage2_end": s2_end,
                "stage3_end": s3_end,
                "stage4_end": s4_end,
            },
        }

    def _build_headless_teardown_script(
        self,
        timing_info: Dict[str, Any],
        output_mp4_path: str,
        category: str = "Engineering",
    ) -> str:
        """Generate self-contained Blender 5.0 Python script for 3D teardown animation."""
        payload = {
            "fps": self.fps,
            "total_frames": timing_info["total_frames"],
            "stages": timing_info["stages"],
            "output_mp4_path": os.path.abspath(output_mp4_path),
            "category": category,
        }
        payload_json = json.dumps(payload, indent=2)

        script_code = f'''# Auto-generated Blender 5.0 3D Hardware Teardown Engine
import bpy
import os
import sys
import json
import math

PAYLOAD = json.loads(r"""{payload_json}""")

def reset_and_configure_studio():
    bpy.ops.wm.read_factory_settings(use_empty=True)
    scene = bpy.context.scene
    scene.render.resolution_x = 1080
    scene.render.resolution_y = 1920
    scene.render.resolution_percentage = 100
    scene.render.fps = PAYLOAD["fps"]
    scene.frame_start = 1
    scene.frame_end = PAYLOAD["total_frames"]

    # Render Engine: Blender 5.0 re-standardized on BLENDER_EEVEE
    for eng in ["BLENDER_EEVEE", "BLENDER_EEVEE_NEXT", "CYCLES"]:
        try:
            scene.render.engine = eng
            break
        except Exception:
            pass

    # Video output configuration (media_type = 'VIDEO' mandatory in Blender 5.0)
    if hasattr(scene.render.image_settings, "media_type"):
        try:
            scene.render.image_settings.media_type = 'VIDEO'
        except Exception:
            pass

    try:
        scene.render.image_settings.file_format = 'FFMPEG'
        scene.render.ffmpeg.format = 'MPEG4'
        scene.render.ffmpeg.codec = 'H264'
        scene.render.ffmpeg.constant_rate_factor = 'HIGH'
        scene.render.ffmpeg.ffmpeg_preset = 'GOOD'
    except Exception:
        pass

    scene.render.filepath = PAYLOAD["output_mp4_path"]

    # Sleek dark engineering studio world background (#141820)
    world = bpy.data.worlds.new("StudioDarkWorld")
    scene.world = world
    world.use_nodes = True
    bg = world.node_tree.nodes.get("Background")
    if bg:
        try:
            bg.inputs[0].default_value = (0.078, 0.094, 0.125, 1.0)
            bg.inputs[1].default_value = 0.8
        except Exception:
            pass

    # 3D Studio Floor Grid
    try:
        bpy.ops.mesh.primitive_grid_add(x_subdivisions=24, y_subdivisions=24, size=16.0, location=(0.0, 0.0, -2.2))
        floor = bpy.context.active_object
        floor.name = "StudioFloorGrid"
        f_mat = bpy.data.materials.new("FloorGridMat")
        f_mat.use_nodes = True
        bsdf = f_mat.node_tree.nodes.get("Principled BSDF")
        if bsdf:
            bsdf.inputs[0].default_value = (0.05, 0.06, 0.08, 1.0)
            if "Roughness" in bsdf.inputs:
                bsdf.inputs["Roughness"].default_value = 0.85
        floor.data.materials.append(f_mat)
    except Exception:
        pass

    # 3-Point Studio Lighting (Key, Cool Cyan Rim, Soft Top Fill)
    def add_light(name, l_type, energy, color, loc):
        l_data = bpy.data.lights.new(name=name, type=l_type)
        l_data.energy = energy
        l_data.color = color
        l_obj = bpy.data.objects.new(name=name, object_data=l_data)
        l_obj.location = loc
        scene.collection.objects.link(l_obj)
        return l_obj

    add_light("KeyLight", 'AREA', 650.0, (1.0, 0.94, 0.85), (3.5, -4.0, 5.0))
    add_light("RimLightCyan", 'AREA', 800.0, (0.15, 0.75, 1.0), (-4.5, 4.0, 4.0))
    add_light("TopSoftFill", 'POINT', 300.0, (0.85, 0.90, 1.0), (0.0, 0.0, 6.0))

    # 3D Tracking Empty & Perspective Camera (lens = 50mm)
    cam_target = bpy.data.objects.new("CamTarget", None)
    cam_target.empty_display_type = 'PLAIN_AXES'
    cam_target.location = (0.0, 0.0, 0.0)
    scene.collection.objects.link(cam_target)

    cam_data = bpy.data.cameras.new("Studio3DCamera")
    cam_data.lens = 50.0
    cam_data.sensor_width = 36.0
    cam_obj = bpy.data.objects.new("Studio3DCamera", cam_data)
    scene.collection.objects.link(cam_obj)
    scene.camera = cam_obj

    # Add Track To constraint so camera always frames CamTarget
    track = cam_obj.constraints.new(type='TRACK_TO')
    track.target = cam_target
    track.track_axis = 'TRACK_NEGATIVE_Z'
    track.up_axis = 'UP_Y'

    return scene, cam_obj, cam_target

def get_or_create_pbr_material(name, base_color, metallic=0.0, roughness=0.5, alpha=1.0, emissive=None):
    if name in bpy.data.materials:
        return bpy.data.materials[name]
    mat = bpy.data.materials.new(name)
    mat.use_nodes = True
    if hasattr(mat, "blend_method") and alpha < 1.0:
        try:
            mat.blend_method = 'BLEND'
            mat.shadow_method = 'NONE'
        except Exception:
            pass

    bsdf = mat.node_tree.nodes.get("Principled BSDF")
    if bsdf:
        try:
            bsdf.inputs[0].default_value = base_color
            if "Metallic" in bsdf.inputs:
                bsdf.inputs["Metallic"].default_value = metallic
            if "Roughness" in bsdf.inputs:
                bsdf.inputs["Roughness"].default_value = roughness
            if alpha < 1.0:
                if "Alpha" in bsdf.inputs:
                    bsdf.inputs["Alpha"].default_value = alpha
                if "Transmission Weight" in bsdf.inputs:
                    bsdf.inputs["Transmission Weight"].default_value = 0.85
                elif "Transmission" in bsdf.inputs:
                    bsdf.inputs["Transmission"].default_value = 0.85
            if emissive:
                col, strength = emissive
                if "Emission Color" in bsdf.inputs:
                    bsdf.inputs["Emission Color"].default_value = col
                elif "Emission" in bsdf.inputs:
                    bsdf.inputs["Emission"].default_value = col
                if "Emission Strength" in bsdf.inputs:
                    bsdf.inputs["Emission Strength"].default_value = strength
        except Exception:
            pass
    return mat

def build_assembly_materials():
    return {{
        "casing_xray": get_or_create_pbr_material("CasingXRay", (0.35, 0.45, 0.55, 1.0), metallic=0.1, roughness=0.15, alpha=0.28),
        "brushed_steel": get_or_create_pbr_material("BrushedSteel", (0.82, 0.84, 0.86, 1.0), metallic=0.92, roughness=0.25),
        "titanium_dark": get_or_create_pbr_material("TitaniumDark", (0.35, 0.38, 0.42, 1.0), metallic=0.88, roughness=0.30),
        "copper_brass": get_or_create_pbr_material("CopperBrass", (0.88, 0.52, 0.22, 1.0), metallic=0.95, roughness=0.20),
        "quartz_piezo": get_or_create_pbr_material("QuartzPiezo", (0.75, 0.92, 0.95, 1.0), metallic=0.05, roughness=0.10, alpha=0.55),
        "spark_emissive": get_or_create_pbr_material("SparkEmissive", (0.2, 0.85, 1.0, 1.0), emissive=((0.2, 0.85, 1.0, 1.0), 12.0)),
        "gold_damper": get_or_create_pbr_material("GoldDamper", (0.95, 0.78, 0.22, 1.0), metallic=0.96, roughness=0.18),
    }}

def create_piezo_mechanism(materials):
    """Procedural 3D Piezoelectric Ignition / Motor mechanism."""
    parts = {{}}

    # 1. Outer Translucent Housing
    bpy.ops.mesh.primitive_cylinder_add(radius=0.9, depth=3.2, location=(0.0, 0.0, 0.0))
    casing = bpy.context.active_object
    casing.name = "Part_Casing"
    casing.data.materials.append(materials["casing_xray"])
    parts["casing"] = casing

    # 2. Quartz Piezo Crystal Anvil (Base)
    bpy.ops.mesh.primitive_cube_add(size=0.7, location=(0.0, 0.0, -0.9))
    crystal = bpy.context.active_object
    crystal.name = "Part_Crystal"
    crystal.data.materials.append(materials["quartz_piezo"])
    parts["crystal"] = crystal

    # 3. Steel Striker Hammer (Middle)
    bpy.ops.mesh.primitive_cylinder_add(radius=0.45, depth=0.7, location=(0.0, 0.0, -0.1))
    striker = bpy.context.active_object
    striker.name = "Part_Striker"
    striker.data.materials.append(materials["brushed_steel"])
    parts["striker"] = striker

    # 4. Helical Brass Compression Spring (Upper Core)
    bpy.ops.mesh.primitive_cylinder_add(radius=0.40, depth=0.9, location=(0.0, 0.0, 0.7))
    spring = bpy.context.active_object
    spring.name = "Part_Spring"
    spring.data.materials.append(materials["copper_brass"])
    parts["spring"] = spring

    # 5. Copper Ignition Wire & Nozzle
    bpy.ops.mesh.primitive_cylinder_add(radius=0.08, depth=2.4, location=(0.55, 0.0, 0.2))
    wire = bpy.context.active_object
    wire.name = "Part_Wire"
    wire.data.materials.append(materials["copper_brass"])
    parts["wire"] = wire

    # 6. High-Voltage Spark Discharge Arc (Active highlight)
    bpy.ops.mesh.primitive_ico_sphere_add(radius=0.18, location=(0.35, 0.0, 1.5))
    spark = bpy.context.active_object
    spark.name = "Part_Spark"
    spark.data.materials.append(materials["spark_emissive"])
    parts["spark"] = spark

    return parts

def create_structural_damper(materials):
    """Procedural Taipei 101 Tuned Mass Damper & Hydraulic Shock Rig."""
    parts = {{}}

    # 1. Structural Cage Framework
    bpy.ops.mesh.primitive_cylinder_add(radius=1.3, depth=3.6, vertices=8, location=(0.0, 0.0, 0.0))
    cage = bpy.context.active_object
    cage.name = "Part_Cage"
    cage.data.materials.append(materials["titanium_dark"])
    parts["cage"] = cage

    # 2. Golden Tuned Mass Damper Sphere
    bpy.ops.mesh.primitive_uv_sphere_add(radius=0.75, location=(0.0, 0.0, 0.0))
    damper = bpy.context.active_object
    damper.name = "Part_DamperSphere"
    damper.data.materials.append(materials["gold_damper"])
    parts["damper"] = damper

    # 3. Hydraulic Shock Absorbers (Lateral Pistons)
    bpy.ops.mesh.primitive_cylinder_add(radius=0.12, depth=1.6, location=(0.8, 0.0, -0.6))
    piston1 = bpy.context.active_object
    piston1.rotation_euler = (0.0, math.radians(65.0), 0.0)
    piston1.name = "Part_PistonLeft"
    piston1.data.materials.append(materials["brushed_steel"])
    parts["piston1"] = piston1

    bpy.ops.mesh.primitive_cylinder_add(radius=0.12, depth=1.6, location=(-0.8, 0.0, -0.6))
    piston2 = bpy.context.active_object
    piston2.rotation_euler = (0.0, math.radians(-65.0), 0.0)
    piston2.name = "Part_PistonRight"
    piston2.data.materials.append(materials["brushed_steel"])
    parts["piston2"] = piston2

    # 4. Energy Dissipation Ring
    bpy.ops.mesh.primitive_torus_add(major_radius=0.88, minor_radius=0.06, location=(0.0, 0.0, 0.0))
    ring = bpy.context.active_object
    ring.name = "Part_Ring"
    ring.data.materials.append(materials["spark_emissive"])
    parts["ring"] = ring

    return parts

def create_stem_vacuum_chamber(materials):
    """Procedural Vacuum Chamber & Electromagnet Release Rig."""
    parts = {{}}

    # 1. Vacuum Glass Cylinder
    bpy.ops.mesh.primitive_cylinder_add(radius=0.95, depth=3.5, location=(0.0, 0.0, 0.0))
    glass = bpy.context.active_object
    glass.name = "Part_GlassCylinder"
    glass.data.materials.append(materials["casing_xray"])
    parts["glass"] = glass

    # 2. Top Electromagnet Solenoid Rig
    bpy.ops.mesh.primitive_cylinder_add(radius=0.55, depth=0.6, location=(0.0, 0.0, 1.45))
    solenoid = bpy.context.active_object
    solenoid.name = "Part_Solenoid"
    solenoid.data.materials.append(materials["copper_brass"])
    parts["solenoid"] = solenoid

    # 3. Steel Gravity Sphere
    bpy.ops.mesh.primitive_uv_sphere_add(radius=0.32, location=(0.0, 0.0, 0.8))
    sphere = bpy.context.active_object
    sphere.name = "Part_SteelSphere"
    sphere.data.materials.append(materials["brushed_steel"])
    parts["sphere"] = sphere

    # 4. Vacuum Manifold Pressure Base
    bpy.ops.mesh.primitive_cylinder_add(radius=1.1, depth=0.4, location=(0.0, 0.0, -1.55))
    base = bpy.context.active_object
    base.name = "Part_VacuumBase"
    base.data.materials.append(materials["titanium_dark"])
    parts["base"] = base

    return parts

def animate_4_stage_teardown(parts, stages, cam_obj, cam_target, category):
    """Keyframes the 4 teardown stages synchronized to script cues."""
    s1_end = stages["stage1_end"]
    s2_end = stages["stage2_end"]
    s3_end = stages["stage3_end"]
    s4_end = stages["stage4_end"]

    def safe_kf(obj, path, frame):
        try:
            obj.keyframe_insert(data_path=path, frame=frame)
        except Exception:
            pass

    # Store base locations
    base_locs = {{k: tuple(o.location) for k, o in parts.items()}}

    # -------------------------------------------------------------
    # CAMERA CHOREOGRAPHY
    # -------------------------------------------------------------
    # Stage 1: Mid-orbit hero view (Radius 5.5, Z=1.2)
    cam_obj.location = (4.8, -2.6, 1.4)
    cam_target.location = (0.0, 0.0, 0.0)
    safe_kf(cam_obj, "location", 1)
    safe_kf(cam_target, "location", 1)

    # Orbit clockwise to (2.5, -4.8, 1.8) at end of Stage 1
    cam_obj.location = (2.5, -4.8, 1.8)
    safe_kf(cam_obj, "location", s1_end)

    # Stage 2: Pull back slightly for Exploded View (Radius 6.8, Z=2.2)
    cam_obj.location = (-1.8, -6.2, 2.4)
    safe_kf(cam_obj, "location", s2_end)

    # Stage 3: Macro close-up zoom into core mechanism (Radius 3.2, Z=0.4)
    cam_obj.location = (1.8, -2.4, 0.2)
    safe_kf(cam_obj, "location", s3_end)

    # Stage 4: Return to exact Frame 1 angle for seamless loop
    cam_obj.location = (4.8, -2.6, 1.4)
    safe_kf(cam_obj, "location", s4_end)

    # -------------------------------------------------------------
    # STAGE 2: EXPLODED VIEW VECTOR DISPLACEMENT
    # -------------------------------------------------------------
    for k, obj in parts.items():
        bx, by, bz = base_locs[k]
        safe_kf(obj, "location", 1)
        safe_kf(obj, "location", s1_end)

        # Compute radial explosion vectors
        if "casing" in k or "glass" in k or "cage" in k:
            obj.location = (bx + 1.2, by, bz)
        elif "spring" in k or "solenoid" in k:
            obj.location = (bx, by, bz + 1.1)
        elif "striker" in k or "sphere" in k or "damper" in k:
            obj.location = (bx, by, bz - 0.4)
        elif "crystal" in k or "base" in k:
            obj.location = (bx, by, bz - 0.9)
        elif "wire" in k or "piston" in k:
            obj.location = (bx + 0.6, by + 0.5, bz)

        safe_kf(obj, "location", s2_end)

    # -------------------------------------------------------------
    # STAGE 3: INTERNAL KINETIC ACTION PASS
    # -------------------------------------------------------------
    striker_obj = parts.get("striker") or parts.get("sphere") or parts.get("damper")
    spark_obj = parts.get("spark") or parts.get("ring")
    spring_obj = parts.get("spring") or parts.get("piston1")

    if striker_obj:
        # Rapid kinetic strike downward onto quartz crystal / impact floor
        s3_mid = int((s2_end + s3_end) / 2)
        safe_kf(striker_obj, "location", s2_end)
        striker_obj.location = (striker_obj.location[0], striker_obj.location[1], striker_obj.location[2] - 0.35)
        safe_kf(striker_obj, "location", s3_mid)
        # Recoil bounce
        striker_obj.location = (striker_obj.location[0], striker_obj.location[1], striker_obj.location[2] + 0.12)
        safe_kf(striker_obj, "location", s3_mid + 8)

    if spring_obj:
        # Compression wave
        safe_kf(spring_obj, "scale", s2_end)
        spring_obj.scale = (1.0, 1.0, 0.65)
        safe_kf(spring_obj, "scale", s2_end + 12)
        spring_obj.scale = (1.0, 1.0, 1.0)
        safe_kf(spring_obj, "scale", s3_end)

    if spark_obj:
        # Pulsing emissive spark at impact point
        spark_obj.scale = (0.2, 0.2, 0.2)
        safe_kf(spark_obj, "scale", s2_end)
        spark_obj.scale = (1.6, 1.6, 1.6)
        safe_kf(spark_obj, "scale", int((s2_end + s3_end) / 2))
        spark_obj.scale = (0.1, 0.1, 0.1)
        safe_kf(spark_obj, "scale", s3_end)

    # -------------------------------------------------------------
    # STAGE 4: CUTAWAY REASSEMBLY & SEAMLESS LOOP
    # -------------------------------------------------------------
    for k, obj in parts.items():
        bx, by, bz = base_locs[k]
        obj.location = (bx, by, bz)
        safe_kf(obj, "location", s4_end)
        obj.scale = (1.0, 1.0, 1.0)
        safe_kf(obj, "scale", s4_end)

def build_full_teardown_scene():
    scene, cam_obj, cam_target = reset_and_configure_studio()
    materials = build_assembly_materials()
    category = PAYLOAD.get("category", "Engineering")

    cat_upper = category.upper()
    if "ARCH" in cat_upper or "DAMPER" in cat_upper:
        parts = create_structural_damper(materials)
    elif "STEM" in cat_upper or "PHYS" in cat_upper:
        parts = create_stem_vacuum_chamber(materials)
    else:  # Engineering / How It's Made / Default Piezo
        parts = create_piezo_mechanism(materials)

    animate_4_stage_teardown(parts, PAYLOAD["stages"], cam_obj, cam_target, category)

    print(f"[CrayonStudio 3D] Rendering {{PAYLOAD['total_frames']}} frames to {{PAYLOAD['output_mp4_path']}}...")
    bpy.ops.render.render(animation=True)
    print("[CrayonStudio 3D] Headless 3D Teardown render complete.")

if __name__ == "__main__":
    build_full_teardown_scene()
'''
        return script_code

    def render_project(
        self,
        project_dir: str,
        words_json_path: str,
        output_mp4_path: str,
        category: str = "Engineering",
        duration_override: Optional[float] = None,
        progress_callback: Optional[Callable[[str], None]] = None,
    ) -> str:
        """Execute headless 3D teardown render pass."""
        os.makedirs(project_dir, exist_ok=True)
        timing_info = self.parse_word_stages(
            words_json_path=words_json_path,
            default_duration=duration_override or 65.0,
        )

        script_path = os.path.join(project_dir, "_run_3d_teardown_scene.py")
        script_content = self._build_headless_teardown_script(
            timing_info=timing_info,
            output_mp4_path=output_mp4_path,
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
            progress_callback(f"[3D Teardown] Launching Blender 5.0 3D pass: {' '.join(cmd)}")

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

                    if progress_callback:
                        lower = clean_line.lower()
                        if any(kw in lower for kw in ("traceback", "error", "exception", "typeerror", "fra:", "[crayonstudio 3d]", "append frame")):
                            progress_callback(f"[3D Teardown] {clean_line}")

        return_code = process.wait()
        if return_code != 0 or not os.path.exists(output_mp4_path):
            tail_msg = "\n".join(output_tail) if output_tail else "No output captured."
            raise RuntimeError(
                f"Headless 3D Teardown exited with code {return_code}.\n"
                f"--- Blender Output (Last 20 Lines) ---\n"
                f"{tail_msg}\n"
                f"Command: {' '.join(cmd)}"
            )

        if progress_callback:
            progress_callback(f"[3D Teardown] Render pass saved: {output_mp4_path}")

        return output_mp4_path
