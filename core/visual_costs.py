"""Per-short cost estimates for the picture modes.

Prices are Google's published Gemini API rates (checked October 2026):

- Gemini 2.5 Flash Image: $0.039 per image up to 1024px.
- Gemini Omni Flash: about $0.10 per second at 720p
  (5,792 video tokens per second at $17.50 per million).
- Veo 3.1 Fast, with audio: $0.12 per second at 1080p, $0.10 at 720p.
- Veo 3.1 Lite, with audio: $0.08 per second at 1080p, $0.05 at 720p.
- Veo 3.1 Standard, with audio: $0.40 per second at 1080p.
  The old "$15–$20" label matches this standard tier for roughly 40–50
  generated seconds. The code path calls Fast or Omni, not Standard.
- Pexels and Pixabay: $0. Ken Burns / pan-zoom is local.

The storyboard asks for 6 clips. Veo is fixed at 8 seconds each, so a
60-second edit bills about 48 generated seconds and then stretches them
across the voiceover. It does not bill 60 seconds of model time.
"""

from __future__ import annotations

from typing import Dict

GEMINI_FLASH_IMAGE_USD = 0.039
OMNI_FLASH_USD_PER_SEC = 0.10
VEO_FAST_1080_USD_PER_SEC = 0.12
VEO_LITE_1080_USD_PER_SEC = 0.08
VEO_STANDARD_1080_USD_PER_SEC = 0.40

SCENE_COUNT = 6
GENERATED_CLIP_SECONDS = 8  # Veo duration_seconds in storyboard_engine
GENERATED_SECONDS = SCENE_COUNT * GENERATED_CLIP_SECONDS  # 48


def _money(value: float) -> float:
    return round(float(value), 2)


def estimate_short_cost(mode: str, scene_count: int = SCENE_COUNT) -> Dict[str, float]:
    """Return low / typical / high USD for one ~60 second short.

    ``low`` is the free-fallback or best stock match. ``typical`` is the
    expected STEM mix. ``high`` is every scene taking the paid path.
    """
    scenes = max(1, int(scene_count))
    image_cost = scenes * GEMINI_FLASH_IMAGE_USD
    generated = scenes * GENERATED_CLIP_SECONDS

    if mode == "hybrid_stock":
        # Niche mechanisms rarely have a real stock match. Two establishing
        # shots may hit; the rest become generated stills. Worst case, none hit.
        paid_scenes_typical = max(0, scenes - 2)
        return {
            "low": 0.0,
            "typical": _money(paid_scenes_typical * GEMINI_FLASH_IMAGE_USD),
            "high": _money(image_cost),
        }
    if mode == "image_motion":
        return {
            "low": 0.0,  # Pollinations / local card, no API key
            "typical": _money(image_cost),
            "high": _money(image_cost),
        }
    if mode == "veo_lite":
        video = generated * VEO_LITE_1080_USD_PER_SEC
        total = video + image_cost
        return {"low": _money(total), "typical": _money(total), "high": _money(total)}
    if mode == "generative_video":
        # Omni is tried first at ~$0.10/s. If it fails, Veo Fast is $0.12/s.
        # Both still generate a still first.
        low = generated * OMNI_FLASH_USD_PER_SEC + image_cost
        high = generated * VEO_FAST_1080_USD_PER_SEC + image_cost
        return {"low": _money(low), "typical": _money((low + high) / 2.0), "high": _money(high)}
    if mode == "veo_standard_reference":
        # Not a wired mode. Kept so the old $15–$20 checkbox can be compared.
        video = generated * VEO_STANDARD_1080_USD_PER_SEC
        total = video + image_cost
        return {"low": _money(total), "typical": _money(total), "high": _money(total)}
    raise KeyError(mode)


def cost_summary_line(mode: str) -> str:
    """One line for the studio combo tooltip."""
    est = estimate_short_cost(mode)
    if est["low"] == est["high"]:
        return f"about ${est['typical']:.2f} per 60s short"
    return f"about ${est['low']:.2f}–${est['high']:.2f} per 60s short (typical ${est['typical']:.2f})"


MODE_LABELS = {
    "hybrid_stock": "Hybrid — stock only when the mechanism matches, otherwise illustrated motion",
    "image_motion": "Illustrated motion — generated stills with Ken Burns / pan-zoom",
    "veo_lite": "Cheaper generative — Veo 3.1 Lite",
    "generative_video": "Generative video — Gemini Omni, then Veo 3.1 Fast",
}
