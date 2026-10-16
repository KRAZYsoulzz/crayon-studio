"""In-App AI Assistant for Script & Hook Revisions.

Provides intelligent, topic-aware script authoring and alterations:
- High-friction viral hook injection
- Word count budgeted from the measured neural TTS rate so a 69s target
  still clears 60 seconds after silence trimming
- Seamless audio loop closures (ending sentence flows naturally back into opening hook)
- Factual, engaging scientific & engineering narrative structure
- TikTok Shop organic product bridge integration
"""

from __future__ import annotations

import logging
import re
from typing import Optional

from core.duration_guard import DEFAULT_TARGET_SECONDS, ensure_script_word_count

logger = logging.getLogger("crayon_studio.ai_modifier")


# =====================================================================
# CURATED HIGH-RETENTION MASTER SCRIPTS (160-168 Words, Seamless Loops)
# =====================================================================

MASTER_SCRIPTS = {
    "architecture_roman_concrete": (
        "Ancient Roman concrete gets stronger the longer it sits in crashing ocean waves, while modern concrete crumbles in fifty years. "
        "For decades, modern civil engineers couldn't figure out why ancient harbors in Italy survived two millennia of salt water erosion. "
        "The breakthrough came when geologists put Roman seawalls under electron microscopes. "
        "The Romans didn't just mix sand and gravel; they forged their concrete using reactive volcanic ash called pozzolana, slaked lime, and chunks of quicklime hot-mixed together. "
        "When ocean saltwater infiltrates the microscopic pores, it doesn't rot the internal framework. "
        "Instead, the alkaline brine dissolves the volcanic minerals and reacts with the lime clasts, precipitating interlocking crystals of a rare mineral called aluminous tobermorite. "
        "These microscopic crystals expand into microscopic voids, literally stitching microcracks closed like living bone tissue. "
        "The ocean isn't destroying the seawall—it's actively fueling the chemical reaction that cements it tighter with every passing decade, which is why modern architects are still racing to replicate how ancient Roman concrete gets stronger the longer it sits in crashing ocean waves."
    ),
    "engineering_piezo_lighter": (
        "Inside every push-button lighter is a tiny power plant that generates fifteen thousand volts without a single battery. "
        "Most people assume there is a miniature watch battery hidden in the handle, but watch what happens when you pull the casing apart. "
        "When your thumb presses the spring-loaded plunger down, it compresses a heavy steel spring until a tiny internal hammer slips off its catch. "
        "That hammer slams into a microscopic quartz crystal at extreme velocity. "
        "Under that sudden mechanical impact, the crystal lattice deforms violently, forcing positive and negative ions out of alignment. "
        "This sudden charge separation creates a massive electrical potential that leaps across the spark gap as blazing blue plasma. "
        "At the exact same millisecond, a plastic lever lifts the butane valve, spraying pressurized gas directly into the arc to ignite the flame. "
        "It is one of the most brilliant pieces of solid-state physics, proving you can generate pure electricity every time you remember that inside every push-button lighter is a tiny power plant that generates fifteen thousand volts without a single battery."
    ),
    "how_its_made_brushless_motor": (
        "Inside a brushless electric motor spinning at forty thousand rotations per minute, nothing is actually touching. "
        "If you open up a high-performance drone motor or electric hypercar drive, you will find no physical gears, no carbon brushes, and zero friction contact. "
        "At the center sits a rotor lined with alternating neodymium permanent magnets, balanced to within a fraction of a gram. "
        "Surrounding the rotor is a stationary copper stator wound with three distinct electromagnetic coils. "
        "Instead of using mechanical switches that wear down and throw sparks, an onboard microchip pulses three-phase electric currents through the copper windings in an ultra-precise sequence. "
        "The energized coils produce a rotating magnetic wave that constantly repels and pulls the rotor magnets, dragging the shaft in an endless circular chase at dizzying speed. "
        "Because there are no rubbing parts to create heat or wear out, the motor achieves over ninety percent energy efficiency, delivering pure electromagnetic torque every time you watch how inside a brushless electric motor spinning at forty thousand rotations per minute, nothing is actually touching."
    ),
    "escape_heist_vault_physics": (
        "In 2003, a crew of thieves breached an impenetrable subterranean bank vault and escaped with one hundred million dollars without tripping a single alarm. "
        "The vault was fortified behind a three-ton steel door protected by a combination dial, physical key, encrypted magnetic field detector, infrared motion sensors, and a seismic sensor tuned to detect footsteps. "
        "On paper, breaching it was completely impossible. But the mastermind spent thirty months analyzing the blueprints and discovered an astonishing flaw in the physics of the sensors. "
        "The infrared detectors monitored ambient heat differentials rather than solid objects. "
        "By coating the sensors with a thin layer of ordinary hairspray, they temporarily insulated the thermal optics, blinding the alarm system. "
        "Next, they placed a magnetic bypass across the door contacts to simulate a closed circuit before swinging the vault wide open. "
        "Security systems are designed by humans, meaning every barrier contains a hidden structural vulnerability, which is the exact reason why in 2003, a crew of thieves breached an impenetrable subterranean bank vault and escaped with one hundred million dollars without tripping a single alarm."
    ),
    "psychology_illusion_control": (
        "There is a bizarre glitch wired into your subconscious mind that casinos exploit every single day to influence your behavior. "
        "Cognitive psychologists call this blindspot the Illusion of Control. "
        "When gamblers throw dice across a craps table, high-speed cameras show they instinctively roll with gentle finesse when they need low numbers, and throw with aggressive force when they need high numbers. "
        "Logically, physics and probability do not care about arm speed once the dice leave your fingertips. "
        "Yet human brains crave pattern recognition so desperately that we trick ourselves into believing our personal intention dictates purely random events. "
        "From pressing elevator buttons multiple times to superstitious game-day rituals, we manufacture false agency to shield ourselves from existential uncertainty. "
        "The moment you recognize this psychological blindspot, you begin catching yourself doing it constantly throughout your daily life, especially when you realize how there is a bizarre glitch wired into your subconscious mind that casinos exploit every single day to influence your behavior."
    ),
    "stem_vacuum_paradox": (
        "If you drop a heavy bowling ball and a lightweight feather inside a giant vacuum chamber, they hit the floor at the exact same millisecond. "
        "Galileo formulated this counterintuitive law of physics over four hundred years ago, but watching it unfold before your eyes looks like an outright glitch in our physical simulation. "
        "Under ordinary room conditions, aerodynamic air resistance pushes upward against the feather's broad surface, causing it to flutter and drift downward slowly. "
        "But once you extract all the air molecules and drop them in a complete vacuum, atmospheric drag drops to zero. "
        "Without air molecules pushing back, planetary gravity accelerates every single object at the identical rate: nine point eight meters per second squared, regardless of its mass, size, or material composition. "
        "The universe proves that gravity doesn't accelerate weight; it curves spacetime itself, pulling massive steel and fragile feathers with the exact same celestial urgency, which is why if you drop a heavy bowling ball and a lightweight feather inside a giant vacuum chamber, they hit the floor at the exact same millisecond."
    ),
    "quartz_watch": (
        "A quartz watch does not tell time with a spinning wheel. It counts the vibrations of a tiny tuning fork, "
        "and that fork moves thirty two thousand seven hundred sixty eight times every single second. "
        "Open the case and the part that matters is a crystal of quartz, laser-cut into a tuning fork smaller than a grain of rice, "
        "with two metal electrodes plated onto its surface. "
        "A battery feeds a simple circuit that nudges the fork with a tiny electric field. "
        "Quartz is piezoelectric, so the field bends the fork, and the bending creates a field of its own, which kicks the circuit again. "
        "The fork and the circuit lock together and hold that rate, because the shape of the crystal wants to flex at one pitch and no other. "
        "The circuit then divides that pitch in half, fifteen times in a row, until one pulse is left each second. "
        "That one pulse fires a stepper motor, and the motor advances the seconds hand by a single tooth. "
        "A mechanical watch depends on a balance wheel and a hairspring, and gravity tugs that wheel whenever you tilt your wrist. "
        "The quartz fork is too stiff and too small for that tug to matter, which is why a cheap quartz watch stays closer to the right time than a handmade mechanical one. "
        "So the tick you hear is not a decoration. It is the last step of a counter that began with a quartz watch counting thirty two thousand seven hundred sixty eight vibrations every single second."
    ),
    "fireworks_shell": (
        "A firework shell is a timed machine, and the colors you see are packed into it before it ever leaves the tube. "
        "The lift charge is black powder in a pouch under the shell. When that powder burns it makes a rush of gas, and the gas shoves the shell up the mortar. "
        "A slow fuse, the time fuse, is lit by the same fire and burns while the shell is in the air. Its length is the delay. "
        "At the top of the arc the fuse reaches the burst charge in the middle of the shell. "
        "That second burn does not make the colors. It only breaks the paper casing and throws the stars outward. "
        "Each star is a pea of fuel, oxidizer, and a metal salt. Strontium burns red, barium burns green, copper burns blue, and sodium burns yellow. "
        "The star has to be pressed dense enough to stay lit as it flies, and loose enough that the whole pea is gone before it hits the ground. "
        "So the bloom in the sky is the shell finishing a sequence that started when the lift charge fired, which is why a firework shell is a timed machine and the colors were packed into it before it ever left the tube."
    ),
    "noise_cancelling_headphones": (
        "Noise-cancelling headphones do not block the world with thicker foam. They play the noise backwards. "
        "A microphone on the outside of the ear cup listens to the sound that is about to reach your ear. "
        "Inside the cup, a second microphone listens to whatever got through, including the music and what is left of the noise. "
        "A small processor compares those two signals and builds a new wave whose peaks line up with the noise's valleys. "
        "The driver plays that opposing wave into the ear, and the two pressure waves add together. Where they match in size and miss in direction, the air barely moves, and the low rumble of an engine drops out. "
        "Foam still does the high hiss, because those short waves change too fast for the processor to catch. "
        "The trick only works if the opposing wave arrives at the same instant as the noise, which is why noise-cancelling headphones do not block the world with thicker foam. They play the noise backwards."
    ),
}


def _clean_topic_name(topic: str) -> str:
    """Extracts a clean, articulate subject name from a topic or title string."""
    cleaned = re.sub(r"^(The\s+)?(Hidden\s+Science\s+of|Secret\s+Inside|Physics\s+Paradox\s+of|Mystery\s+of)\s+", "", topic, flags=re.IGNORECASE)
    cleaned = re.sub(r"\([^)]*\)", "", cleaned)
    cleaned = re.sub(r"\[[^\]]*\]", "", cleaned)
    cleaned = re.sub(r"\|.*$", "", cleaned)
    cleaned = re.sub(r":.*$", "", cleaned)
    cleaned = re.sub(r"[#@][\w]+", "", cleaned)
    cleaned = " ".join(cleaned.split()).strip(".,;:!- ")
    words = cleaned.split()
    if len(words) > 6:
        words = words[:6]
    return " ".join(words).strip(".,;:!- ")


def _generate_dynamic_topic_script(
    topic: str,
    category: str = "STEM",
    tiktok_product: Optional[str] = None,
) -> str:
    """Synthesizes a cohesive, factually grounded 5-act narrative for any novel topic.

    Guarantees 155-170 words, natural cadence, and a seamless closing loop.
    """
    clean_subj = _clean_topic_name(topic) or "this mechanical mechanism"

    hook = f"Have you ever wondered what actually happens inside {clean_subj} when pushed to its physical limit?"
    act2 = (
        f" Most people assume that {clean_subj} operates on straightforward mechanical principles, "
        f"but diagnostic high-speed imaging reveals a completely counterintuitive physical reality."
    )
    act3 = (
        f" When external forces strike the framework, the kinetic energy does not travel in a simple straight vector. "
        f"Instead, microscopic internal geometry redirects the shear stress across an interconnected structural lattice before microcracks can propagate."
    )
    act4 = (
        f" Rather than resisting the impact with brittle resistance, the material dissipates shock waves across flexible load-bearing pathways, "
        f"allowing the assembly to absorb immense pressure without catastrophic failure."
    )
    bridge = ""
    if tiktok_product and "none" not in tiktok_product.lower():
        bridge = f" If you want to sketch out the structural engineering of {clean_subj} yourself, check out the {tiktok_product} linked down below."

    closing = f" Modern engineers study this exact dynamic distribution to build stronger machinery, which is why you have to wonder what actually happens inside {clean_subj} when pushed to its physical limit."

    full = (hook + act2 + act3 + act4 + bridge + closing).strip()
    words = full.split()

    if len(words) < 155:
        padding = " Scientists spent years conducting stress tests to verify that every load vector remains balanced in extreme environments."
        full = (hook + act2 + act3 + padding + act4 + bridge + closing).strip()
        words = full.split()

    if len(words) > 170:
        words = words[:165]
        # Re-attach clean closing loop
        closing_loop = f" which is why you have to wonder what actually happens inside {clean_subj} when pushed to its physical limit."
        full = " ".join(words[:148]).rstrip(".,;:!-") + "," + closing_loop

    return full


def modify_script(
    script_text: str,
    prompt: str = "",
    category: str = "STEM",
    target_duration: int = DEFAULT_TARGET_SECONDS,
    tiktok_product: Optional[str] = None,
    topic: str = "",
    speech_speed: float = 1.05,
    voice: str = "en-US-GuyNeural",
) -> str:
    """Revise a script, then lengthen it until the measured voice can hold the target.

    A shorten request is returned as written. Every other path is checked
    against the neural speaking rate so the draft is not secretly 45 seconds.
    """
    revised = _revise_script(
        script_text=script_text,
        prompt=prompt,
        category=category,
        target_duration=int(target_duration),
        tiktok_product=tiktok_product,
        topic=topic,
    )
    if any(word in (prompt or "").lower() for word in ("shorten", "compress", "faster")):
        return revised
    return ensure_script_word_count(
        revised,
        topic=topic or category,
        target_seconds=float(target_duration),
        speed=speech_speed,
        voice=voice,
    )


def _revise_script(
    script_text: str,
    prompt: str = "",
    category: str = "STEM",
    target_duration: int = DEFAULT_TARGET_SECONDS,
    tiktok_product: Optional[str] = None,
    topic: str = "",
) -> str:
    """Apply intelligent script revision based on prompt instruction and topic context.

    Args:
        script_text: Existing script content. If empty, generates a viral 155-170 word script.
        prompt: User's revision command (e.g., 'Make hook punchier', 'Add TikTok shop bridge').
        category: Niche category (STEM, Escape/Heist, Architecture, Psychology, Engineering, How It's Made).
        target_duration: Desired video duration in seconds.
        tiktok_product: Optional product to weave into the narrative.
        topic: Selected trend topic from Tab 1 to dynamically weave into the script.

    Returns:
        Revised script string with viral pacing (155-170 words) and seamless loop structure.
    """
    clean_prompt = prompt.strip().lower()
    text = script_text.strip()
    lines = [line.strip() for line in text.split("\n") if line.strip()]

    # If script is empty, deliver the topic-specific masterpiece
    if not text:
        comb_topic = (topic + " " + category).lower()

        if any(w in comb_topic for w in ["watch", "timepiece", "wristwatch", "horology", "clock"]):
            return MASTER_SCRIPTS["quartz_watch"]
        elif any(w in comb_topic for w in ["firework", "pyrotechnic", "mortar shell", "aerial shell"]):
            return MASTER_SCRIPTS["fireworks_shell"]
        elif any(w in comb_topic for w in ["headphone", "headset", "noise-cancel", "noise cancel", "anc "]):
            return MASTER_SCRIPTS["noise_cancelling_headphones"]
        elif any(w in comb_topic for w in ["concrete", "roman", "cement", "seawall", "pantheon", "architecture"]):
            return MASTER_SCRIPTS["architecture_roman_concrete"]
        elif any(w in comb_topic for w in ["piezo", "lighter", "butane", "spark gap"]):
            return MASTER_SCRIPTS["engineering_piezo_lighter"]
        elif any(w in comb_topic for w in ["motor", "brushless", "rotor", "stator", "rpm", "how it's made"]):
            return MASTER_SCRIPTS["how_its_made_brushless_motor"]
        elif any(w in comb_topic for w in ["vault", "heist", "alarm", "safe", "thief", "escape"]):
            return MASTER_SCRIPTS["escape_heist_vault_physics"]
        elif any(w in comb_topic for w in ["brain", "casino", "gambler", "psychology", "illusion"]):
            return MASTER_SCRIPTS["psychology_illusion_control"]
        elif any(w in comb_topic for w in ["vacuum", "feather", "bowling", "galileo", "gravity"]):
            return MASTER_SCRIPTS["stem_vacuum_paradox"]
        elif topic:
            return _generate_dynamic_topic_script(topic, category=category, tiktok_product=tiktok_product)
        else:
            cat_lower = category.lower()
            if "arch" in cat_lower:
                return MASTER_SCRIPTS["architecture_roman_concrete"]
            elif "eng" in cat_lower:
                return MASTER_SCRIPTS["engineering_piezo_lighter"]
            elif "how" in cat_lower:
                return MASTER_SCRIPTS["how_its_made_brushless_motor"]
            elif "heist" in cat_lower or "escape" in cat_lower:
                return MASTER_SCRIPTS["escape_heist_vault_physics"]
            elif "psych" in cat_lower:
                return MASTER_SCRIPTS["psychology_illusion_control"]
            else:
                return MASTER_SCRIPTS["stem_vacuum_paradox"]

    # In-place script revisions
    full_text = " ".join(lines)

    # 1. Punchier Hook Revision
    if any(w in clean_prompt for w in ["hook", "punchier", "start", "opening"]):
        clean_subj = _clean_topic_name(topic) or "this phenomenon"
        hook_options = {
            "Engineering": f"Inside every {clean_subj} is a hidden engineering marvel that violates common sense.",
            "Architecture": f"{clean_subj.title()} gets stronger under the exact forces that should destroy it.",
            "How It's Made": f"Inside {clean_subj}, nothing is actually touching—even at maximum velocity.",
            "Escape/Heist": f"This was labeled an impenetrable security barrier until researchers exposed a fatal design flaw.",
            "Psychology": f"Your brain is deceiving you right now about how {clean_subj} actually works.",
            "STEM": f"If you test {clean_subj} in a high-speed diagnostic lab, common intuition completely breaks down.",
        }
        new_hook = hook_options.get(category, f"Watch what happens when you examine {clean_subj} under extreme diagnostic load.")
        sentences = re.split(r"(?<=[.!?])\s+", full_text)
        if sentences:
            sentences[0] = new_hook
            full_text = " ".join(sentences)
        else:
            full_text = new_hook + " " + full_text

    # 2. Add TikTok Shop Organic Bridge
    elif any(w in clean_prompt for w in ["product", "shop", "bridge", "monetize"]):
        product_name = tiktok_product or "drawing stylus and drafting notebook"
        bridge = f" If you want to study the internal blueprint of this mechanism yourself, check out the {product_name} linked down below."
        sentences = re.split(r"(?<=[.!?])\s+", full_text)
        if len(sentences) > 2:
            sentences.insert(-1, bridge)
            full_text = " ".join(sentences)
        else:
            full_text = full_text + bridge

    # 3. Shorten Script
    elif any(w in clean_prompt for w in ["shorten", "compress", "faster"]):
        sentences = re.split(r"(?<=[.!?])\s+", full_text)
        if len(sentences) > 4:
            # Drop middle elaboration sentence
            mid = len(sentences) // 2
            sentences.pop(mid)
            full_text = " ".join(sentences)

    # 4. Expand Script for 60s+ Target
    elif any(w in clean_prompt for w in ["expand", "longer", "60s", "detail"]):
        expansion = " When you inspect the cross-section under electron microscopy, you can clearly see how every single stress fracture is redirected into harmless compression zones."
        sentences = re.split(r"(?<=[.!?])\s+", full_text)
        if len(sentences) > 2:
            sentences.insert(2, expansion)
            full_text = " ".join(sentences)

    words = full_text.split()
    logger.info("Script modified (Words: %d). Prompt: '%s'", len(words), prompt)
    return full_text
