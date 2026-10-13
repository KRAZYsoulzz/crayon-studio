"""In-App AI Assistant for Script & Hook Revisions.

Provides intelligent, topic-aware script alterations:
- High-friction viral hook injection
- Topic-aware script drafting addressing confusion points & content gaps
- 155-170 word target length (62-68 seconds at 1.05x speed)
- Seamless audio loop closures (ending sentence loops into opening hook)
- TikTok Shop organic product bridge integration
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
    topic: str = "",
) -> str:
    """Apply intelligent script revision based on prompt instruction and topic context.

    Args:
        script_text: Existing script content. If empty, generates a viral 155-170 word script.
        prompt: User's revision command (e.g., 'Make hook punchier', 'Address confusion...').
        category: Niche category (STEM, Escape/Heist, Architecture, Psychology).
        target_duration: Desired video duration in seconds.
        tiktok_product: Optional product to weave into the narrative.
        topic: Selected trend topic from Tab 1 to dynamically weave into the script.

    Returns:
        Revised script string with viral pacing and seamless loop structure.
    """
    clean_prompt = prompt.strip().lower()
    text = script_text.strip()
    lines = [line.strip() for line in text.split("\n") if line.strip()]

    # If script is completely empty, generate a tailored 155-170 word script
    if not text:
        if topic:
            clean_topic = topic.strip()
            confusion_match = re.search(r"confusion:\s*([^.|?]+)", prompt, re.IGNORECASE)
            gap_match = re.search(r"gap:\s*([^.|!]+)", prompt, re.IGNORECASE)
            confusion = confusion_match.group(1).strip() if confusion_match else "why this works under extreme load"
            gap = gap_match.group(1).strip() if gap_match else "the hidden stress distribution"

            if len(confusion.split()) > 6:
                confusion = " ".join(confusion.split()[:6])
            if len(gap.split()) > 6:
                gap = " ".join(gap.split()[:6])

            hook = f"Stop scrolling, because {clean_topic} is something almost everyone gets wrong when they first see it."
            core = (
                f" The primary question that puzzles most viewers comes down to one fundamental mystery: {confusion}? "
                f"When researchers placed the subject under high-speed diagnostic cameras, they uncovered an astonishing physical mechanism at work. "
                f"The external forces do not travel in a simple straight line; instead, microscopic internal geometry actively redirects the shear stress before microcracks can propagate. "
                f"Most viral videos completely overlook {gap}, but that exact detail is the secret reason the entire framework survives without catastrophic failure. "
                f"By dissipating kinetic shock across an interconnected geometric lattice, the material actually gains structural rigidity during initial pressure waves. "
                f"Every test demonstrates that true physical stability is achieved through dynamic energy distribution rather than brittle resistance."
            )
            product_bridge = ""
            if tiktok_product and "none" not in tiktok_product.lower():
                product_bridge = (
                    f" If you want to sketch out the structural engineering of {clean_topic} yourself, "
                    f"check out the {tiktok_product} linked down below in the showcase."
                )

            closing = (
                f" Once you understand how these hidden forces balance, you will never view modern mechanics the same way again, "
                f"especially when considering why:"
            )

            combined = (hook + core + product_bridge + closing).strip()
            words = combined.split()
            if len(words) < 155:
                extra = " Scientists spent years conducting stress tests to verify that every single load vector remains balanced in real-world environments."
                combined = (hook + core + extra + product_bridge + closing).strip()
                words = combined.split()

            if len(words) > 170:
                words = words[:165]
                result = " ".join(words).rstrip(".,;:!") + ", especially when considering why:"
            else:
                result = " ".join(words)
            return result

        # Category-specific baseline templates (Guaranteed 155-170 words each with seamless loop)
        if category == "Escape/Heist":
            return (
                "In 2003, a crew of thieves bypassed an impenetrable subterranean bank vault and escaped with one hundred million dollars without tripping a single alarm. "
                "The vault was fortified behind a three-ton steel door protected by a combination dial, a physical key, an encrypted magnetic field detector, infrared motion sensors, and a seismic sensor tuned to detect footsteps. "
                "On paper, breaching it was completely impossible. But the mastermind spent thirty months analyzing the blueprints and discovered an astonishing flaw in the physics of the sensors. "
                "The high-end infrared detectors monitored ambient heat differentials rather than solid objects. "
                "By coating the sensors with a thin layer of ordinary women's hairspray, they temporarily insulated the thermal optics, blinding the alarm system. "
                "Next, they placed a magnetic bypass across the door contacts to simulate a closed circuit before swinging the vault wide open. "
                "Security systems are designed by humans, meaning every barrier contains a hidden structural vulnerability waiting for someone who studies:"
            )
        elif category == "Architecture":
            return (
                "Why can ancient Roman harbors withstand two thousand years of crashing ocean waves, while modern concrete structures crack and crumble after fifty years? "
                "Scientists finally unlocked this mystery using electron microscopes and high-energy X-ray diffraction. "
                "The Romans didn't just mix sand and gravel; they forged their concrete using reactive volcanic ash called pozzolana, slaked lime, and seawater. "
                "When saltwater infiltrates the microscopic pores, it doesn't degrade the internal framework. "
                "Instead, it dissolves the volcanic ash and triggers an active hydrothermal reaction. "
                "This chemical reaction precipitates interlocking crystals of a rare mineral called aluminous tobermorite. "
                "These microscopic crystals expand into microscopic voids like biological bone tissue, sealing microcracks before structural damage can spread. "
                "Instead of eroding the seawall, the immense hydraulic pressure of the ocean actually cements the Roman concrete tighter with every single passing decade. "
                "Modern architects are now racing to replicate this self-healing chemistry for new deep-sea mega-structures, but it all begins by questioning:"
            )
        elif category == "Psychology":
            return (
                "There is a fascinating glitch wired into your subconscious mind that casinos and con artists exploit every single day to influence your behavior. "
                "Cognitive psychologists call this cognitive blindspot the 'Illusion of Control'. "
                "When gamblers throw dice across a craps table, high-speed cameras show they instinctively roll with gentle finesse when they need low numbers, and throw with aggressive force when they need high numbers. "
                "Logically, physics and probability do not care about arm speed once the dice leave your fingertips. "
                "Yet human brains crave pattern recognition so desperately that we trick ourselves into believing our personal intention dictates purely random events. "
                "From pressing elevator buttons multiple times to superstitious game-day rituals, we manufacture false agency to shield ourselves from existential chaos. "
                "The moment you recognize this psychological blindspot, you begin catching yourself doing it constantly throughout your daily life, especially when you remember that deep down, our daily choices are driven by the fact that:"
            )
        else:  # STEM
            return (
                "If you drop a heavy bowling ball and a lightweight feather inside a giant vacuum chamber, they hit the floor at the exact same millisecond. "
                "Galileo formulated this counterintuitive law of physics over four hundred years ago, but watching it unfold before your eyes looks like an outright glitch in our physical simulation. "
                "Under ordinary room conditions, aerodynamic air resistance pushes upward against the feather's broad surface, causing it to flutter and drift downward slowly. "
                "But once you extract all the air molecules and drop them in a complete vacuum, atmospheric drag drops to zero. "
                "Without air molecules pushing back, planetary gravity accelerates every single object at the identical rate: nine point eight meters per second squared, regardless of its mass, size, or material composition. "
                "The universe proves that gravity doesn't accelerate weight; it curves spacetime itself, pulling massive steel and fragile feathers with the exact same celestial urgency. "
                "Whenever people see physics stripped down to its raw mechanics, they find themselves questioning:"
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
        if lines:
            lines[-1] = lines[-1] + " And that is why this changes everything."

    result = " ".join(lines)
    logger.info("Script modified with prompt: '%s'", prompt)
    return result
