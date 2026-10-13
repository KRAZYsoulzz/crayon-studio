import os
import sys
import json
import glob
import math
import shutil
import subprocess
from pathlib import Path
from typing import Callable, Dict, List, Optional, Tuple, Any


class BlenderOrchestrator:
    """
    Production orchestrator that converts timestamped scripts into articulated 2D
    crayon Grease Pencil animations rendered headlessly in Blender (4.2 LTS through 5.x).
    """

    def __init__(self, blender_path: Optional[str] = None, fps: int = 30):
        self.fps = fps
        self.blender_path = (
            blender_path
            if blender_path and (os.path.exists(blender_path) or shutil.which(blender_path))
            else self.find_blender_executable()
        )

    def validate_blender_binary(self) -> bool:
        """Check whether the configured Blender binary exists and can be executed."""
        try:
            result = subprocess.run(
                [self.blender_path, "--version"],
                capture_output=True,
                text=True,
                check=False,
                timeout=5,
            )
            return result.returncode == 0
        except Exception:
            return False

    @staticmethod
    def find_blender_executable(config_path: str = "config.json") -> str:
        """Locates the Blender binary via config.json, system PATH, or standard OS install paths."""
        possible_configs = [
            config_path,
            os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "config.json"),
        ]
        for cp in possible_configs:
            if os.path.exists(cp):
                try:
                    with open(cp, "r", encoding="utf-8") as f:
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
            search_patterns = [
                r"C:\Program Files\Blender Foundation\Blender *\blender.exe",
                r"C:\Program Files (x86)\Blender Foundation\Blender *\blender.exe",
                os.path.expandvars(r"%LOCALAPPDATA%\Programs\Blender Foundation\Blender *\blender.exe"),
            ]
            candidates = []
            for pattern in search_patterns:
                candidates.extend(glob.glob(pattern))
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
        default_duration: float = 65.0
    ) -> Tuple[float, List[Dict[str, Any]]]:
        """
        Reads faster-whisper words.json and maps semantic cue points into exact Blender frame numbers.
        Guarantees Frame 1 has an active 'Visual Incomplete' hook sketch.
        """
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
            total_duration = max(last_end + 0.75, 10.0)

        # Divide timeline into 5 structured acts based on actual spoken word timing or fallback ratios
        act_ratios = [0.0, 0.14, 0.34, 0.58, 0.82]
        keyword_triggers = {
            1: ["inside", "filament", "actin", "cell", "blueprint", "vent", "kernel", "layer"],
            2: ["rest", "block", "caution", "tropomyosin", "dummy", "sensor", "steam", "pressure"],
            3: ["calcium", "signal", "flood", "rip", "raft", "bypass", "explode", "armor"],
            4: ["latch", "ratchet", "crawl", "flex", "grip", "shop", "test", "microscope"],
        }

        act_starts_sec = [0.0] * 5
        used_times = {0.0}

        for act_idx in range(1, 5):
            matched_time = None
            triggers = keyword_triggers.get(act_idx, [])
            min_time = total_duration * (act_ratios[act_idx] - 0.08)
            max_time = total_duration * (act_ratios[act_idx] + 0.12)

            for w in words:
                clean_w = str(w.get("word", "")).strip().lower().strip(".,!?;:\"'")
                t_start = float(w.get("start", 0.0))
                if min_time <= t_start <= max_time and any(k in clean_w for k in triggers):
                    matched_time = t_start
                    break

            if matched_time is None or matched_time in used_times:
                matched_time = round(total_duration * act_ratios[act_idx], 2)

            act_starts_sec[act_idx] = matched_time
            used_times.add(matched_time)

        act_starts_sec.sort()

        scenes = []
        act_names = [
            "Act1_Hook_Incomplete",
            "Act2_Core_Mechanism",
            "Act3_Obstacle_Friction",
            "Act4_Trigger_Action",
            "Act5_Resolution_Bridge",
        ]

        for i in range(5):
            start_s = act_starts_sec[i]
            end_s = act_starts_sec[i + 1] if i < 4 else total_duration
            start_frame = max(1, int(round(start_s * self.fps)))
            end_frame = max(start_frame + 15, int(round(end_s * self.fps)))
            scenes.append({
                "index": i,
                "name": act_names[i],
                "start_sec": start_s,
                "end_sec": end_s,
                "start_frame": start_frame if i > 0 else 1,
                "end_frame": end_frame,
                "draw_frames": min(35, max(12, int((end_frame - start_frame) * 0.22))),
                "erase_frames": 12,
            })

        return total_duration, scenes

    def generate_svg_puppets(self, svg_dir: str, category: str = "STEM") -> Dict[str, List[Dict[str, Any]]]:
        """
        Generates multi-part articulated SVG vector components on disk for each Act,
        tailored specifically to the given video category (STEM, Architecture, Escape/Heist, Psychology).
        Each part specifies its SVG filepath, color palette key, joint pivot offset,
        and kinematic motion profile so Blender rigs and animates real 2D movement.
        """
        os.makedirs(svg_dir, exist_ok=True)
        manifest: Dict[str, List[Dict[str, Any]]] = {}

        # Helper to write clean SVG path files
        def write_svg(filename: str, paths_xml: str) -> str:
            full_path = os.path.join(svg_dir, filename)
            svg_content = (
                '<?xml version="1.0" encoding="UTF-8"?>\n'
                '<svg xmlns="http://www.w3.org/2000/svg" viewBox="-500 -500 1000 1000" width="1000" height="1000">\n'
                f"{paths_xml}\n"
                "</svg>\n"
            )
            with open(full_path, "w", encoding="utf-8") as f:
                f.write(svg_content)
            return full_path

        cat_upper = category.upper()

        if "ARCH" in cat_upper:
            # ARCHITECTURE: Roman Concrete Self-Healing Hydrothermal Lattice
            seawall_base = write_svg(
                "arch_act1_seawall.svg",
                '<rect x="-420" y="-120" width="840" height="240" rx="8" fill="none" stroke="black" stroke-width="16"/>'
                '<path d="M -420,-40 L 420,-40 M -420,40 L 420,40 M -200,-120 L -200,-40 M 0,-40 L 0,40 M 200,-40 L 200,40 M -100,40 L -100,120 M 100,40 L 100,120" fill="none" stroke="black" stroke-width="12"/>',
            )
            ocean_wave = write_svg(
                "arch_act1_wave.svg",
                '<path d="M -450,-180 C -350,-80 -250,-240 -150,-140 C -50,-40 50,-200 150,-100 C 250,0 350,-160 450,-60 L 450,-300 L -450,-300 Z" fill="none" stroke="black" stroke-width="16"/>'
                '<path d="M -220,-110 C -180,-70 -140,-130 -100,-90 M 80,-70 C 120,-30 160,-90 200,-50" fill="none" stroke="black" stroke-width="12"/>',
            )
            stress_callout = write_svg(
                "arch_act1_stress.svg",
                '<path d="M -300,-220 L -300,-130 M -325,-160 L -300,-125 L -275,-160" fill="none" stroke="black" stroke-width="14"/>'
                '<path d="M 0,-240 L 0,-130 M -25,-165 L 0,-125 L 25,-165" fill="none" stroke="black" stroke-width="14"/>'
                '<path d="M 300,-220 L 300,-130 M 275,-160 L 300,-125 L 325,-160" fill="none" stroke="black" stroke-width="14"/>',
            )
            manifest["Act1_Hook_Incomplete"] = [
                {"file": seawall_base, "color": "blue", "pivot": (0.0, 0.0, 0.0), "motion": "breathe_scale"},
                {"file": ocean_wave, "color": "blue", "pivot": (-0.2, -0.15, 0.0), "motion": "slide_in_left"},
                {"file": stress_callout, "color": "red", "pivot": (0.0, 0.28, 0.0), "motion": "bounce_arrow"},
            ]

            pozzolana_matrix = write_svg(
                "arch_act2_pozzolana.svg",
                '<circle cx="-250" cy="80" r="45" fill="none" stroke="black" stroke-width="14"/>'
                '<circle cx="-80" cy="-60" r="60" fill="none" stroke="black" stroke-width="14"/>'
                '<circle cx="160" cy="70" r="50" fill="none" stroke="black" stroke-width="14"/>'
                '<circle cx="300" cy="-70" r="40" fill="none" stroke="black" stroke-width="14"/>'
                '<path d="M -380,0 L 380,0 M 0,-250 L 0,250" fill="none" stroke="black" stroke-width="10"/>',
            )
            water_channels = write_svg(
                "arch_act2_channels.svg",
                '<path d="M -320,-280 C -300,-180 -220,-120 -200,-20 C -180,80 -120,160 -100,280" fill="none" stroke="black" stroke-width="14"/>'
                '<path d="M 120,-280 C 140,-160 200,-100 220,0 C 240,100 280,180 300,280" fill="none" stroke="black" stroke-width="14"/>',
            )
            manifest["Act2_Core_Mechanism"] = [
                {"file": pozzolana_matrix, "color": "yellow", "pivot": (0.0, 0.0, 0.0), "motion": "breathe_scale"},
                {"file": water_channels, "color": "blue", "pivot": (0.0, 0.0, 0.0), "motion": "drop_cascade"},
            ]

            microcracks = write_svg(
                "arch_act3_microcracks.svg",
                '<path d="M -280,0 L -180,60 L -100,-20 L 20,40 L 140,-50 L 260,30" fill="none" stroke="black" stroke-width="16"/>'
                '<path d="M -180,60 L -140,140 M 20,40 L 60,120 M 140,-50 L 190,-130" fill="none" stroke="black" stroke-width="12"/>',
            )
            erosion_barrier = write_svg(
                "arch_act3_erosion.svg",
                '<path d="M -400,-180 C -250,-100 -100,-240 50,-160 C 200,-80 350,-220 450,-140" fill="none" stroke="black" stroke-width="16"/>'
                '<path d="M -400,-120 C -250,-40 -100,-180 50,-100 C 200,-20 350,-160 450,-80" fill="none" stroke="black" stroke-width="12"/>',
            )
            manifest["Act3_Obstacle_Friction"] = [
                {"file": microcracks, "color": "red", "pivot": (0.0, 0.0, 0.0), "motion": "wave_shift"},
                {"file": erosion_barrier, "color": "yellow", "pivot": (0.0, -0.15, 0.0), "motion": "recoil_bounce"},
            ]

            mineral_ions = write_svg(
                "arch_act4_ions.svg",
                '<circle cx="-260" cy="-140" r="28" fill="none" stroke="black" stroke-width="12"/>'
                '<circle cx="-90" cy="-220" r="32" fill="none" stroke="black" stroke-width="12"/>'
                '<circle cx="120" cy="-180" r="30" fill="none" stroke="black" stroke-width="12"/>'
                '<circle cx="280" cy="-150" r="26" fill="none" stroke="black" stroke-width="12"/>'
                '<path d="M -260,-100 L -260,0 M -90,-180 L -90,-20 M 120,-140 L 120,20 M 280,-115 L 280,-10" fill="none" stroke="black" stroke-width="12"/>',
            )
            tobermorite_growth = write_svg(
                "arch_act4_crystals.svg",
                '<path d="M -300,-10 L -220,50 L -140,-20 L -60,60 L 20,-10 L 100,70 L 180,-20 L 260,50" fill="none" stroke="black" stroke-width="18"/>'
                '<path d="M -200,-30 L -160,80 M -40,-40 L 0,90 M 120,-30 L 160,80" fill="none" stroke="black" stroke-width="14"/>',
            )
            manifest["Act4_Trigger_Action"] = [
                {"file": mineral_ions, "color": "green", "pivot": (0.0, -0.2, 0.0), "motion": "drop_cascade"},
                {"file": tobermorite_growth, "color": "green", "pivot": (0.0, 0.1, 0.0), "motion": "peel_away"},
            ]

            interlocking_left = write_svg(
                "arch_act5_lattice_left.svg",
                '<path d="M -420,180 L -60,180 M -420,-180 L -60,-180 M -420,-220 L -420,220" fill="none" stroke="black" stroke-width="18"/>'
                '<path d="M -320,180 L -240,-180 M -180,180 L -100,-180" fill="none" stroke="black" stroke-width="14"/>',
            )
            interlocking_right = write_svg(
                "arch_act5_lattice_right.svg",
                '<path d="M 60,180 L 420,180 M 60,-180 L 420,-180 M 420,-220 L 420,220" fill="none" stroke="black" stroke-width="18"/>'
                '<path d="M 160,180 L 240,-180 M 300,180 L 380,-180" fill="none" stroke="black" stroke-width="14"/>',
            )
            healed_monolith = write_svg(
                "arch_act5_monolith.svg",
                '<rect x="-300" y="-60" width="600" height="120" rx="16" fill="none" stroke="black" stroke-width="18"/>'
                '<path d="M -200,0 L 200,0 M -100,-60 L -100,60 M 100,-60 L 100,60" fill="none" stroke="black" stroke-width="14"/>',
            )
            manifest["Act5_Resolution_Bridge"] = [
                {"file": interlocking_left, "color": "blue", "pivot": (-0.25, 0.0, 0.0), "motion": "ratchet_in_left"},
                {"file": interlocking_right, "color": "blue", "pivot": (0.25, 0.0, 0.0), "motion": "ratchet_in_right"},
                {"file": healed_monolith, "color": "red", "pivot": (0.0, 0.0, 0.0), "motion": "ratchet_power_stroke"},
            ]

        elif "HEIST" in cat_upper or "ESCAPE" in cat_upper:
            # ESCAPE / HEIST: Subterranean Vault & Thermal Sensor Bypass
            vault_door = write_svg(
                "heist_act1_door.svg",
                '<rect x="-350" y="-350" width="700" height="700" rx="40" fill="none" stroke="black" stroke-width="18"/>'
                '<circle cx="0" cy="0" r="220" fill="none" stroke="black" stroke-width="16"/>',
            )
            dial_wheel = write_svg(
                "heist_act1_dial.svg",
                '<circle cx="0" cy="0" r="100" fill="none" stroke="black" stroke-width="16"/>'
                '<path d="M 0,-100 L 0,-170 M 100,0 L 170,0 M 0,100 L 0,170 M -100,0 L -170,0" fill="none" stroke="black" stroke-width="18"/>',
            )
            heist_callout = write_svg(
                "heist_act1_callout.svg",
                '<path d="M -160,-240 L -160,-330 M -190,-275 L -160,-235 L -130,-275" fill="none" stroke="black" stroke-width="14"/>'
                '<circle cx="-160" cy="-210" r="24" fill="none" stroke="black" stroke-width="12"/>',
            )
            manifest["Act1_Hook_Incomplete"] = [
                {"file": vault_door, "color": "blue", "pivot": (0.0, 0.0, 0.0), "motion": "pulse_bicep"},
                {"file": dial_wheel, "color": "blue", "pivot": (0.0, 0.0, 0.0), "motion": "hinge_flex"},
                {"file": heist_callout, "color": "red", "pivot": (-0.16, 0.25, 0.0), "motion": "bounce_arrow"},
            ]

            laser_grid = write_svg(
                "heist_act2_lasers.svg",
                '<path d="M -400,240 L 400,240 M -400,80 L 400,80 M -400,-80 L 400,-80 M -400,-240 L 400,-240" fill="none" stroke="black" stroke-width="14"/>'
                '<circle cx="-300" cy="240" r="18" fill="none" stroke="black" stroke-width="12"/>'
                '<circle cx="300" cy="-240" r="18" fill="none" stroke="black" stroke-width="12"/>',
            )
            seismic_floor = write_svg(
                "heist_act2_seismic.svg",
                '<path d="M -420,320 L 420,320 M -350,320 L -300,380 M -150,320 L -100,380 M 50,320 L 100,380 M 250,320 L 300,380" fill="none" stroke="black" stroke-width="16"/>',
            )
            central_safe = write_svg(
                "heist_act2_safe.svg",
                '<rect x="-200" y="-140" width="400" height="280" rx="18" fill="none" stroke="black" stroke-width="18"/>'
                '<circle cx="0" cy="0" r="50" fill="none" stroke="black" stroke-width="14"/>'
                '<path d="M 0,0 L 35,-35" fill="none" stroke="black" stroke-width="16"/>',
            )
            manifest["Act2_Core_Mechanism"] = [
                {"file": laser_grid, "color": "red", "pivot": (0.0, 0.15, 0.0), "motion": "slide_in_left"},
                {"file": seismic_floor, "color": "blue", "pivot": (0.0, -0.25, 0.0), "motion": "slide_in_right"},
                {"file": central_safe, "color": "yellow", "pivot": (0.0, 0.0, 0.0), "motion": "breathe_scale"},
            ]

            thermal_cone = write_svg(
                "heist_act3_thermal.svg",
                '<path d="M 0,-340 L -380,240 L 380,240 Z" fill="none" stroke="black" stroke-width="16"/>'
                '<path d="M -220,40 L 220,40 M -140,-100 L 140,-100" fill="none" stroke="black" stroke-width="12"/>',
            )
            alarm_boundary = write_svg(
                "heist_act3_alarm.svg",
                '<path d="M -400,-60 L 400,-60 M -400,-20 L 400,-20" fill="none" stroke="black" stroke-width="14"/>'
                '<path d="M -300,-60 L -250,-20 M -100,-60 L -50,-20 M 100,-60 L 150,-20 M 300,-60 L 350,-20" fill="none" stroke="black" stroke-width="12"/>',
            )
            manifest["Act3_Obstacle_Friction"] = [
                {"file": thermal_cone, "color": "yellow", "pivot": (0.0, 0.1, 0.0), "motion": "wave_shift"},
                {"file": alarm_boundary, "color": "red", "pivot": (0.0, 0.0, 0.0), "motion": "recoil_bounce"},
            ]

            spray_cloud = write_svg(
                "heist_act4_spray.svg",
                '<circle cx="-180" cy="-240" r="42" fill="none" stroke="black" stroke-width="14"/>'
                '<circle cx="-40" cy="-280" r="52" fill="none" stroke="black" stroke-width="14"/>'
                '<circle cx="120" cy="-250" r="48" fill="none" stroke="black" stroke-width="14"/>'
                '<circle cx="260" cy="-210" r="38" fill="none" stroke="black" stroke-width="14"/>'
                '<path d="M -40,-220 L -40,-80 M 120,-190 L 120,-70" fill="none" stroke="black" stroke-width="12"/>',
            )
            disabled_lasers = write_svg(
                "heist_act4_bypass.svg",
                '<path d="M -400,200 C -200,200 0,320 200,380" fill="none" stroke="black" stroke-width="14"/>'
                '<path d="M -400,-200 C -200,-200 0,-320 200,-380" fill="none" stroke="black" stroke-width="14"/>',
            )
            manifest["Act4_Trigger_Action"] = [
                {"file": spray_cloud, "color": "green", "pivot": (0.0, 0.25, 0.0), "motion": "drop_cascade"},
                {"file": disabled_lasers, "color": "yellow", "pivot": (-0.3, 0.0, 0.0), "motion": "peel_away"},
            ]

            jumper_left = write_svg(
                "heist_act5_jumper_left.svg",
                '<path d="M -420,160 L -80,160 M -420,-160 L -80,-160 M -420,-200 L -420,200" fill="none" stroke="black" stroke-width="18"/>'
                '<circle cx="-250" cy="160" r="30" fill="none" stroke="black" stroke-width="14"/>',
            )
            jumper_right = write_svg(
                "heist_act5_jumper_right.svg",
                '<path d="M 80,160 L 420,160 M 80,-160 L 420,-160 M 420,-200 L 420,200" fill="none" stroke="black" stroke-width="18"/>'
                '<circle cx="250" cy="160" r="30" fill="none" stroke="black" stroke-width="14"/>',
            )
            open_bolts = write_svg(
                "heist_act5_bolts.svg",
                '<rect x="-240" y="-50" width="480" height="100" rx="20" fill="none" stroke="black" stroke-width="18"/>'
                '<path d="M -140,50 L -140,160 M 140,50 L 140,160 M -140,-50 L -140,-160 M 140,-50 L 140,-160" fill="none" stroke="black" stroke-width="16"/>',
            )
            manifest["Act5_Resolution_Bridge"] = [
                {"file": jumper_left, "color": "blue", "pivot": (-0.25, 0.0, 0.0), "motion": "ratchet_in_left"},
                {"file": jumper_right, "color": "blue", "pivot": (0.25, 0.0, 0.0), "motion": "ratchet_in_right"},
                {"file": open_bolts, "color": "red", "pivot": (0.0, 0.0, 0.0), "motion": "ratchet_power_stroke"},
            ]

        elif "PSYCH" in cat_upper:
            # PSYCHOLOGY: Illusion of Control & Cognitive Bias Lattice
            head_profile = write_svg(
                "psych_act1_head.svg",
                '<path d="M -220,-280 C -80,-380 180,-340 220,-180 C 240,-100 240,0 200,80 C 180,120 180,180 140,240 C 100,300 20,340 -120,340 C -180,340 -260,280 -260,200 Z" fill="none" stroke="black" stroke-width="18"/>',
            )
            neuron_firing = write_svg(
                "psych_act1_neuron.svg",
                '<path d="M -100,-160 L -20,-80 L 80,-140 L 40,0 L 120,60" fill="none" stroke="black" stroke-width="16"/>'
                '<circle cx="-100" cy="-160" r="22" fill="none" stroke="black" stroke-width="12"/>'
                '<circle cx="80" cy="-140" r="22" fill="none" stroke="black" stroke-width="12"/>'
                '<circle cx="120" cy="60" r="22" fill="none" stroke="black" stroke-width="12"/>',
            )
            bias_arrow = write_svg(
                "psych_act1_arrow.svg",
                '<path d="M -60,-320 L 40,-240 M 10,-300 L 40,-240 L -20,-240" fill="none" stroke="black" stroke-width="14"/>',
            )
            manifest["Act1_Hook_Incomplete"] = [
                {"file": head_profile, "color": "blue", "pivot": (0.0, 0.0, 0.0), "motion": "pulse_bicep"},
                {"file": neuron_firing, "color": "blue", "pivot": (0.05, 0.05, 0.0), "motion": "hinge_flex"},
                {"file": bias_arrow, "color": "red", "pivot": (0.0, 0.28, 0.0), "motion": "bounce_arrow"},
            ]

            dice_throw = write_svg(
                "psych_act2_dice.svg",
                '<rect x="-280" y="-80" width="160" height="160" rx="24" transform="rotate(25 -200 0)" fill="none" stroke="black" stroke-width="16"/>'
                '<circle cx="-200" cy="0" r="14" fill="none" stroke="black" stroke-width="14"/>',
            )
            trajectory_arc = write_svg(
                "psych_act2_trajectory.svg",
                '<path d="M -300,-180 C -150,-320 50,-240 250,-40" fill="none" stroke="black" stroke-width="16"/>'
                '<path d="M 180,-80 L 250,-40 L 220,-110" fill="none" stroke="black" stroke-width="14"/>',
            )
            casino_table = write_svg(
                "psych_act2_table.svg",
                '<path d="M -420,180 L 420,180 M -420,300 L 420,300 M -250,180 L -250,300 M 0,180 L 0,300 M 250,180 L 250,300" fill="none" stroke="black" stroke-width="16"/>',
            )
            manifest["Act2_Core_Mechanism"] = [
                {"file": dice_throw, "color": "blue", "pivot": (-0.2, 0.0, 0.0), "motion": "slide_in_left"},
                {"file": trajectory_arc, "color": "blue", "pivot": (0.1, 0.1, 0.0), "motion": "slide_in_right"},
                {"file": casino_table, "color": "yellow", "pivot": (0.0, -0.2, 0.0), "motion": "breathe_scale"},
            ]

            randomness_curve = write_svg(
                "psych_act3_random.svg",
                '<path d="M -400,100 C -300,-120 -200,220 -100,40 C 0,-180 100,180 200,-60 C 300,140 400,-100 450,20" fill="none" stroke="black" stroke-width="16"/>',
            )
            illusion_barrier = write_svg(
                "psych_act3_barrier.svg",
                '<rect x="-300" y="-120" width="600" height="80" rx="14" fill="none" stroke="black" stroke-width="16"/>'
                '<path d="M -180,-120 L -120,-40 M -40,-120 L 20,-40 M 100,-120 L 160,-40" fill="none" stroke="black" stroke-width="12"/>',
            )
            manifest["Act3_Obstacle_Friction"] = [
                {"file": randomness_curve, "color": "yellow", "pivot": (0.0, 0.0, 0.0), "motion": "wave_shift"},
                {"file": illusion_barrier, "color": "red", "pivot": (0.0, -0.1, 0.0), "motion": "recoil_bounce"},
            ]

            dopamine_surge = write_svg(
                "psych_act4_dopamine.svg",
                '<circle cx="-240" cy="200" r="34" fill="none" stroke="black" stroke-width="14"/>'
                '<circle cx="-80" cy="240" r="40" fill="none" stroke="black" stroke-width="14"/>'
                '<circle cx="100" cy="190" r="36" fill="none" stroke="black" stroke-width="14"/>'
                '<circle cx="260" cy="230" r="32" fill="none" stroke="black" stroke-width="14"/>'
                '<path d="M -240,160 L -240,60 M -80,195 L -80,40 M 100,150 L 100,50 M 260,190 L 260,70" fill="none" stroke="black" stroke-width="12"/>',
            )
            broken_belief = write_svg(
                "psych_act4_belief.svg",
                '<path d="M -380,-100 C -200,-120 0,-40 240,-180" fill="none" stroke="black" stroke-width="16"/>'
                '<path d="M -30,-60 L 30,-120 M 10,-50 L -10,-110" fill="none" stroke="black" stroke-width="14"/>',
            )
            manifest["Act4_Trigger_Action"] = [
                {"file": dopamine_surge, "color": "green", "pivot": (0.0, 0.2, 0.0), "motion": "drop_cascade"},
                {"file": broken_belief, "color": "yellow", "pivot": (0.0, -0.1, 0.0), "motion": "peel_away"},
            ]

            lattice_left = write_svg(
                "psych_act5_lattice_left.svg",
                '<path d="M -420,180 L -60,180 M -420,-180 L -60,-180 M -420,-220 L -420,220" fill="none" stroke="black" stroke-width="18"/>'
                '<circle cx="-240" cy="0" r="60" fill="none" stroke="black" stroke-width="14"/>',
            )
            lattice_right = write_svg(
                "psych_act5_lattice_right.svg",
                '<path d="M 60,180 L 420,180 M 60,-180 L 420,-180 M 420,-220 L 420,220" fill="none" stroke="black" stroke-width="18"/>'
                '<circle cx="240" cy="0" r="60" fill="none" stroke="black" stroke-width="14"/>',
            )
            rational_cortex = write_svg(
                "psych_act5_cortex.svg",
                '<rect x="-260" y="-50" width="520" height="100" rx="20" fill="none" stroke="black" stroke-width="18"/>'
                '<path d="M -150,0 L 150,0 M 0,-50 L 0,50" fill="none" stroke="black" stroke-width="14"/>',
            )
            manifest["Act5_Resolution_Bridge"] = [
                {"file": lattice_left, "color": "blue", "pivot": (-0.25, 0.0, 0.0), "motion": "ratchet_in_left"},
                {"file": lattice_right, "color": "blue", "pivot": (0.25, 0.0, 0.0), "motion": "ratchet_in_right"},
                {"file": rational_cortex, "color": "red", "pivot": (0.0, 0.0, 0.0), "motion": "ratchet_power_stroke"},
            ]

        else:
            # STEM: Kinetic Molecular / Muscle Filament Rig
            arm_base = write_svg(
                "stem_act1_upper_arm.svg",
                '<path d="M -320,80 C -220,110 -80,105 20,75 L 20,-45 C -90,-15 -220,-20 -320,-40 Z" fill="none" stroke="black" stroke-width="14"/>'
                '<path d="M -230,-35 C -160,-145 -60,-145 5,-40" fill="none" stroke="black" stroke-width="18"/>',
            )
            forearm_hinged = write_svg(
                "stem_act1_forearm.svg",
                '<path d="M 0,0 L 240,-180 L 285,-145 L 45,45 Z" fill="none" stroke="black" stroke-width="14"/>'
                '<circle cx="275" cy="-175" r="48" fill="none" stroke="black" stroke-width="14"/>',
            )
            hook_callout = write_svg(
                "stem_act1_callout.svg",
                '<path d="M -115,-175 L -115,-280 M -150,-215 L -115,-170 L -80,-215" fill="none" stroke="black" stroke-width="12"/>'
                '<path d="M -240,-330 L 20,-330 M -210,-370 L -30,-370" fill="none" stroke="black" stroke-width="10"/>',
            )
            manifest["Act1_Hook_Incomplete"] = [
                {"file": arm_base, "color": "blue", "pivot": (0.0, 0.0, 0.0), "motion": "pulse_bicep"},
                {"file": forearm_hinged, "color": "blue", "pivot": (0.15, 0.05, 0.0), "motion": "hinge_flex"},
                {"file": hook_callout, "color": "red", "pivot": (0.0, 0.3, 0.0), "motion": "bounce_arrow"},
            ]

            actin_top = write_svg(
                "stem_act2_actin_top.svg",
                '<path d="M -420,220 C -280,245 -140,195 0,220 C 140,245 280,195 420,220" fill="none" stroke="black" stroke-width="16"/>'
                '<circle cx="-300" cy="220" r="28" fill="none" stroke="black" stroke-width="12"/>'
                '<circle cx="-150" cy="220" r="28" fill="none" stroke="black" stroke-width="12"/>'
                '<circle cx="0" cy="220" r="28" fill="none" stroke="black" stroke-width="12"/>'
                '<circle cx="150" cy="220" r="28" fill="none" stroke="black" stroke-width="12"/>'
                '<circle cx="300" cy="220" r="28" fill="none" stroke="black" stroke-width="12"/>',
            )
            actin_bottom = write_svg(
                "stem_act2_actin_bottom.svg",
                '<path d="M -420,-220 C -280,-195 -140,-245 0,-220 C 140,-195 280,-245 420,-220" fill="none" stroke="black" stroke-width="16"/>'
                '<circle cx="-300" cy="-220" r="28" fill="none" stroke="black" stroke-width="12"/>'
                '<circle cx="-150" cy="-220" r="28" fill="none" stroke="black" stroke-width="12"/>'
                '<circle cx="0" cy="-220" r="28" fill="none" stroke="black" stroke-width="12"/>'
                '<circle cx="150" cy="-220" r="28" fill="none" stroke="black" stroke-width="12"/>'
                '<circle cx="300" cy="-220" r="28" fill="none" stroke="black" stroke-width="12"/>',
            )
            myosin_core = write_svg(
                "stem_act2_myosin.svg",
                '<rect x="-360" y="-45" width="720" height="90" rx="20" fill="none" stroke="black" stroke-width="18"/>'
                '<path d="M -250,45 L -210,125 M -50,45 L -10,125 M 150,45 L 190,125" fill="none" stroke="black" stroke-width="14"/>'
                '<path d="M -250,-45 L -210,-125 M -50,-45 L -10,-125 M 150,-45 L 190,-125" fill="none" stroke="black" stroke-width="14"/>',
            )
            manifest["Act2_Core_Mechanism"] = [
                {"file": actin_top, "color": "blue", "pivot": (0.0, 0.22, 0.0), "motion": "slide_in_left"},
                {"file": actin_bottom, "color": "blue", "pivot": (0.0, -0.22, 0.0), "motion": "slide_in_right"},
                {"file": myosin_core, "color": "red", "pivot": (0.0, 0.0, 0.0), "motion": "breathe_scale"},
            ]

            caution_tape = write_svg(
                "stem_act3_caution.svg",
                '<path d="M -430,175 L 430,175 M -430,135 L 430,135" fill="none" stroke="black" stroke-width="14"/>'
                '<path d="M -380,175 L -330,135 M -260,175 L -210,135 M -140,175 L -90,135 M -20,175 L 30,135 M 100,175 L 150,135 M 220,175 L 270,135" fill="none" stroke="black" stroke-width="12"/>',
            )
            blocked_heads = write_svg(
                "stem_act3_blocked.svg",
                '<path d="M -220,0 L -180,115 C -160,135 -130,115 -145,85 L -190,0" fill="none" stroke="black" stroke-width="16"/>'
                '<path d="M 40,0 L 80,115 C 100,135 130,115 115,85 L 70,0" fill="none" stroke="black" stroke-width="16"/>'
                '<path d="M -60,195 L 20,275 M 20,195 L -60,275" fill="none" stroke="black" stroke-width="18"/>',
            )
            manifest["Act3_Obstacle_Friction"] = [
                {"file": caution_tape, "color": "yellow", "pivot": (0.0, 0.15, 0.0), "motion": "wave_shift"},
                {"file": blocked_heads, "color": "red", "pivot": (0.0, 0.0, 0.0), "motion": "recoil_bounce"},
            ]

            calcium_swarm = write_svg(
                "stem_act4_calcium.svg",
                '<circle cx="-280" cy="340" r="36" fill="none" stroke="black" stroke-width="14"/>'
                '<circle cx="-90" cy="390" r="36" fill="none" stroke="black" stroke-width="14"/>'
                '<circle cx="110" cy="350" r="36" fill="none" stroke="black" stroke-width="14"/>'
                '<circle cx="290" cy="380" r="36" fill="none" stroke="black" stroke-width="14"/>'
                '<path d="M -280,290 L -280,180 M -90,340 L -90,210 M 110,300 L 110,180 M 290,330 L 290,200" fill="none" stroke="black" stroke-width="12"/>',
            )
            peeling_tape = write_svg(
                "stem_act4_peeled.svg",
                '<path d="M -420,150 C -180,160 80,260 390,410" fill="none" stroke="black" stroke-width="14"/>'
                '<path d="M -390,120 C -150,130 110,230 410,380" fill="none" stroke="black" stroke-width="14"/>',
            )
            manifest["Act4_Trigger_Action"] = [
                {"file": calcium_swarm, "color": "green", "pivot": (0.0, 0.35, 0.0), "motion": "drop_cascade"},
                {"file": peeling_tape, "color": "yellow", "pivot": (-0.4, 0.15, 0.0), "motion": "peel_away"},
            ]

            ratchet_left = write_svg(
                "stem_act5_ratchet_left.svg",
                '<path d="M -440,210 L -60,210 M -440,-210 L -60,-210 M -440,-250 L -440,250" fill="none" stroke="black" stroke-width="18"/>'
                '<circle cx="-260" cy="210" r="24" fill="none" stroke="black" stroke-width="14"/>'
                '<circle cx="-120" cy="210" r="24" fill="none" stroke="black" stroke-width="14"/>',
            )
            ratchet_right = write_svg(
                "stem_act5_ratchet_right.svg",
                '<path d="M 60,210 L 440,210 M 60,-210 L 440,-210 M 440,-250 L 440,250" fill="none" stroke="black" stroke-width="18"/>'
                '<circle cx="120" cy="210" r="24" fill="none" stroke="black" stroke-width="14"/>'
                '<circle cx="260" cy="210" r="24" fill="none" stroke="black" stroke-width="14"/>',
            )
            myosin_pullers = write_svg(
                "stem_act5_pullers.svg",
                '<rect x="-280" y="-40" width="560" height="80" rx="18" fill="none" stroke="black" stroke-width="16"/>'
                '<path d="M -180,40 L -240,195 M -40,40 L -100,195 M 40,40 L 100,195 M 180,40 L 240,195" fill="none" stroke="black" stroke-width="16"/>'
                '<path d="M -180,-40 L -240,-195 M -40,-40 L -100,-195 M 40,-40 L 100,-195 M 180,-40 L 240,-195" fill="none" stroke="black" stroke-width="16"/>',
            )
            manifest["Act5_Resolution_Bridge"] = [
                {"file": ratchet_left, "color": "blue", "pivot": (-0.25, 0.0, 0.0), "motion": "ratchet_in_left"},
                {"file": ratchet_right, "color": "blue", "pivot": (0.25, 0.0, 0.0), "motion": "ratchet_in_right"},
                {"file": myosin_pullers, "color": "red", "pivot": (0.0, 0.0, 0.0), "motion": "ratchet_power_stroke"},
            ]

        # ERASER SCRIBBLE MASK (Used between acts for authentic erase-and-replace across all categories)
        eraser_svg = write_svg(
            "eraser_scribble.svg",
            '<path d="M -450,380 L 450,310 L -440,210 L 440,120 L -430,20 L 450,-80 L -440,-190 L 430,-290 L -400,-380" '
            'fill="none" stroke="black" stroke-width="85" stroke-linecap="round" stroke-linejoin="round"/>',
        )
        manifest["_eraser"] = [{"file": eraser_svg, "color": "paper_erase", "pivot": (0.0, 0.0, 0.0), "motion": "none"}]

        return manifest

    def _build_headless_blender_script(
        self,
        scenes: List[Dict[str, Any]],
        svg_manifest: Dict[str, List[Dict[str, Any]]],
        output_mp4_path: str,
        total_duration: float,
    ) -> str:
        """
        Generates the self-contained Python script executed inside Blender.
        Compatible with both Grease Pencil v3 (Blender 4.3, 4.4, 4.5, 5.x) and Legacy v2 (4.2 LTS).
        """
        payload = {
            "fps": self.fps,
            "total_frames": int(math.ceil(total_duration * self.fps)),
            "output_mp4_path": os.path.abspath(output_mp4_path),
            "scenes": scenes,
            "svg_manifest": svg_manifest,
        }
        payload_json = json.dumps(payload, indent=2)

        script_code = f'''# Auto-generated Headless Blender 2D Crayon Puppet Engine
import bpy
import os
import sys
import json
import math

PAYLOAD = json.loads(r"""{payload_json}""")

def reset_and_configure_scene():
    bpy.ops.wm.read_factory_settings(use_empty=True)
    scene = bpy.context.scene
    scene.render.resolution_x = 1080
    scene.render.resolution_y = 1920
    scene.render.resolution_percentage = 100
    scene.render.fps = PAYLOAD["fps"]
    scene.frame_start = 1
    scene.frame_end = PAYLOAD["total_frames"]

    # Fast Eevee rendering for crisp 2D Grease Pencil output
    for eng in ["BLENDER_EEVEE_NEXT", "BLENDER_EEVEE"]:
        try:
            scene.render.engine = eng
            break
        except Exception:
            pass

    # Configure FFmpeg MP4 output
    scene.render.image_settings.file_format = 'FFMPEG'
    scene.render.ffmpeg.format = 'MPEG4'
    scene.render.ffmpeg.codec = 'H264'
    scene.render.ffmpeg.constant_rate_factor = 'HIGH'
    scene.render.ffmpeg.ffmpeg_preset = 'GOOD'
    scene.render.filepath = PAYLOAD["output_mp4_path"]

    # Off-White Sketchbook Paper World Background
    try:
        scene.view_settings.view_transform = 'Standard'
    except Exception:
        pass

    world = bpy.data.worlds.new("CrayonPaperWorld")
    scene.world = world
    world.use_nodes = True
    bg_node = world.node_tree.nodes.get("Background")
    if bg_node:
        bg_node.inputs[0].default_value = (0.965, 0.945, 0.902, 1.0)
        bg_node.inputs[1].default_value = 1.0

    # 9:16 Orthographic 2D Camera
    cam_data = bpy.data.cameras.new("OrthoCrayonCam")
    cam_data.type = 'ORTHO'
    cam_data.ortho_scale = 3.2
    cam_obj = bpy.data.objects.new("OrthoCrayonCam", cam_data)
    scene.collection.objects.link(cam_obj)
    scene.camera = cam_obj
    cam_obj.location = (0.0, 0.0, 10.0)
    cam_obj.rotation_euler = (0.0, 0.0, 0.0)

    # Subtle paper grain background frame lines (keeps Frame 1 visually grounded)
    return scene

def get_or_create_crayon_material(name, rgba):
    if name in bpy.data.materials:
        return bpy.data.materials[name]
    mat = bpy.data.materials.new(name=name)
    if hasattr(bpy.data.materials, "create_gpencil_data"):
        bpy.data.materials.create_gpencil_data(mat)
    gp_style = getattr(mat, "grease_pencil", None) or getattr(mat, "gpencil_style", None)
    if gp_style:
        try:
            gp_style.color = rgba
        except Exception:
            pass
        try:
            gp_style.show_stroke = True
            gp_style.show_fill = False
        except Exception:
            pass
    return mat

def import_svg_as_grease_pencil(svg_path, obj_name):
    """Universal SVG -> Grease Pencil importer across Blender 4.2, 4.3, 4.4, and 5.x."""
    before_objs = set(bpy.data.objects)

    # 1. Try Blender 4.3+ / 5.x native Grease Pencil v3 SVG operator
    imported = False
    if hasattr(bpy.ops.wm, "grease_pencil_import_svg"):
        try:
            bpy.ops.wm.grease_pencil_import_svg(filepath=svg_path, resolution=12, scale=1.0)
            imported = True
        except Exception:
            imported = False

    # 2. Fallback to Blender 4.2 gpencil_import_svg
    if not imported and hasattr(bpy.ops.wm, "gpencil_import_svg"):
        try:
            bpy.ops.wm.gpencil_import_svg(filepath=svg_path, resolution=12, scale=1.0)
            imported = True
        except Exception:
            imported = False

    # 3. Fallback to Curve SVG import + convert to Grease Pencil
    if not imported:
        bpy.ops.import_curve.svg(filepath=svg_path)
        new_curves = [o for o in (set(bpy.data.objects) - before_objs) if o.type == 'CURVE']
        if new_curves:
            bpy.ops.object.select_all(action='DESELECT')
            for c in new_curves:
                c.select_set(True)
            bpy.context.view_layer.objects.active = new_curves[0]
            if len(new_curves) > 1:
                bpy.ops.object.join()
            try:
                bpy.ops.object.convert(target='GREASEPENCIL')
            except Exception:
                bpy.ops.object.convert(target='GPENCIL')

    after_objs = set(bpy.data.objects) - before_objs
    gp_objs = [o for o in after_objs if o.type in ('GREASEPENCIL', 'GPENCIL', 'CURVE')]
    if not gp_objs:
        return None

    main_obj = gp_objs[0]
    main_obj.name = obj_name
    # Normalize SVG scale to fit 9:16 ortho camera
    main_obj.scale = (0.38, 0.38, 0.38)
    return main_obj

def apply_crayon_style_and_modifiers(obj, mat, start_frame, draw_frames, end_frame, is_eraser=False):
    """Applies crayon material, Grease Pencil v3/v2 Build modifier, and continuous line-boil Noise."""
    if hasattr(obj.data, "materials"):
        obj.data.materials.clear()
        obj.data.materials.append(mat)

    # Set uniform crayon stroke thickness if Grease Pencil v3 drawings are accessible
    if hasattr(obj.data, "layers"):
        for layer in obj.data.layers:
            try:
                layer.use_lights = False
            except Exception:
                pass
            frames = getattr(layer, "frames", [])
            for fr in frames:
                drawing = getattr(fr, "drawing", None)
                if drawing and hasattr(drawing, "strokes"):
                    for st in drawing.strokes:
                        for pt in st.points:
                            try:
                                pt.radius = 0.045 if is_eraser else 0.016
                                pt.opacity = 1.0 if is_eraser else 0.94
                            except Exception:
                                pass

    # Detect whether Blender uses v3 (obj.modifiers) or v2 (obj.grease_pencil_modifiers)
    use_v3_mods = True
    build_mod = None
    try:
        build_mod = obj.modifiers.new(name="CrayonDrawIn", type='GREASE_PENCIL_BUILD')
    except Exception:
        use_v3_mods = False
        if hasattr(obj, "grease_pencil_modifiers"):
            build_mod = obj.grease_pencil_modifiers.new(name="CrayonDrawIn", type='GP_BUILD')

    if build_mod:
        for attr, val in [
            ("mode", 'CONCURRENT'),
            ("transition", 'GROW'),
            ("use_restrict_frame_range", True),
            ("frame_start", start_frame),
            ("frame_end", start_frame + draw_frames),
            ("start_delay", 0),
            ("length", draw_frames),
        ]:
            if hasattr(build_mod, attr):
                try:
                    setattr(build_mod, attr, val)
                except Exception:
                    pass

    # Add Crayon Line-Boil Noise Modifier
    noise_mod = None
    if use_v3_mods:
        try:
            noise_mod = obj.modifiers.new(name="CrayonBoil", type='GREASE_PENCIL_NOISE')
        except Exception:
            pass
    elif hasattr(obj, "grease_pencil_modifiers"):
        try:
            noise_mod = obj.grease_pencil_modifiers.new(name="CrayonBoil", type='GP_NOISE')
        except Exception:
            pass

    if noise_mod:
        for attr, val in [
            ("factor", 0.18),
            ("factor_thickness", 0.25),
            ("use_random", True),
            ("step", 4),
        ]:
            if hasattr(noise_mod, attr):
                try:
                    setattr(noise_mod, attr, val)
                except Exception:
                    pass

def keyframe_visibility(obj, visible_start, visible_end, total_frames):
    """Controls exact frame range visibility for each Act and Erase transition."""
    def set_vis(frame, hidden):
        obj.hide_render = hidden
        obj.hide_viewport = hidden
        obj.keyframe_insert(data_path="hide_render", frame=frame)
        obj.keyframe_insert(data_path="hide_viewport", frame=frame)

    if visible_start > 1:
        set_vis(1, True)
        set_vis(visible_start - 1, True)
    set_vis(visible_start, False)
    set_vis(visible_end, False)
    if visible_end < total_frames:
        set_vis(visible_end + 1, True)

def animate_puppet_kinematics(obj, motion_type, start_f, end_f, base_pivot):
    """Keyframes true 2D articulated movement (hinges, ratchets, cascades, recoils) per puppet part."""
    ox, oy, oz = base_pivot
    obj.location = (ox, oy, oz)
    obj.rotation_euler = (0.0, 0.0, 0.0)
    base_scale = tuple(obj.scale)

    mid_f = int((start_f + end_f) / 2)
    quarter_f = int(start_f + (end_f - start_f) * 0.3)
    three_q_f = int(start_f + (end_f - start_f) * 0.75)

    obj.keyframe_insert(data_path="location", frame=start_f)
    obj.keyframe_insert(data_path="rotation_euler", frame=start_f)
    obj.keyframe_insert(data_path="scale", frame=start_f)

    if motion_type == "hinge_flex":
        # Forearm pivots upward at elbow joint twice
        obj.rotation_euler = (0.0, 0.0, math.radians(42.0))
        obj.keyframe_insert(data_path="rotation_euler", frame=quarter_f)
        obj.rotation_euler = (0.0, 0.0, math.radians(10.0))
        obj.keyframe_insert(data_path="rotation_euler", frame=mid_f)
        obj.rotation_euler = (0.0, 0.0, math.radians(52.0))
        obj.keyframe_insert(data_path="rotation_euler", frame=three_q_f)

    elif motion_type == "pulse_bicep":
        obj.scale = (base_scale[0] * 1.0, base_scale[1] * 1.18, base_scale[2])
        obj.keyframe_insert(data_path="scale", frame=quarter_f)
        obj.scale = base_scale
        obj.keyframe_insert(data_path="scale", frame=mid_f)
        obj.scale = (base_scale[0] * 1.05, base_scale[1] * 1.24, base_scale[2])
        obj.keyframe_insert(data_path="scale", frame=three_q_f)

    elif motion_type == "bounce_arrow":
        for f_step in range(start_f, end_f, 15):
            offset = 0.08 if ((f_step - start_f) // 15) % 2 == 0 else -0.04
            obj.location = (ox, oy + offset, oz)
            obj.keyframe_insert(data_path="location", frame=f_step)

    elif motion_type in ("slide_in_left", "ratchet_in_left"):
        obj.location = (ox - 0.35, oy, oz)
        obj.keyframe_insert(data_path="location", frame=start_f)
        obj.location = (ox + 0.18, oy, oz)
        obj.keyframe_insert(data_path="location", frame=three_q_f)

    elif motion_type in ("slide_in_right", "ratchet_in_right"):
        obj.location = (ox + 0.35, oy, oz)
        obj.keyframe_insert(data_path="location", frame=start_f)
        obj.location = (ox - 0.18, oy, oz)
        obj.keyframe_insert(data_path="location", frame=three_q_f)

    elif motion_type == "recoil_bounce":
        # Myosin head reaches up, hits caution tape, bounces down
        obj.location = (ox, oy + 0.14, oz)
        obj.keyframe_insert(data_path="location", frame=quarter_f)
        obj.location = (ox, oy - 0.08, oz)
        obj.keyframe_insert(data_path="location", frame=quarter_f + 8)
        obj.location = (ox, oy + 0.14, oz)
        obj.keyframe_insert(data_path="location", frame=three_q_f)
        obj.location = (ox, oy - 0.06, oz)
        obj.keyframe_insert(data_path="location", frame=three_q_f + 8)

    elif motion_type == "drop_cascade":
        obj.location = (ox, oy + 0.45, oz)
        obj.keyframe_insert(data_path="location", frame=start_f)
        obj.location = (ox, oy - 0.15, oz)
        obj.keyframe_insert(data_path="location", frame=mid_f)

    elif motion_type == "peel_away":
        obj.rotation_euler = (0.0, 0.0, math.radians(28.0))
        obj.location = (ox + 0.35, oy + 0.30, oz)
        obj.keyframe_insert(data_path="rotation_euler", frame=three_q_f)
        obj.keyframe_insert(data_path="location", frame=three_q_f)

    elif motion_type == "ratchet_power_stroke":
        for step_idx, f_curr in enumerate(range(start_f + 10, end_f - 10, 18)):
            shift = 0.09 if step_idx % 2 == 0 else -0.05
            obj.scale = (base_scale[0] * (1.0 + shift), base_scale[1] * (1.0 - shift * 0.5), base_scale[2])
            obj.keyframe_insert(data_path="scale", frame=f_curr)

def build_full_animation():
    scene = reset_and_configure_scene()
    total_frames = PAYLOAD["total_frames"]

    palette = {{
        "blue": get_or_create_crayon_material("CrayonBlue", (0.12, 0.38, 0.82, 1.0)),
        "red": get_or_create_crayon_material("CrayonRed", (0.86, 0.18, 0.18, 1.0)),
        "yellow": get_or_create_crayon_material("CrayonGold", (0.88, 0.62, 0.06, 1.0)),
        "green": get_or_create_crayon_material("CrayonGreen", (0.15, 0.68, 0.32, 1.0)),
        "paper_erase": get_or_create_crayon_material("PaperEraser", (0.965, 0.945, 0.902, 1.0)),
    }}

    scenes = PAYLOAD["scenes"]
    manifest = PAYLOAD["svg_manifest"]
    eraser_info = manifest.get("_eraser", [])

    for sc in scenes:
        act_name = sc["name"]
        s_frame = sc["start_frame"]
        e_frame = sc["end_frame"]
        d_frames = sc["draw_frames"]
        er_frames = sc["erase_frames"]

        parts = manifest.get(act_name, [])
        for p_idx, part in enumerate(parts):
            svg_file = part["file"]
            if not os.path.exists(svg_file):
                continue

            obj_name = f"{{act_name}}_part_{{p_idx}}"
            gp_obj = import_svg_as_grease_pencil(svg_file, obj_name)
            if not gp_obj:
                continue

            mat = palette.get(part.get("color", "blue"), palette["blue"])
            # Frame 1 Visual Incomplete rule: Act 1 Part 0 is already 60% drawn on Frame 1
            part_draw_frames = 5 if (sc["index"] == 0 and p_idx == 0) else d_frames
            part_start = s_frame if p_idx == 0 else min(e_frame - 10, s_frame + p_idx * 8)

            apply_crayon_style_and_modifiers(
                gp_obj, mat, start_frame=part_start, draw_frames=part_draw_frames, end_frame=e_frame
            )
            keyframe_visibility(gp_obj, s_frame, e_frame, total_frames)
            animate_puppet_kinematics(
                gp_obj,
                part.get("motion", "none"),
                s_frame,
                e_frame,
                tuple(part.get("pivot", (0.0, 0.0, 0.0))),
            )

        # Add Erase-and-Replace Scribble Wipe at the end of Acts 1-4
        if sc["index"] < len(scenes) - 1 and eraser_info:
            er_svg = eraser_info[0]["file"]
            if os.path.exists(er_svg):
                er_start = max(s_frame + 10, e_frame - er_frames)
                er_obj = import_svg_as_grease_pencil(er_svg, f"Eraser_{{act_name}}")
                if er_obj:
                    er_obj.location = (0.0, 0.0, 0.5)
                    apply_crayon_style_and_modifiers(
                        er_obj,
                        palette["paper_erase"],
                        start_frame=er_start,
                        draw_frames=er_frames,
                        end_frame=e_frame,
                        is_eraser=True,
                    )
                    keyframe_visibility(er_obj, er_start, e_frame, total_frames)

    print(f"[CrayonStudio] Rendering {{total_frames}} frames to {{PAYLOAD['output_mp4_path']}}...")
    bpy.ops.render.render(animation=True)
    print("[CrayonStudio] Headless Blender render complete.")

if __name__ == "__main__":
    build_full_animation()
'''
        return script_code

    def render_project(
        self,
        project_dir: str,
        words_json_path: str,
        output_mp4_path: str,
        category: str = "STEM",
        duration_override: Optional[float] = None,
        progress_callback: Optional[Callable[[str], None]] = None,
    ) -> str:
        """
        Full end-to-end execution:
        1. Parses Whisper word timestamps for semantic frame alignment.
        2. Generates multi-part SVG vector puppets inside project_dir/svg_assets.
        3. Writes headless Blender Grease Pencil runner script.
        4. Executes Blender in background mode and streams progress logs.
        """
        os.makedirs(project_dir, exist_ok=True)
        svg_dir = os.path.join(project_dir, "svg_assets")

        if progress_callback:
            progress_callback("[Blender] Aligning word timestamps to 30fps keyframes...")

        total_duration, scenes = self.parse_word_cues(
            words_json_path=words_json_path,
            default_duration=duration_override or 65.0,
        )

        if progress_callback:
            progress_callback(f"[Blender] Generating articulated SVG puppets for {len(scenes)} acts...")

        svg_manifest = self.generate_svg_puppets(svg_dir=svg_dir, category=category)

        script_path = os.path.join(project_dir, "_run_blender_scene.py")
        script_content = self._build_headless_blender_script(
            scenes=scenes,
            svg_manifest=svg_manifest,
            output_mp4_path=output_mp4_path,
            total_duration=total_duration,
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
            progress_callback(f"[Blender] Launching headless render: {' '.join(cmd)}")

        process = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            encoding="utf-8",
            errors="replace",
        )

        if process.stdout:
            for line in process.stdout:
                clean_line = line.strip()
                if clean_line and progress_callback:
                    if "Fra:" in clean_line or "[CrayonStudio]" in clean_line or "Error" in clean_line:
                        progress_callback(f"[Blender] {clean_line}")

        return_code = process.wait()
        if return_code != 0 or not os.path.exists(output_mp4_path):
            raise RuntimeError(
                f"Headless Blender exited with code {return_code}. Verify Blender path ({self.blender_path})."
            )

        if progress_callback:
            progress_callback(f"[Blender] Render pass saved: {output_mp4_path}")

        return output_mp4_path


# Top-level functional adapter so any import pattern in app.py works out of the box
def render_crayon_animation(
    project_dir: str,
    words_json_path: str,
    output_mp4_path: str,
    category: str = "STEM",
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
