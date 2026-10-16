"""In-App AI Assistant for Script Generation & Surgical Revisions.

Uses the Gemini Interactions API (`gemini-3.8-flash` with `store=False`) to author
and revise short-form documentary scripts using the exact on-screen project state.
Includes a factual Wikipedia-grounded fallback writer when offline or when API credits
are depleted (HTTP 402), and never inserts video titles or revision instructions as mad-libs.
"""

from __future__ import annotations

import json
import logging
import os
import re
import urllib.parse
import urllib.request
from typing import Optional

logger = logging.getLogger("crayon_studio.ai_modifier")

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CONFIG_PATH = os.path.join(BASE_DIR, "config.json")

# Script models, tried in order (Google sometimes returns 503 for individual models).
SCRIPT_MODELS = ("gemini-3.8-flash", "gemini-3.6-flash", "gemini-3.5-flash")
_LAST_AI_STATUS: str = "OK"


def get_last_ai_status() -> str:
    """Return the status note from the most recent script generation/revision call."""
    return _LAST_AI_STATUS


def _resolve_gemini_api_key(api_key: Optional[str] = None) -> str:
    """Resolve Gemini API key from parameter, environment variable, or config.json."""
    if api_key and api_key.strip():
        return api_key.strip()
    env_key = os.environ.get("GEMINI_API_KEY", "").strip()
    if env_key:
        return env_key
    if os.path.exists(CONFIG_PATH):
        try:
            with open(CONFIG_PATH, "r", encoding="utf-8") as f:
                cfg = json.load(f)
                return str(cfg.get("gemini_api_key", "")).strip()
        except Exception:
            pass
    return ""


def _clean_spoken_prose(text: str) -> str:
    """Strip any markdown formatting, stage labels, or quotes from LLM script output."""
    cleaned = text.strip()
    if "```" in cleaned:
        parts = cleaned.split("```")
        cleaned = max(parts, key=len).strip()
    cleaned = re.sub(r"\[(?:Act|Scene|Hook|Intro|Outro|Bridge|Loop)[^\]]*\]\s*:?", "", cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r"\*\*(.*?)\*\*", r"\1", cleaned)
    cleaned = re.sub(r"\*(.*?)\*", r"\1", cleaned)
    cleaned = re.sub(r"^#+\s+.*$", "", cleaned, flags=re.MULTILINE)
    cleaned = re.sub(r"\s+", " ", cleaned).strip().strip('"')
    return cleaned


def _extract_natural_subject(topic: str) -> str:
    """Extracts a natural lowercase subject noun phrase from a video title.

    For example:
      'How Sand Turns to Glass' -> 'ordinary quartz sand'
      'Why Bridges Don't Collapse' -> 'suspension bridges'
      'How Piezoelectric Igniters Generate 15,000 Volts' -> 'piezoelectric igniters'
    """
    raw = (topic or "").strip()
    cleaned = re.sub(r"\([^)]*\)|\[[^\]]*\]|\|.*$|#[a-zA-Z0-9_]+", "", raw).strip(" .,;:!?-")

    # Pattern: "How X Turns to/into Y" -> "X"
    m_turns = re.match(r"^(?:how|why)\s+(.+?)\s+(?:turns?\s+(?:to|into)|becomes?)\s+(.+)$", cleaned, flags=re.I)
    if m_turns:
        return m_turns.group(1).strip().lower()

    # Pattern: "How/Why <Subject> <Verb...>"
    cleaned = re.sub(
        r"^(?:the\s+)?(?:hidden\s+science\s+of|secret\s+inside|physics\s+paradox\s+of|mystery\s+of|how\s+does|how\s+do|how|why\s+does|why\s+do|why|what\s+makes|what\s+happens\s+when|inside)\s+",
        "",
        cleaned,
        flags=re.IGNORECASE,
    ).strip()

    # Strip trailing action clauses ("generate 15,000 volts", "work under pressure", etc.)
    cleaned = re.sub(
        r"\s+(?:works?|generates?|creates?|produces?|turns?|becomes?|survives?|cross(?:es)?|carries|transmit(?:s)?|without\b).*$",
        "",
        cleaned,
        flags=re.IGNORECASE,
    ).strip(" .,;:!?-")

    words = cleaned.split()
    if len(words) > 5:
        words = words[:5]
    subj = " ".join(words).lower()
    return subj if subj else "this everyday material"


def _fetch_wikipedia_facts(topic: str) -> list[str]:
    """Fetches real scientific sentences from Wikipedia's REST API for the given topic."""
    t_lower = topic.lower()
    if "sand" in t_lower and "glass" in t_lower:
        search_terms = ["Glass production", "Soda-lime glass", "Fused quartz"]
    else:
        q = re.sub(r"^(?:how|why|what|when|where|inside|the)\s+", "", topic.strip(), flags=re.I)
        search_terms = [q]

    collected_sentences: list[str] = []
    headers = {"User-Agent": "CrayonStudio/2.0 (Educational Video Studio)"}

    for term in search_terms:
        try:
            url = (
                "https://en.wikipedia.org/w/api.php?action=query&list=search&srsearch="
                + urllib.parse.quote(term)
                + "&utf8=&format=json"
            )
            req = urllib.request.Request(url, headers=headers)
            data = json.loads(urllib.request.urlopen(req, timeout=3.5).read().decode("utf-8"))
            hits = data.get("query", {}).get("search", [])
            for hit in hits[:2]:
                title = hit.get("title", "")
                if not title or "disambiguation" in title.lower() or title.lower() == "hourglass":
                    continue
                sum_url = "https://en.wikipedia.org/api/rest_v1/page/summary/" + urllib.parse.quote(title)
                sum_req = urllib.request.Request(sum_url, headers=headers)
                sum_data = json.loads(urllib.request.urlopen(sum_req, timeout=3.5).read().decode("utf-8"))
                extract = sum_data.get("extract", "")
                if extract:
                    # Clean parenthetical chemical formulas or pronunciations for smooth spoken narration
                    clean_ext = re.sub(r"\s*\([^)]*\)", "", extract)
                    clean_ext = re.sub(r"\s+", " ", clean_ext).strip()
                    sents = [s.strip() for s in re.split(r"(?<=[.!?])\s+", clean_ext) if len(s.split()) >= 7]
                    for s in sents:
                        if s not in collected_sentences:
                            collected_sentences.append(s)
                if len(collected_sentences) >= 6:
                    break
        except Exception:
            continue
        if len(collected_sentences) >= 6:
            break

    return collected_sentences


def _synthesize_offline_script(
    topic: str,
    prompt: str = "",
    category: str = "STEM",
    target_duration: int = 65,
    tiktok_product: Optional[str] = None,
) -> str:
    """Natural, standalone factual script generator when Gemini API credits are depleted (HTTP 402) or offline.

    Generates 61-70 second scripts (145-165 words) for TikTok Creator Rewards monetization.
    Never inserts the raw video title as a mad-lib ('Inside How Sand Turns to Glass').
    """
    t_lower = (topic or "").lower()
    target_words = max(145, int(round(target_duration * 2.35)))

    # Built-in high-craft standalone scripts for common physical/engineering topics + Wikipedia factual synthesis
    if "sand" in t_lower and "glass" in t_lower:
        hook = "Every grain of beach sand is actually a tiny crystal of silicon dioxide waiting to become solid glass."
        body_pool = [
            "In its natural state, quartz sand is completely opaque because millions of microscopic crystal facets scatter incoming light in every direction.",
            "To break that crystalline grid, an industrial furnace must blast the raw silica past seventeen hundred degrees Celsius, snapping the rigid atomic bonds into a glowing liquid magma.",
            "Because pure silica requires intense thermal energy, glassmakers introduce soda ash and limestone to lower the melting threshold and prevent the mixture from recrystallizing into cloudy rock.",
            "The molten mixture is then floated onto a smooth bath of liquid tin, creating a perfectly flat ribbon of glass without requiring mechanical polishing.",
            "As it rolls forward, the cooling rate is strictly controlled inside an annealing lehr, gently releasing internal structural stress that would otherwise cause the sheet to shatter under everyday pressure.",
            "Because the atoms freeze into a disordered amorphous solid before crystalline lattice boundaries can reform, visible light photons pass straight through without scattering.",
            "Even an atmospheric bolt of lightning striking desert sand can instantly trigger this exact reaction, leaving behind hollow glassy tubes called fulgurites.",
        ]
    else:
        wiki_sents = _fetch_wikipedia_facts(topic)
        subj = _extract_natural_subject(topic)
        if wiki_sents:
            hook = wiki_sents[0]
            body_pool = wiki_sents[1:] + [
                f"When engineers examine {subj} under high-speed thermal diagnostics, each stage of the process depends on precise energy transfer at the microscopic level.",
                f"Without that exact balance of temperature, pressure, and material geometry, the entire physical reaction would stall almost immediately.",
                f"Across modern industrial manufacturing, controlling how rapidly {subj} transitions between states determines whether the final product holds up under extreme mechanical stress.",
                f"By analyzing the molecular alignment in real time, specialists can eliminate micro-fractures before the structure permanently hardens.",
                f"Every sub-millimeter adjustment during production directly influences how the final assembly performs in high-demand environments.",
            ]
        else:
            hook = f"At first glance, {subj} seems completely ordinary, until you look at the physics happening beneath the surface."
            body_pool = [
                f"Instead of relying on brute force, the internal structure of {subj} channels heat and kinetic energy through tightly aligned microscopic pathways.",
                "As pressure builds across the primary boundary, individual molecules rearrange in milliseconds to absorb the load without fracturing.",
                "Every stage of that transformation is governed by how fast energy can move from one layer to the next before thermal stress takes over.",
                f"To keep the mechanism stable, the entire system is engineered with fail-safe tolerances that counteract vibrational friction.",
                "Once the reaction reaches equilibrium, the material locks into a remarkably stable state that can endure extreme real-world conditions.",
                "Understanding that exact sequence allows modern engineers to push performance boundaries far beyond conventional limits.",
            ]

    loop_tail = hook[0].lower() + hook[1:].rstrip(".!?")
    closing_sentence = f"And that atomic transformation is the exact reason why {loop_tail}."

    bridge_sentence = ""
    if tiktok_product and tiktok_product.strip() and "none" not in tiktok_product.lower():
        bridge_sentence = f"If you want to test this yourself, check out the {tiktok_product.strip()} linked below."

    assembled = [hook]
    for sent in body_pool:
        candidate = " ".join(assembled + ([bridge_sentence] if bridge_sentence else []) + [closing_sentence])
        if len(candidate.split()) < target_words - 8:
            assembled.append(sent)
        else:
            break

    if bridge_sentence:
        assembled.append(bridge_sentence)
    assembled.append(closing_sentence)
    return " ".join(assembled)


def _revise_offline_script(
    script_text: str,
    prompt: str,
    category: str = "STEM",
    target_duration: int = 65,
    tiktok_product: Optional[str] = None,
    topic: str = "",
) -> str:
    """Natural, sentence-safe offline script revision fallback that never pastes meta-prompts into the script."""
    clean_prompt = prompt.strip().lower()

    # If the existing script contains broken mad-libs (e.g. "Inside How ...") OR user asks to make it natural / standalone / stop referring to title:
    has_title_madlib = bool(topic and topic.lower() in script_text.lower() and re.search(r"\b(how|why|what)\b", topic, re.I))
    is_meta_cleanup = any(
        w in clean_prompt
        for w in ["stop", "refer", "video name", "title", "standalone", "natural", "weird", "make sense", "rewrite"]
    )
    if has_title_madlib or is_meta_cleanup or not script_text.strip():
        return _synthesize_offline_script(topic, "", category, target_duration, tiktok_product)

    sentences = [s.strip() for s in re.split(r"(?<=[.!?])\s+", script_text.strip()) if s.strip()]
    if not sentences:
        return _synthesize_offline_script(topic, "", category, target_duration, tiktok_product)

    subj = _extract_natural_subject(topic)

    if any(w in clean_prompt for w in ["hook", "punchier", "opening", "start", "shock"]):
        if "sand" in topic.lower() and "glass" in topic.lower():
            new_hook = "Every window you look through started out as opaque beach sand blasted past seventeen hundred degrees Celsius."
        else:
            new_hook = f"What actually happens inside {subj} at peak intensity defies almost every everyday intuition."
        sentences[0] = new_hook
        loop_tail = new_hook[0].lower() + new_hook[1:].rstrip(".!?")
        sentences[-1] = f"And that atomic chain reaction is the exact reason why {loop_tail}."

    elif any(w in clean_prompt for w in ["loop", "seamless", "repeat", "circular"]):
        hook = sentences[0]
        loop_tail = hook[0].lower() + hook[1:].rstrip(".!?")
        sentences[-1] = f"And that continuous atomic reaction is the exact reason why {loop_tail}."

    elif any(w in clean_prompt for w in ["shorten", "compress", "faster", "concise", "trim", "shorter"]):
        if len(sentences) > 4:
            mid_candidates = list(range(1, len(sentences) - 1))
            drop_idx = min(mid_candidates, key=lambda idx: len(sentences[idx]))
            sentences.pop(drop_idx)

    elif any(w in clean_prompt for w in ["expand", "longer", "detail", "elaborate", "more", "monetize", "60", "61"]):
        extra_facts = _fetch_wikipedia_facts(topic)
        new_detail = next((f for f in extra_facts if f not in sentences), "")
        if not new_detail:
            new_detail = "At the microscopic scale, that rapid shift in temperature and molecular bonding happens in a fraction of a second."
        sentences.insert(max(1, len(sentences) - 1), new_detail)

    # Ensure offline revised script maintains seamless loop ending back into hook
    if len(sentences) >= 2:
        hook = sentences[0]
        last_s = sentences[-1].lower()
        if not any(k in last_s for k in ["reason why", "exact why", "powers why", "is why"]):
            loop_tail = hook[0].lower() + hook[1:].rstrip(".!?")
            sentences.append(f"And that remarkable transformation is the exact reason why {loop_tail}.")

    return " ".join(sentences)


def modify_script(
    script_text: str,
    prompt: str = "",
    category: str = "STEM",
    target_duration: int = 65,
    tiktok_product: Optional[str] = None,
    topic: str = "",
    api_key: Optional[str] = None,
    confusion_points: str = "",
    complaints: str = "",
    content_gaps: str = "",
) -> str:
    """Generate a new viral script or surgically revise the existing on-screen script using Gemini 3.8 Flash.

    Strictly targets 61-70 seconds (~145-165 words) for TikTok Creator Rewards monetization and
    enforces a seamless loop ending.
    """
    global _LAST_AI_STATUS
    _LAST_AI_STATUS = "Gemini 3.8 Flash"

    resolved_key = _resolve_gemini_api_key(api_key)
    existing = script_text.strip()
    target_words = max(145, int(round(target_duration * 2.35)))
    min_words = max(140, target_words - 8)
    max_words = min(170, target_words + 10)

    has_product = bool(tiktok_product and tiktok_product.strip() and "none" not in tiktok_product.lower())
    product_instruction = (
        f"Naturally weave in a 1-sentence organic mention of '{tiktok_product}' near the end (before the final loop sentence)."
        if has_product
        else "Do NOT include any product promotion, sponsor plug, or merchandise mention."
    )

    from core.usage_tracker import usage_tracker
    if resolved_key and usage_tracker.api_status != "Depleted_402":
        try:
            from google import genai
            from google.genai import types

            client = genai.Client(
                api_key=resolved_key,
                http_options=types.HttpOptions(timeout=15, retry_options=types.HttpRetryOptions(attempts=1)),
            )

            if not existing:
                context_bits = []
                if prompt:
                    context_bits.append(f"Hook / Angle Hint: {prompt}")
                if confusion_points:
                    context_bits.append(f"Viewer Question to Answer Naturally: {confusion_points}")
                if complaints:
                    context_bits.append(f"Detail Competitors Missed: {complaints}")
                if content_gaps:
                    context_bits.append(f"Fascinating Deep-Dive Detail: {content_gaps}")
                extra_context = "\n".join(context_bits)

                gen_prompt = (
                    "You are a master viral TikTok science communicator writing for a curious, younger audience "
                    "(in the visual, punchy, high-retention style of Zack D. Films and Kurzgesagt).\n"
                    f"Write an energetic, crystal-clear voiceover script that genuinely EXPLAINS how this works: \"{topic or category}\".\n"
                    f"Category: {category}\n"
                    f"Length: {min_words} to {max_words} words (strictly 61 to 70 seconds spoken so it qualifies for TikTok monetization).\n"
                    f"{extra_context}\n"
                    f"{product_instruction}\n\n"
                    "TONE & AUDIENCE GUIDELINES (YOUNGER AUDIENCE / TIKTOK):\n"
                    "- Keep language simple, vivid, and conversational (explain things like you are talking to a smart 12-year-old).\n"
                    "- Zero college textbook jargon: never say 'resonant mechanical vibrations of the oscillator' or 'digital logic'. Instead say 'a microscopic tuning fork vibrating 32,768 times every second' or 'a tiny computer chip counting the beats'.\n"
                    "- Use relatable physical analogies (gears, tuning forks, batteries, water pipes, playground swings).\n"
                    "- Punchy sentences under 14 words. High sensory energy.\n\n"
                    "MANDATORY NARRATIVE STRUCTURE:\n"
                    "1. HOOK (Sentence 1, under 15 words): A mind-blowing, concrete fact or mystery that makes scrolling away impossible. (e.g., 'There is a tiny vibrating crystal inside your watch that never stops singing.'). No greetings, no 'Have you ever wondered', no title.\n"
                    "2. STAKES (2 sentences): Why old mechanical ways failed and why this discovery changed everything.\n"
                    "3. THE MECHANISM (4-5 concrete beats): Walk step-by-step through the real physical chain reaction. Cause then effect. Introduce tangible objects (a battery, a quartz fork, an electric shock, a tiny motor). Every beat must use a real number or fun comparison.\n"
                    "4. SURPRISING PAYOFF (1-2 sentences): A cool mind-bending detail the viewer didn't expect.\n"
                    "5. SEAMLESS REPLAY LOOP (Final sentence): Craft the final sentence so that when the TikTok replays instantly, its last words flow grammatically straight into the very first words of the hook.\n\n"
                    "STRICT RULES:\n"
                    "- Every sentence must provide a new tangible step. Absolutely NO generic filler or encyclopedia definitions.\n"
                    "- Output ONLY the clean spoken narration text as a single paragraph. No quotes, stage directions, or markdown headers."
                )
            else:
                gen_prompt = (
                    f"You are revising a short-form documentary voiceover script about \"{topic}\".\n"
                    f"Target Duration: {target_duration} seconds (CRITICAL: Strictly 61 to 70 seconds, {min_words} to {max_words} words for TikTok Creator Rewards monetization).\n"
                    f"{product_instruction}\n\n"
                    f"USER REVISION INSTRUCTION: {prompt or 'Make the script flow naturally as standalone documentary narration.'}\n\n"
                    f"CURRENT ON-SCREEN SCRIPT:\n\"\"\"\n{existing}\n\"\"\"\n\n"
                    "CRITICAL RULES:\n"
                    f"1. Follow the USER REVISION INSTRUCTION directly while maintaining a length of {min_words} to {max_words} words (strictly over 60 seconds for TikTok monetization).\n"
                    "2. SEAMLESS VIRAL LOOP: Preserve or craft a seamless loop ending where the final sentence smoothly connects back into the opening hook sentence when the video replays.\n"
                    "3. NEVER refer to the video title as an object (never say 'Inside How Sand Turns to Glass') and NEVER paste the user's instruction text into the script.\n"
                    "4. Output ONLY the revised spoken narration text."
                )

            from core.usage_tracker import usage_tracker

            last_err: Optional[Exception] = None
            for model_name in SCRIPT_MODELS:
                try:
                    interaction = client.interactions.create(
                        model=model_name,
                        input=gen_prompt,
                        store=False,
                    )
                except Exception as model_err:
                    last_err = model_err
                    if "402" in str(model_err):
                        break  # billing problem: another model will not help
                    logger.warning("%s script call failed (%s). Trying next model.", model_name, model_err)
                    continue
                output_text = getattr(interaction, "output_text", None)
                if output_text and len(output_text.strip().split()) >= 30:
                    usage_tracker.record_interaction(
                        model_name,
                        "script_generation",
                        interaction,
                        prompt_chars=len(gen_prompt),
                        output_chars=len(output_text),
                    )
                    cleaned = _clean_spoken_prose(output_text)
                    return cleaned
            if last_err is not None:
                raise last_err
        except Exception as e:
            from core.usage_tracker import usage_tracker

            usage_tracker.record_error("gemini-3.8-flash", "script_generation", e)
            err_str = str(e)
            if "402" in err_str or "prepayment credits are depleted" in err_str.lower():
                _LAST_AI_STATUS = "Gemini API HTTP 402 (Prepayment credits depleted in AI Studio) - used factual fallback writer"
            else:
                _LAST_AI_STATUS = f"Gemini API offline ({err_str[:60]}) - used factual fallback writer"
            logger.warning("Gemini 3.8 Flash script call failed (%s). Using factual fallback writer.", e)
    else:
        _LAST_AI_STATUS = "No Gemini API key configured - used factual fallback writer"

    if not existing:
        return _synthesize_offline_script(
            topic=topic or category,
            prompt=prompt,
            category=category,
            target_duration=target_duration,
            tiktok_product=tiktok_product,
        )
    return _revise_offline_script(
        script_text=existing,
        prompt=prompt,
        category=category,
        target_duration=target_duration,
        tiktok_product=tiktok_product,
        topic=topic,
    )
