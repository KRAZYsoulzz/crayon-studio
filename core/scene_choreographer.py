"""Universal Storybook Visual Choreographer.

Analyzes ANY script and aligned word timestamps from faster-whisper, extracting
narrative entities, verbs, and physical processes across 5 Acts. Generates a structured
'visual_blueprint.json' with parameterized Cubic Bezier assemblies, dynamic on-screen
typography labels, and purposeful cause-and-effect process animations.
"""

from __future__ import annotations

import json
import logging
import math
import os
import re
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger("crayon_studio.scene_choreographer")

# =====================================================================
# GEOMETRY HELPERS (Cubic Bezier & Poly Point Generators)
# =====================================================================

def bezier_circle(cx: float, cy: float, r: float, n: int = 16) -> List[Tuple[float, float]]:
    """Generates smooth circular control points suitable for Bezier AUTO handles."""
    return [
        (
            round(cx + r * math.cos(2 * math.pi * i / n), 4),
            round(cy + r * math.sin(2 * math.pi * i / n), 4),
        )
        for i in range(n + 1)
    ]


def bezier_wave(x0: float, x1: float, y_base: float, amp: float, freq: float, n: int = 20) -> List[Tuple[float, float]]:
    """Generates a smooth undulating wave with Bezier points."""
    pts = []
    for i in range(n + 1):
        t = i / float(n)
        x = x0 + (x1 - x0) * t
        y = y_base + amp * math.sin(t * math.pi * 2.0 * freq)
        pts.append((round(x, 4), round(y, 4)))
    return pts


def bezier_arc(p0: Tuple[float, float], p1: Tuple[float, float], p2: Tuple[float, float], n: int = 12) -> List[Tuple[float, float]]:
    """Generates a quadratic/cubic Bezier trajectory curve through control points."""
    pts = []
    for i in range(n + 1):
        t = i / float(n)
        # B(t) = (1-t)^2 * p0 + 2(1-t)t * p1 + t^2 * p2
        x = (1 - t) ** 2 * p0[0] + 2 * (1 - t) * t * p1[0] + (t ** 2) * p2[0]
        y = (1 - t) ** 2 * p0[1] + 2 * (1 - t) * t * p1[1] + (t ** 2) * p2[1]
        pts.append((round(x, 4), round(y, 4)))
    return pts


def rect_box(cx: float, cy: float, w: float, h: float) -> List[Tuple[float, float]]:
    """Generates closed rectangular path coordinates."""
    hw, hh = w / 2.0, h / 2.0
    return [
        (round(cx - hw, 4), round(cy - hh, 4)),
        (round(cx + hw, 4), round(cy - hh, 4)),
        (round(cx + hw, 4), round(cy + hh, 4)),
        (round(cx - hw, 4), round(cy + hh, 4)),
        (round(cx - hw, 4), round(cy - hh, 4)),
    ]


# =====================================================================
# ACT CLASSIFIER & LABEL MINER
# =====================================================================

ARCHETYPE_KEYWORDS = {
    "vault_heist_bypass": ["vault", "heist", "laser", "sensor", "alarm", "security", "bypassed", "safe", "diamond", "drill", "door"],
    "vacuum_gravity_drop": ["vacuum", "feather", "bowling", "gravity", "bell jar", "pump", "freefall", "fall", "air resistance", "terminal"],
    "brain_psychology_pathway": ["brain", "psychology", "dopamine", "illusion", "casino", "gamble", "reward", "neural", "cognitive", "mind", "slot"],
    "structural_load_arch": ["arch", "bridge", "keystone", "load", "pier", "foundation", "seawall", "span", "compression", "solid", "mass"],
    "lattice_bond_growth": ["crystal", "lattice", "tobermorite", "interlock", "grow", "stitch", "bond", "healing", "molecular", "needle"],
    "micro_cross_section": ["micro", "pore", "crack", "channel", "infiltrat", "flow", "void", "brine", "fluid", "dissolve", "microscopic"],
    "recipe_combine": ["mix", "recipe", "ingredient", "ash", "lime", "react", "pour", "cauldron", "vessel", "compound", "reaction"],
    "comparison_split": ["vs", "versus", "compare", "crumble", "fail", "holding", "strong", "modern", "ancient", "why", "secret", "difference"],
}


def classify_act_archetype(text: str, act_index: int, category: str = "STEM") -> str:
    """Classifies an act's script into the most vivid visual archetype."""
    text_lower = text.lower()

    # Category hints
    if "heist" in category.lower() or "escape" in category.lower():
        if act_index in (0, 2, 3, 4):
            return "vault_heist_bypass"
    if "psychology" in category.lower():
        if act_index in (1, 2, 3):
            return "brain_psychology_pathway"

    # Score against keywords
    best_match = None
    best_score = 0
    for arch, keywords in ARCHETYPE_KEYWORDS.items():
        score = sum(2 if kw in text_lower else 0 for kw in keywords)
        if score > best_score:
            best_score = score
            best_match = arch

    if best_match and best_score >= 2:
        return best_match

    # Default progression for science / engineering narratives:
    progression = [
        "comparison_split",        # Act 1: Hook / Comparison / Visual Mystery
        "recipe_combine",          # Act 2: Components / Setup / Raw Elements
        "micro_cross_section",     # Act 3: Micro Cross-Section / Flow & Friction
        "lattice_bond_growth",     # Act 4: Dynamic Action / Crystal Lattice Stitch
        "structural_load_arch",    # Act 5: Solid Arch / Resolution / Victory
    ]
    return progression[min(act_index, 4)]


def extract_salient_labels(text: str, archetype: str) -> Dict[str, str]:
    """Extracts short, uppercase callout labels from the script for 3D typography."""
    words = [re.sub(r"[^A-Za-z0-9]", "", w).upper() for w in text.split() if w]
    text_upper = " ".join(words)

    # Contextual dictionary
    if archetype == "comparison_split":
        sub_a = "SUBJECT A"
        sub_b = "SUBJECT B"
        if "ROMAN" in text_upper:
            sub_a = "ROMAN CONCRETE"
            sub_b = "MODERN CONCRETE"
        elif "VACUUM" in text_upper or "BOWLING" in text_upper:
            sub_a = "VACUUM"
            sub_b = "AIR RESISTANCE"
        elif "PLAYER" in text_upper or "HOUSE" in text_upper:
            sub_a = "PLAYER"
            sub_b = "THE HOUSE"
        return {"left": sub_a, "right": sub_b, "center": "VS"}

    elif archetype == "recipe_combine":
        ing1 = "INGREDIENT 1"
        ing2 = "INGREDIENT 2"
        ing3 = "CATALYST"
        if "ASH" in text_upper:
            ing1 = "VOLCANIC ASH"
        if "LIME" in text_upper:
            ing2 = "QUICKLIME"
        if "SEAWATER" in text_upper or "BRINE" in text_upper or "OCEAN" in text_upper:
            ing3 = "SEAWATER"
        return {"ing1": ing1, "ing2": ing2, "ing3": ing3, "vessel": "MATRIX"}

    elif archetype == "micro_cross_section":
        return {"scope": "MICROSCOPE", "channel": "PORE CHANNEL", "action": "INFILTRATION"}

    elif archetype == "lattice_bond_growth":
        term = "CRYSTAL LATTICE"
        if "TOBERMORITE" in text_upper:
            term = "TOBERMORITE"
        elif "NEURAL" in text_upper:
            term = "SYNAPSE"
        return {"title": term, "status": "SELF-HEALING"}

    elif archetype == "structural_load_arch":
        return {"arch": "ROMAN ARCH", "keystone": "KEYSTONE LOCK", "load": "FORCE DISSIPATION"}

    elif archetype == "vault_heist_bypass":
        return {"vault": "REINFORCED VAULT", "sensor": "LASER SENSOR", "status": "BYPASSED"}

    elif archetype == "vacuum_gravity_drop":
        return {"left": "BOWLING BALL", "right": "FEATHER", "status": "EQUAL FALL (0g)"}

    elif archetype == "brain_psychology_pathway":
        return {"cortex": "CORTEX", "dopamine": "DOPAMINE LOOP", "target": "REWARD"}

    return {"label": "BLUEPRINT"}


# =====================================================================
# UNIVERSAL PARAMETERIZED COMPONENT GENERATORS
# =====================================================================

def build_comparison_split_components(labels: Dict[str, str]) -> List[Dict[str, Any]]:
    """Builds side-by-side comparison: Subject A (strong + checkmark) vs Subject B (fracturing)."""
    components = []

    # Notebook outer card frame
    components.append({
        "name": "FrameCard",
        "spline_type": "POLY",
        "thickness": 0.018,
        "color": "charcoal",
        "strokes": [rect_box(0.0, 0.55, 2.55, 1.85)],
        "animation": {"type": "draw_stroke_progressive", "start_offset": 0, "duration": 12},
    })

    # Subject A (Left): Solid curved block / tower
    block_a = rect_box(-0.62, 0.42, 0.75, 1.10)
    components.append({
        "name": "SubjectA_Block",
        "spline_type": "POLY",
        "thickness": 0.038,
        "color": "charcoal",
        "strokes": [block_a, [(-0.99, 0.65), (-0.25, 0.65)], [(-0.99, 0.20), (-0.25, 0.20)]],
        "animation": {"type": "draw_stroke_progressive", "start_offset": 0, "duration": 15},
    })

    # Green checkmark badge over Subject A
    check = [
        bezier_circle(-0.62, 1.15, 0.22, 16),
        [(-0.72, 1.15), (-0.64, 1.05), (-0.50, 1.25)],
    ]
    components.append({
        "name": "SubjectA_Check",
        "spline_type": "BEZIER",
        "thickness": 0.040,
        "color": "green",
        "strokes": check,
        "animation": {"type": "draw_stroke_progressive", "start_offset": 6, "duration": 16},
    })

    # Subject B (Right): Fracturing block under force wave
    block_b = rect_box(0.62, 0.42, 0.75, 1.10)
    components.append({
        "name": "SubjectB_Block",
        "spline_type": "POLY",
        "thickness": 0.036,
        "color": "charcoal",
        "strokes": [block_b],
        "animation": {"type": "draw_stroke_progressive", "start_offset": 4, "duration": 15},
    })

    # Jagged fracture crack running through Subject B
    crack = [
        [(0.35, 0.90), (0.55, 0.68), (0.42, 0.45), (0.78, 0.22), (0.60, -0.10)],
    ]
    components.append({
        "name": "SubjectB_Crack",
        "spline_type": "POLY",
        "thickness": 0.038,
        "color": "red",
        "strokes": crack,
        "animation": {"type": "fracture_and_fall", "start_offset": 12, "duration": 24},
    })

    # Dynamic force impact wave (waves/arrows driving in from right)
    impact_wave = [
        bezier_wave(0.20, 1.15, 0.75, 0.12, 1.8),
        bezier_wave(0.20, 1.15, 0.35, 0.12, 1.8),
    ]
    components.append({
        "name": "ImpactForceWave",
        "spline_type": "BEZIER",
        "thickness": 0.038,
        "color": "blue",
        "strokes": impact_wave,
        "animation": {"type": "flow_through_channel", "start_offset": 8, "duration": 22},
    })

    return components


def build_recipe_combine_components(labels: Dict[str, str]) -> List[Dict[str, Any]]:
    """Builds 3 labeled source ingredients pouring along curved Bezier arcs into a central vessel."""
    components = []

    # Card frame
    components.append({
        "name": "FrameCard",
        "spline_type": "POLY",
        "thickness": 0.018,
        "color": "charcoal",
        "strokes": [rect_box(0.0, 0.55, 2.55, 1.85)],
        "animation": {"type": "draw_stroke_progressive", "start_offset": 0, "duration": 10},
    })

    # Central Reaction Vessel (Cauldron / Beaker / Crucible) at (0.0, 0.28)
    vessel = [
        [(-0.55, 0.50), (-0.60, 0.12), (0.0, -0.05), (0.60, 0.12), (0.55, 0.50)],
        [(-0.62, 0.50), (0.62, 0.50)],
    ]
    components.append({
        "name": "ReactionVessel",
        "spline_type": "BEZIER",
        "thickness": 0.040,
        "color": "charcoal",
        "strokes": vessel,
        "animation": {"type": "draw_stroke_progressive", "start_offset": 0, "duration": 14},
    })

    # Ingredient 1 (Left - e.g. Volcanic Ash): Triangular flask / volcanic silhouette
    ing1 = [
        [(-0.75, 1.25), (-0.95, 0.85), (-0.55, 0.85), (-0.75, 1.25)],
    ]
    components.append({
        "name": "Ingredient1_Source",
        "spline_type": "BEZIER",
        "thickness": 0.036,
        "color": "red",
        "strokes": ing1,
        "animation": {"type": "draw_stroke_progressive", "start_offset": 4, "duration": 12},
    })

    # Ingredient 1 Pour Arc Trajectory into vessel
    arc1 = [bezier_arc((-0.75, 0.85), (-0.60, 0.55), (-0.25, 0.35))]
    components.append({
        "name": "Ing1_PourArc",
        "spline_type": "BEZIER",
        "thickness": 0.034,
        "color": "red",
        "strokes": arc1,
        "animation": {"type": "pour_along_arc", "start_offset": 10, "duration": 20},
    })

    # Ingredient 2 (Center - Quicklime / Spark Minerals): Hexagonal crystal clasts
    ing2 = [
        bezier_circle(0.0, 1.25, 0.20, 6),
        [(-0.08, 1.25), (0.08, 1.25)],
    ]
    components.append({
        "name": "Ingredient2_Source",
        "spline_type": "BEZIER",
        "thickness": 0.036,
        "color": "gold",
        "strokes": ing2,
        "animation": {"type": "draw_stroke_progressive", "start_offset": 6, "duration": 12},
    })

    # Ingredient 2 Pour Line into vessel
    arc2 = [[(0.0, 1.05), (0.0, 0.40)]]
    components.append({
        "name": "Ing2_PourStream",
        "spline_type": "BEZIER",
        "thickness": 0.034,
        "color": "gold",
        "strokes": arc2,
        "animation": {"type": "pour_along_arc", "start_offset": 12, "duration": 20},
    })

    # Ingredient 3 (Right - Seawater / Catalyst): Wavy brine droplet
    ing3 = [
        bezier_wave(0.55, 0.95, 1.15, 0.08, 2.0),
        bezier_circle(0.75, 0.95, 0.18, 16),
    ]
    components.append({
        "name": "Ingredient3_Source",
        "spline_type": "BEZIER",
        "thickness": 0.036,
        "color": "blue",
        "strokes": ing3,
        "animation": {"type": "draw_stroke_progressive", "start_offset": 8, "duration": 12},
    })

    # Ingredient 3 Pour Arc into vessel
    arc3 = [bezier_arc((0.75, 0.85), (0.60, 0.55), (0.25, 0.35))]
    components.append({
        "name": "Ing3_PourArc",
        "spline_type": "BEZIER",
        "thickness": 0.034,
        "color": "blue",
        "strokes": arc3,
        "animation": {"type": "pour_along_arc", "start_offset": 14, "duration": 20},
    })

    # Rising Heat / Reaction Steam Waves from vessel
    steam = [
        bezier_wave(-0.30, 0.30, 0.65, 0.07, 2.5),
        bezier_wave(-0.25, 0.25, 0.80, 0.08, 2.5),
    ]
    components.append({
        "name": "ReactionSteam",
        "spline_type": "BEZIER",
        "thickness": 0.030,
        "color": "green",
        "strokes": steam,
        "animation": {"type": "flow_through_channel", "start_offset": 18, "duration": 22},
    })

    return components


def build_micro_cross_section_components(labels: Dict[str, str]) -> List[Dict[str, Any]]:
    """Builds magnifying glass zooming into an internal porous cross-section channel."""
    components = []

    components.append({
        "name": "FrameCard",
        "spline_type": "POLY",
        "thickness": 0.018,
        "color": "charcoal",
        "strokes": [rect_box(0.0, 0.55, 2.55, 1.85)],
        "animation": {"type": "draw_stroke_progressive", "start_offset": 0, "duration": 10},
    })

    # Magnifying Glass Outer Rim & Handle
    glass_rim = [
        bezier_circle(0.0, 0.60, 0.78, 28),
        bezier_circle(0.0, 0.60, 0.86, 28),
        [(0.58, 0.05), (1.02, -0.38)],  # Handle
    ]
    components.append({
        "name": "MagnifyingLens",
        "spline_type": "BEZIER",
        "thickness": 0.040,
        "color": "blue",
        "strokes": glass_rim,
        "animation": {"type": "draw_stroke_progressive", "start_offset": 0, "duration": 16},
    })

    # Internal porous rock channel walls
    channel_walls = [
        [(-0.65, 1.05), (-0.35, 0.80), (-0.55, 0.45), (-0.25, 0.15)],
        [(0.25, 1.05), (0.55, 0.80), (0.35, 0.45), (0.65, 0.15)],
    ]
    components.append({
        "name": "PoreChannelWalls",
        "spline_type": "BEZIER",
        "thickness": 0.038,
        "color": "charcoal",
        "strokes": channel_walls,
        "animation": {"type": "draw_stroke_progressive", "start_offset": 6, "duration": 15},
    })

    # Infiltrating Fluid / Energy Stream traveling down the channel
    stream = [
        bezier_arc((-0.20, 1.15), (0.10, 0.70), (-0.05, 0.20)),
    ]
    components.append({
        "name": "InfiltratingFluid",
        "spline_type": "BEZIER",
        "thickness": 0.042,
        "color": "blue",
        "strokes": stream,
        "animation": {"type": "flow_through_channel", "start_offset": 12, "duration": 22},
    })

    # 3 Glowing Reaction Nodes lighting up on contact
    nodes = [
        bezier_circle(-0.15, 0.78, 0.14, 12),
        bezier_circle(0.20, 0.52, 0.16, 12),
        bezier_circle(-0.02, 0.25, 0.15, 12),
    ]
    components.append({
        "name": "ReactionNodes",
        "spline_type": "BEZIER",
        "thickness": 0.038,
        "color": "gold",
        "strokes": nodes,
        "animation": {"type": "draw_stroke_progressive", "start_offset": 16, "duration": 18},
    })

    return components


def build_lattice_bond_growth_components(labels: Dict[str, str]) -> List[Dict[str, Any]]:
    """Builds crystal lattice needle bridges sprouting across a structural void and locking shut."""
    components = []

    components.append({
        "name": "FrameCard",
        "spline_type": "POLY",
        "thickness": 0.018,
        "color": "charcoal",
        "strokes": [rect_box(0.0, 0.55, 2.55, 1.85)],
        "animation": {"type": "draw_stroke_progressive", "start_offset": 0, "duration": 10},
    })

    # Opposing Structural Crack Walls (Left: x=-0.75, Right: x=+0.75)
    walls = [
        [(-0.85, 1.25), (-0.70, 0.55), (-0.85, -0.15)],
        [(0.85, 1.25), (0.70, 0.55), (0.85, -0.15)],
    ]
    components.append({
        "name": "VoidWalls",
        "spline_type": "BEZIER",
        "thickness": 0.044,
        "color": "charcoal",
        "strokes": walls,
        "animation": {"type": "draw_stroke_progressive", "start_offset": 0, "duration": 12},
    })

    # Interlocking Crystal Needles sprouting from left and right
    needles_left = [
        [(-0.70, 0.95), (-0.10, 0.75)],
        [(-0.70, 0.55), (-0.05, 0.55)],
        [(-0.70, 0.15), (-0.12, 0.35)],
    ]
    needles_right = [
        [(0.70, 0.95), (0.10, 0.75)],
        [(0.70, 0.55), (0.05, 0.55)],
        [(0.70, 0.15), (0.12, 0.35)],
    ]
    components.append({
        "name": "CrystalNeedles_Left",
        "spline_type": "BEZIER",
        "thickness": 0.038,
        "color": "green",
        "strokes": needles_left,
        "animation": {"type": "grow_and_interlock", "start_offset": 8, "duration": 22},
    })
    components.append({
        "name": "CrystalNeedles_Right",
        "spline_type": "BEZIER",
        "thickness": 0.038,
        "color": "green",
        "strokes": needles_right,
        "animation": {"type": "grow_and_interlock", "start_offset": 8, "duration": 22},
    })

    # Central Cross-Lattice Molecular Interlock Nodes
    interlock = [
        bezier_circle(0.0, 0.75, 0.15, 6),
        bezier_circle(0.0, 0.55, 0.17, 6),
        bezier_circle(0.0, 0.35, 0.15, 6),
        [(-0.35, 0.55), (0.35, 0.55)],
    ]
    components.append({
        "name": "MolecularBonds",
        "spline_type": "BEZIER",
        "thickness": 0.036,
        "color": "gold",
        "strokes": interlock,
        "animation": {"type": "grow_and_interlock", "start_offset": 16, "duration": 20},
    })

    return components


def build_structural_load_arch_components(labels: Dict[str, str]) -> List[Dict[str, Any]]:
    """Builds Roman semicircular stone arch with locking keystone and load distribution vectors."""
    components = []

    components.append({
        "name": "FrameCard",
        "spline_type": "POLY",
        "thickness": 0.018,
        "color": "charcoal",
        "strokes": [rect_box(0.0, 0.55, 2.55, 1.85)],
        "animation": {"type": "draw_stroke_progressive", "start_offset": 0, "duration": 10},
    })

    # Arch masonry stones
    arch = [
        bezier_circle(0.0, 0.30, 0.88, 16),
        bezier_circle(0.0, 0.30, 0.52, 16),
        [(-0.95, 0.30), (0.95, 0.30)],
    ]
    components.append({
        "name": "ArchRing",
        "spline_type": "BEZIER",
        "thickness": 0.038,
        "color": "blue",
        "strokes": arch,
        "animation": {"type": "draw_stroke_progressive", "start_offset": 0, "duration": 14},
    })

    # Locking Keystone dropping into the crown
    keystone = [
        rect_box(0.0, 1.02, 0.36, 0.35),
        [(-0.45, 1.35), (0.0, 1.20), (0.45, 1.35)],
    ]
    components.append({
        "name": "Keystone",
        "spline_type": "POLY",
        "thickness": 0.040,
        "color": "gold",
        "strokes": keystone,
        "animation": {"type": "draw_stroke_progressive", "start_offset": 6, "duration": 16},
    })

    # Load Distribution Force Vectors spreading outward into piers
    load_vectors = [
        [(0.0, 1.38), (0.0, 1.20)],
        [(-0.25, 0.95), (-0.75, 0.45)],
        [(0.25, 0.95), (0.75, 0.45)],
    ]
    components.append({
        "name": "ForceVectors",
        "spline_type": "BEZIER",
        "thickness": 0.038,
        "color": "green",
        "strokes": load_vectors,
        "animation": {"type": "draw_stroke_progressive", "start_offset": 12, "duration": 20},
    })

    return components


def build_vault_heist_bypass_components(labels: Dict[str, str]) -> List[Dict[str, Any]]:
    """Builds high-security vault door with laser grid, thermal sensor, and rotating unlock wheel."""
    components = []

    components.append({
        "name": "FrameCard",
        "spline_type": "POLY",
        "thickness": 0.018,
        "color": "charcoal",
        "strokes": [rect_box(0.0, 0.55, 2.55, 1.85)],
        "animation": {"type": "draw_stroke_progressive", "start_offset": 0, "duration": 10},
    })

    # Massive Vault Door Rings
    vault = [
        bezier_circle(0.0, 0.55, 0.85, 24),
        bezier_circle(0.0, 0.55, 0.65, 24),
    ]
    components.append({
        "name": "VaultDoor",
        "spline_type": "BEZIER",
        "thickness": 0.042,
        "color": "charcoal",
        "strokes": vault,
        "animation": {"type": "draw_stroke_progressive", "start_offset": 0, "duration": 14},
    })

    # Rotating 4-Spoke Wheel & Hub
    wheel = [
        bezier_circle(0.0, 0.55, 0.22, 16),
        [(-0.45, 0.55), (0.45, 0.55)],
        [(0.0, 0.10), (0.0, 1.00)],
    ]
    components.append({
        "name": "VaultWheel",
        "spline_type": "POLY",
        "thickness": 0.038,
        "color": "gold",
        "strokes": wheel,
        "animation": {"type": "draw_stroke_progressive", "start_offset": 6, "duration": 18},
    })

    # Security Laser Cones (Tripping Grid)
    lasers = [
        [(-0.85, 1.25), (0.0, 0.55)],
        [(0.85, 1.25), (0.0, 0.55)],
        [(-0.65, -0.05), (0.0, 0.55)],
    ]
    components.append({
        "name": "SecurityLasers",
        "spline_type": "BEZIER",
        "thickness": 0.034,
        "color": "red",
        "strokes": lasers,
        "animation": {"type": "draw_stroke_progressive", "start_offset": 10, "duration": 18},
    })

    # Bypassed / Insulating Shield Cloud blocking laser
    shield = [
        bezier_circle(-0.42, 0.90, 0.20, 16),
        bezier_circle(-0.42, 0.90, 0.28, 16),
    ]
    components.append({
        "name": "BypassShield",
        "spline_type": "BEZIER",
        "thickness": 0.036,
        "color": "green",
        "strokes": shield,
        "animation": {"type": "draw_stroke_progressive", "start_offset": 16, "duration": 18},
    })

    return components


def build_vacuum_gravity_drop_components(labels: Dict[str, str]) -> List[Dict[str, Any]]:
    """Builds tall glass vacuum bell jar with bowling ball and feather dropping together."""
    components = []

    components.append({
        "name": "FrameCard",
        "spline_type": "POLY",
        "thickness": 0.018,
        "color": "charcoal",
        "strokes": [rect_box(0.0, 0.55, 2.55, 1.85)],
        "animation": {"type": "draw_stroke_progressive", "start_offset": 0, "duration": 10},
    })

    # Glass Bell Jar Dome & Base
    bell_jar = [
        [(-0.65, 0.05), (-0.65, 0.95), (0.0, 1.35), (0.65, 0.95), (0.65, 0.05)],
        [(-0.85, 0.05), (0.85, 0.05)],
        bezier_circle(0.0, 1.35, 0.10, 8),  # Top valve
    ]
    components.append({
        "name": "VacuumChamber",
        "spline_type": "BEZIER",
        "thickness": 0.038,
        "color": "blue",
        "strokes": bell_jar,
        "animation": {"type": "draw_stroke_progressive", "start_offset": 0, "duration": 14},
    })

    # Bowling Ball (Left: x = -0.30)
    ball = [
        bezier_circle(-0.30, 0.90, 0.18, 16),
        bezier_circle(-0.35, 0.94, 0.04, 8),
        bezier_circle(-0.27, 0.95, 0.04, 8),
        bezier_circle(-0.31, 0.88, 0.04, 8),
    ]
    components.append({
        "name": "BowlingBall",
        "spline_type": "BEZIER",
        "thickness": 0.038,
        "color": "charcoal",
        "strokes": ball,
        "animation": {"type": "draw_stroke_progressive", "start_offset": 6, "duration": 16},
    })

    # Curved Feather (Right: x = +0.30)
    feather = [
        bezier_arc((0.30, 1.05), (0.35, 0.85), (0.30, 0.65)),
        bezier_wave(0.20, 0.40, 0.92, 0.05, 3.0),
        bezier_wave(0.22, 0.38, 0.78, 0.05, 3.0),
    ]
    components.append({
        "name": "Feather",
        "spline_type": "BEZIER",
        "thickness": 0.034,
        "color": "gold",
        "strokes": feather,
        "animation": {"type": "draw_stroke_progressive", "start_offset": 6, "duration": 16},
    })

    # Equal Fall Gravitational Trajectory Indicators
    fall_lines = [
        [(-0.30, 0.68), (-0.30, 0.15)],
        [(0.30, 0.68), (0.30, 0.15)],
    ]
    components.append({
        "name": "EqualFallPaths",
        "spline_type": "BEZIER",
        "thickness": 0.036,
        "color": "green",
        "strokes": fall_lines,
        "animation": {"type": "draw_stroke_progressive", "start_offset": 14, "duration": 20},
    })

    return components


def build_brain_psychology_pathway_components(labels: Dict[str, str]) -> List[Dict[str, Any]]:
    """Builds curved profile head & brain silhouette with glowing neural impulse pathways."""
    components = []

    components.append({
        "name": "FrameCard",
        "spline_type": "POLY",
        "thickness": 0.018,
        "color": "charcoal",
        "strokes": [rect_box(0.0, 0.55, 2.55, 1.85)],
        "animation": {"type": "draw_stroke_progressive", "start_offset": 0, "duration": 10},
    })

    # Side-Profile Head Silhouette
    profile = [
        [
            (-0.35, 1.30),
            (0.15, 1.25),
            (0.45, 0.85),
            (0.55, 0.65),  # Nose
            (0.48, 0.52),  # Lip
            (0.52, 0.42),  # Chin
            (0.35, 0.25),  # Jaw
            (0.30, -0.05), # Neck
        ]
    ]
    components.append({
        "name": "HeadProfile",
        "spline_type": "BEZIER",
        "thickness": 0.036,
        "color": "charcoal",
        "strokes": profile,
        "animation": {"type": "draw_stroke_progressive", "start_offset": 0, "duration": 14},
    })

    # Curved Brain Cortex with Folds
    cortex = [
        bezier_circle(-0.05, 0.78, 0.42, 20),
        bezier_wave(-0.30, 0.20, 0.85, 0.07, 2.0),
        bezier_wave(-0.25, 0.15, 0.70, 0.06, 2.0),
    ]
    components.append({
        "name": "BrainCortex",
        "spline_type": "BEZIER",
        "thickness": 0.038,
        "color": "red",
        "strokes": cortex,
        "animation": {"type": "draw_stroke_progressive", "start_offset": 4, "duration": 16},
    })

    # Glowing Neural Synapse Pathways firing toward frontal lobe
    synapses = [
        bezier_arc((-0.15, 0.75), (0.15, 0.85), (0.42, 0.70)),
        bezier_circle(0.42, 0.70, 0.12, 10),
    ]
    components.append({
        "name": "NeuralSynapses",
        "spline_type": "BEZIER",
        "thickness": 0.040,
        "color": "gold",
        "strokes": synapses,
        "animation": {"type": "flow_through_channel", "start_offset": 10, "duration": 22},
    })

    # Optical / Reward Target
    target = [
        bezier_circle(0.78, 0.70, 0.18, 16),
        bezier_circle(0.78, 0.70, 0.08, 16),
    ]
    components.append({
        "name": "RewardTarget",
        "spline_type": "BEZIER",
        "thickness": 0.038,
        "color": "green",
        "strokes": target,
        "animation": {"type": "draw_stroke_progressive", "start_offset": 14, "duration": 18},
    })

    return components


ARCHETYPE_BUILDERS = {
    "comparison_split": build_comparison_split_components,
    "recipe_combine": build_recipe_combine_components,
    "micro_cross_section": build_micro_cross_section_components,
    "lattice_bond_growth": build_lattice_bond_growth_components,
    "structural_load_arch": build_structural_load_arch_components,
    "vault_heist_bypass": build_vault_heist_bypass_components,
    "vacuum_gravity_drop": build_vacuum_gravity_drop_components,
    "brain_psychology_pathway": build_brain_psychology_pathway_components,
}


# =====================================================================
# MAIN SCENE CHOREOGRAPHER CLASS
# =====================================================================

class SceneChoreographer:
    """Analyzes scripts, generates 5-Act visual blueprints, and formats Bezier geometry."""

    def __init__(self, fps: int = 30):
        self.fps = fps

    def choreograph_project(
        self,
        project_dir: str,
        script_text: str,
        words_json_path: str,
        category: str = "STEM",
        duration_override: Optional[float] = None,
    ) -> Dict[str, Any]:
        """Creates a complete 5-act visual blueprint with Bezier splines and labels."""
        os.makedirs(project_dir, exist_ok=True)

        # 1. Parse words & total duration
        words: List[Dict[str, Any]] = []
        if os.path.exists(words_json_path):
            try:
                with open(words_json_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    words = data if isinstance(data, list) else data.get("words", [])
            except Exception:
                words = []

        total_duration = duration_override or 65.0
        if words:
            last_end = float(words[-1].get("end", total_duration))
            total_duration = max(last_end + 0.5, 10.0)

        # 2. Divide script text into 5 narrative acts
        sentences = [s.strip() for s in re.split(r"(?<=[.!?])\s+", script_text) if s.strip()]
        if len(sentences) < 5:
            # Subdivide sentences if script has fewer than 5 sentences
            words_all = script_text.split()
            chunk_size = max(1, len(words_all) // 5)
            sentences = [" ".join(words_all[i * chunk_size : (i + 1) * chunk_size]) for i in range(5)]

        act_ratios = [0.0, 0.16, 0.36, 0.58, 0.80]
        act_names = [
            "Act1_Hook_Comparison",
            "Act2_Recipe_Combine",
            "Act3_Micro_Infiltration",
            "Act4_Lattice_Action",
            "Act5_Resolution_Arch",
        ]

        # Spatial zones on continuous 2D paper canvas
        zones = [
            (0.0, 0.0),
            (4.2, 0.35),
            (8.4, -0.25),
            (12.6, 0.30),
            (16.8, 0.0),
        ]

        acts_blueprint = []
        for i in range(5):
            start_s = round(total_duration * act_ratios[i], 2)
            end_s = round(total_duration * act_ratios[i + 1], 2) if i < 4 else total_duration
            start_frame = 1 if i == 0 else max(2, int(round(start_s * self.fps)))
            end_frame = max(start_frame + 20, int(round(end_s * self.fps)))

            act_text = sentences[min(i, len(sentences) - 1)]
            archetype = classify_act_archetype(act_text, act_index=i, category=category)
            labels = extract_salient_labels(act_text, archetype)

            builder = ARCHETYPE_BUILDERS.get(archetype, build_comparison_split_components)
            components = builder(labels)

            acts_blueprint.append({
                "act_index": i,
                "act_name": act_names[i],
                "archetype": archetype,
                "act_text_snippet": act_text[:90],
                "start_frame": start_frame,
                "end_frame": end_frame,
                "draw_frames": min(42, max(15, int((end_frame - start_frame) * 0.25))),
                "zone_coords": zones[i],
                "labels": labels,
                "components": components,
            })

        blueprint = {
            "category": category,
            "total_duration": total_duration,
            "total_frames": int(math.ceil(total_duration * self.fps)),
            "fps": self.fps,
            "canvas_zones": zones,
            "acts": acts_blueprint,
        }

        # Persist visual blueprint
        blueprint_path = os.path.join(project_dir, "visual_blueprint.json")
        with open(blueprint_path, "w", encoding="utf-8") as f:
            json.dump(blueprint, f, indent=2)

        logger.info("Universal visual blueprint generated: %s (%d acts)", blueprint_path, len(acts_blueprint))
        return blueprint
