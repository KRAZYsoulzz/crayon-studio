"""In-App AI Assistant for Script & Hook Revisions.

Provides intelligent script alterations:
- High-friction viral hook injection
- Curiosity gap tightening
- TikTok Shop organic product bridge integration
- Pacing adjustments for target duration (61s-75s)
"""

from __future__ import annotations

import logging
import re
from typing import Optional

logger = logging.getLogger("crayon_studio.ai_modifier")


def modify_script(
    script_text: str,
    prompt: str,
    category: str = "STEM",
    target_duration: int = 65,
    tiktok_product: Optional[str] = None,
) -> str:
    """Apply intelligent script revision based on prompt instruction.

    Args:
        script_text: Existing script content.
        prompt: User's revision command (e.g., 'Make hook punchier', 'Add curiosity gap').
        category: Niche category (STEM, Escape/Heist, Architecture, Psychology).
        target_duration: Desired video duration in seconds.
        tiktok_product: Optional product to weave into the narrative.

    Returns:
        Revised script string with viral structure.
    """
    clean_prompt = prompt.strip().lower()
    text = script_text.strip()

    lines = [line.strip() for line in text.split("\n") if line.strip()]

    # If script is completely empty, generate a tailored viral template
    if not text:
        target_words = int(target_duration * 2.3)
        if category == "Escape/Heist":
            return (
                "In 2003, thieves bypassed a ten-tier security vault without tripping a single alarm. "
                "The safe was guarded by magnetic field detectors, infrared beams, and a seismic sensor "
                "calibrated to detect a heartbeat. So how did they walk out with one hundred million dollars? "
                "They realized something the engineers overlooked: the thermal sensors only measured body heat. "
                "By using standard hairspray, they temporarily insulated the thermal sensors before opening the door. "
                "Every lock has a design flaw if you look closely enough."
            )
        elif category == "Architecture":
            return (
                "Why can ancient Roman harbors withstand two thousand years of crashing ocean waves, "
                "while modern concrete cracks after fifty years? "
                "Scientists cracked the secret using electron microscopes. The Romans mixed volcanic ash "
                "with slaked lime and seawater. When waves hit the concrete, it triggered a chemical reaction "
                "that grew interlocking mineral crystals called aluminous tobermorite. "
                "Instead of eroding the wall, the ocean was actually cementing it tighter every single day."
            )
        elif category == "Psychology":
            return (
                "There is a psychological glitch in your brain that con artists exploit every single day. "
                "It's called the 'Illusion of Control'. "
                "When people roll dice in a casino, they roll gently if they want low numbers, and throw with force "
                "if they want high numbers. Logically, physics doesn't care how hard you roll. But our brains "
                "desperately fabricate patterns to feel safe in chaos. Once you see this glitch, you notice it everywhere."
            )
        else:  # STEM
            return (
                "If you drop a bowling ball and a feather in a vacuum chamber, they hit the floor at the exact same millisecond. "
                "Galileo proved this in theory four hundred years ago, but seeing it in real life looks like a glitch in the simulation. "
                "Air resistance is the only reason the feather drifts slowly. Without air molecules pushing upward, gravity pulls "
                "every single kilogram with the identical acceleration: 9.8 meters per second squared. "
                "Matter doesn't care how heavy it is when falling through nothingness."
            )

    # 1. Modify Hook
    if "hook" in clean_prompt or "punchier" in clean_prompt or "start" in clean_prompt:
        hook_options = {
            "STEM": "Most people think physics makes sense until you show them this exact experiment.",
            "Escape/Heist": "This was called the most impenetrable vault on earth—until two guys walked in with a hairpin.",
            "Architecture": "Every skyscraper in Tokyo has a secret hidden inside that keeps it from snapping in an earthquake.",
            "Psychology": "Your brain is lying to you right now, and here is the exact optical proof.",
        }
        chosen_hook = hook_options.get(category, "Stop scrolling, because this is something 99% of people get wrong.")
        if lines:
            lines[0] = chosen_hook
        else:
            lines.append(chosen_hook)

    # 2. Add Curiosity Gap / Friction Trigger
    elif "curiosity" in clean_prompt or "friction" in clean_prompt or "gap" in clean_prompt:
        gap_insert = (
            " But here is the part that nobody talks about—and the reason scientists argued over this for twelve years."
        )
        if len(lines) > 1:
            lines.insert(1, gap_insert)
        else:
            lines.append(gap_insert)

    # 3. Add TikTok Shop Organic Bridge
    elif "product" in clean_prompt or "shop" in clean_prompt or "bridge" in clean_prompt or "monetize" in clean_prompt:
        product_name = tiktok_product or "drawing stylus & textured notebook"
        bridge = (
            f" If you want to sketch out mechanics like this yourself, I linked the exact {product_name} "
            f"down below in the showcase."
        )
        lines.append(bridge)

    # 4. Shorten or Expand for target duration
    elif "shorten" in clean_prompt or "compress" in clean_prompt or "faster" in clean_prompt:
        # Trim sentences
        combined = " ".join(lines)
        sentences = re.split(r"(?<=[.!?]) +", combined)
        target_count = max(4, int(len(sentences) * 0.75))
        lines = [sentences[i] for i in range(min(target_count, len(sentences)))]

    elif "expand" in clean_prompt or "longer" in clean_prompt or "60s" in clean_prompt or "detail" in clean_prompt:
        expansion = (
            " To understand why this works, take a look at the molecular cross-section. "
            "When the pressure wave travels from top to bottom, the force distribution spreads "
            "into a 45-degree cone instead of a straight line."
        )
        lines.insert(len(lines) // 2, expansion)

    else:
        # General enhancement / polish
        prefix = "Notice how "
        if lines:
            lines[-1] = lines[-1] + " And that is why this changes everything."

    result = " ".join(lines)
    logger.info("Script modified with prompt: '%s'", prompt)
    return result
