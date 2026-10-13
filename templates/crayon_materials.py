"""Blender Crayon Materials and Shader Definitions.

Provides procedural shader setups for hand-drawn wax crayon strokes:
- Organic roughness and micro-bump displacement
- Crayon pigment color palettes (vibrant primary & secondary colors)
- Paper tooth scattering and wax edge breakup
"""

# Crayon Core Palette (Hex values optimized for dark and craft paper backgrounds)
CRAYON_PALETTE = {
    "crimson_red": {"rgb": (0.92, 0.18, 0.24), "roughness": 0.85},
    "cobalt_blue": {"rgb": (0.12, 0.45, 0.95), "roughness": 0.82},
    "sun_yellow": {"rgb": (0.98, 0.82, 0.08), "roughness": 0.90},
    "emerald_green": {"rgb": (0.15, 0.75, 0.38), "roughness": 0.84},
    "mandarin_orange": {"rgb": (0.96, 0.52, 0.11), "roughness": 0.86},
    "violet_purple": {"rgb": (0.58, 0.22, 0.88), "roughness": 0.88},
    "chalk_white": {"rgb": (0.95, 0.96, 0.94), "roughness": 0.95},
    "charcoal_black": {"rgb": (0.10, 0.10, 0.11), "roughness": 0.92},
}


def build_crayon_shader_nodes(material_name: str, color_key: str = "sun_yellow"):
    """Shader node setup descriptor for Blender Python scripting (bpy).

    Creates a Principled BSDF with Voronoi texture noise displacement
    simulating the textured, wax-impregnated stroke on paper fibers.
    """
    color_info = CRAYON_PALETTE.get(color_key, CRAYON_PALETTE["sun_yellow"])
    return {
        "material_name": material_name,
        "base_color": color_info["rgb"] + (1.0,),
        "roughness": color_info["roughness"],
        "specular_ior_level": 0.25,
        "displacement_scale": 0.015,
        "voronoi_scale": 120.0,
    }
