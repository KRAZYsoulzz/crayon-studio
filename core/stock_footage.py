"""Stock footage for STEM shorts, accepted only when the clip shows the mechanism.

Pexels and Pixabay are free, but a search for "quartz watch" or "fireworks"
usually returns a wrist on a table or a festival sky. Those clips do not
explain a tuning fork or an aerial shell. A candidate is kept only when its
title or tags share a specific mechanism term with the scene. Otherwise the
caller falls back to a generated still with camera motion.

Clips already downloaded for this project are reused when the new scene
shares those mechanism terms. A fireworks plate is never reused for a watch.
"""

from __future__ import annotations

import json
import logging
import os
import re
import urllib.parse
import urllib.request
from typing import Callable, Dict, Iterable, List, Optional, Sequence, Set, Tuple

logger = logging.getLogger("crayon_studio.stock_footage")

# Topic nouns that stock sites match too easily. Overlap on these alone is not
# evidence that the clip shows how the thing works.
GENERIC_TERMS = {
    "a", "an", "the", "of", "and", "or", "in", "on", "to", "for", "with", "from",
    "how", "why", "what", "it", "is", "are", "this", "that", "its", "into", "over",
    "watch", "watches", "clock", "clocks", "time", "timepiece", "wrist", "wristwatch",
    "firework", "fireworks", "celebration", "celebrate", "sky", "night", "party",
    "headphone", "headphones", "headset", "music", "song", "audio", "sound", "noise",
    "person", "people", "man", "woman", "girl", "boy", "wearing", "portrait",
    "background", "table", "desk", "hand", "hands", "phone", "video", "clip",
    "quartz", "crystal", "close", "closeup", "macro", "shot", "footage", "4k", "hd",
    "slow", "motion", "cinematic", "beautiful", "amazing",
}

# Phrases that mean the clip is a lifestyle shot even if a topic word matches.
LIFESTYLE_PHRASES = (
    "on a table",
    "on table",
    "wooden table",
    "wearing",
    "celebration",
    "party",
    "skyline",
    "background",
    "smiling",
    "portrait",
    "festival",
    "new year",
)

_TOKEN = re.compile(r"[a-z0-9]+")


def _tokens(text: str) -> List[str]:
    return _TOKEN.findall((text or "").lower())


def specific_terms(text: str) -> Set[str]:
    """Mechanism terms: unigrams that are not generic, plus every bigram."""
    tokens = _tokens(text)
    terms: Set[str] = {token for token in tokens if token not in GENERIC_TERMS and len(token) > 2}
    for left, right in zip(tokens, tokens[1:]):
        bigram = f"{left} {right}"
        # Keep a bigram when at least one half is specific, so "tuning fork"
        # and "aerial shell" count, while "on a" does not.
        if left not in GENERIC_TERMS or right not in GENERIC_TERMS:
            if left not in {"a", "an", "the", "of", "and", "or", "in", "on", "to", "for", "with"}:
                terms.add(bigram)
    return terms


def _is_lifestyle(title: str) -> bool:
    lowered = (title or "").lower()
    return any(phrase in lowered for phrase in LIFESTYLE_PHRASES)


def score_stock_match(scene_text: str, title: str, tags: Optional[Iterable[str]] = None) -> Tuple[float, Set[str]]:
    """Return ``(score, overlapping_mechanism_terms)``.

    Score is 0 when the only shared words are generic topic nouns, or when
    the title is a lifestyle shot with fewer than two mechanism terms.
    """
    scene_specific = specific_terms(scene_text)
    candidate_text = " ".join([title or ""] + list(tags or []))
    candidate_specific = specific_terms(candidate_text)
    overlap = scene_specific & candidate_specific
    if not overlap:
        return 0.0, set()
    if _is_lifestyle(title) and len(overlap) < 2:
        return 0.0, set()
    # Bigrams are stronger evidence than a single shared noun.
    bigrams = {term for term in overlap if " " in term}
    score = float(len(overlap) + len(bigrams))
    return score, overlap


def accepts_stock(scene_text: str, title: str, tags: Optional[Iterable[str]] = None) -> bool:
    """True when the clip is specific enough to carry this scene."""
    score, _overlap = score_stock_match(scene_text, title, tags)
    return score >= 1.0


def search_query(scene_text: str, limit: int = 6) -> str:
    """A short query built from mechanism terms, not the whole sentence."""
    terms = sorted(specific_terms(scene_text), key=lambda term: (term.count(" "), len(term)), reverse=True)
    chosen: List[str] = []
    for term in terms:
        if len(chosen) >= limit:
            break
        if any(term in earlier or earlier in term for earlier in chosen):
            continue
        chosen.append(term)
    return " ".join(chosen)


def _http_json(url: str, headers: Optional[Dict[str, str]] = None, timeout: int = 20) -> dict:
    request = urllib.request.Request(url, headers=headers or {"User-Agent": "CrayonStudio/1.0"})
    with urllib.request.urlopen(request, timeout=timeout) as response:
        return json.loads(response.read().decode("utf-8"))


def _download(url: str, dest: str, timeout: int = 45) -> bool:
    request = urllib.request.Request(url, headers={"User-Agent": "CrayonStudio/1.0"})
    os.makedirs(os.path.dirname(os.path.abspath(dest)), exist_ok=True)
    with urllib.request.urlopen(request, timeout=timeout) as response:
        data = response.read()
    if len(data) < 20000:
        return False
    with open(dest, "wb") as handle:
        handle.write(data)
    return True


def _pick_pexels_file(video: dict) -> Optional[str]:
    files = video.get("video_files") or []
    mp4s = []
    for item in files:
        link = item.get("link") or ""
        kind = str(item.get("file_type") or "")
        if "mp4" not in kind.lower() and not link.lower().endswith(".mp4"):
            continue
        width = int(item.get("width") or 0)
        height = int(item.get("height") or 0)
        mp4s.append((height >= width, height, link))
    if not mp4s:
        return None
    # Prefer portrait, then a height near 1280 so we do not pull a 4K master.
    mp4s.sort(key=lambda item: (not item[0], 0 if item[1] >= 720 else 1, abs(item[1] - 1280)))
    return mp4s[0][2] or None


def search_pexels(query: str, api_key: str, per_page: int = 8) -> List[dict]:
    """Search Pexels videos. Returns candidate dicts with title, tags, url, credit."""
    if not api_key or not query:
        return []
    url = (
        "https://api.pexels.com/videos/search?"
        + urllib.parse.urlencode({
            "query": query,
            "orientation": "portrait",
            "per_page": per_page,
            "size": "medium",
        })
    )
    payload = _http_json(url, headers={"Authorization": api_key, "User-Agent": "CrayonStudio/1.0"})
    found = []
    for video in payload.get("videos") or []:
        link = _pick_pexels_file(video)
        if not link:
            continue
        user = (video.get("user") or {}).get("name") or "Pexels contributor"
        # Pexels does not return tags. The URL slug is the closest title.
        slug = str(video.get("url") or "")
        title = slug.rstrip("/").split("/")[-1].replace("-", " ")
        found.append({
            "title": title,
            "tags": [],
            "download_url": link,
            "credit": f"Pexels / {user}",
            "source": "pexels",
        })
    return found


def search_pixabay(query: str, api_key: str, per_page: int = 8) -> List[dict]:
    """Search Pixabay videos. Tags are the match text."""
    if not api_key or not query:
        return []
    url = (
        "https://pixabay.com/api/videos/?"
        + urllib.parse.urlencode({
            "key": api_key,
            "q": query,
            "video_type": "film",
            "orientation": "vertical",
            "per_page": min(per_page, 20),
            "safesearch": "true",
        })
    )
    payload = _http_json(url)
    found = []
    for hit in payload.get("hits") or []:
        videos = hit.get("videos") or {}
        # medium is enough for a 1080-wide crop; large is the fallback.
        file_info = videos.get("medium") or videos.get("small") or videos.get("large") or {}
        link = file_info.get("url")
        if not link:
            continue
        tags = [tag.strip() for tag in str(hit.get("tags") or "").split(",") if tag.strip()]
        user = hit.get("user") or "Pixabay contributor"
        found.append({
            "title": " ".join(tags),
            "tags": tags,
            "download_url": link,
            "credit": f"Pixabay / {user}",
            "source": "pixabay",
        })
    return found


def _manifest_path(storyboard_dir: str) -> str:
    return os.path.join(storyboard_dir, "stock_manifest.json")


def _load_manifest(storyboard_dir: str) -> List[dict]:
    path = _manifest_path(storyboard_dir)
    if not os.path.exists(path):
        return []
    try:
        with open(path, "r", encoding="utf-8") as handle:
            data = json.load(handle)
        return data if isinstance(data, list) else []
    except Exception:
        return []


def _save_manifest(storyboard_dir: str, rows: List[dict]) -> None:
    with open(_manifest_path(storyboard_dir), "w", encoding="utf-8") as handle:
        json.dump(rows, handle, indent=2)


def _reusable_clip(scene_text: str, manifest: Sequence[dict]) -> Optional[dict]:
    """Reuse a downloaded clip only when the mechanism terms still overlap."""
    needed = specific_terms(scene_text)
    best: Optional[dict] = None
    best_score = 0.0
    for row in manifest:
        path = row.get("path") or ""
        if not path or not os.path.exists(path):
            continue
        stored = set(row.get("terms") or [])
        overlap = needed & stored
        bigrams = {term for term in overlap if " " in term}
        score = float(len(overlap) + len(bigrams))
        if score >= 2.0 and score > best_score:
            best = row
            best_score = score
    return best


def _append_credit(project_dir: str, line: str) -> None:
    path = os.path.join(project_dir, "stock_credits.txt")
    existing = ""
    if os.path.exists(path):
        with open(path, "r", encoding="utf-8") as handle:
            existing = handle.read()
    if line in existing:
        return
    with open(path, "a", encoding="utf-8") as handle:
        if not existing:
            handle.write("Stock footage used in this short. Keep these credits with the post.\n")
        handle.write(line.rstrip() + "\n")


def acquire_stock_clip(
    scene_text: str,
    storyboard_dir: str,
    scene_index: int,
    *,
    pexels_api_key: str = "",
    pixabay_api_key: str = "",
    progress_callback: Optional[Callable[[str], None]] = None,
) -> Optional[str]:
    """Download a matching stock clip, or return None so the caller can illustrate.

    API keys are read by the caller from the environment or config. This
    function never writes a key into the project.
    """
    def _log(message: str) -> None:
        logger.info(message)
        if progress_callback:
            progress_callback(message)

    if not scene_text.strip():
        return None

    manifest = _load_manifest(storyboard_dir)
    reused = _reusable_clip(scene_text, manifest)
    if reused:
        _log(f"[Stock] Scene {scene_index + 1}: reusing {os.path.basename(reused['path'])} (mechanism still matches).")
        return reused["path"]

    query = search_query(scene_text)
    if not query:
        _log(f"[Stock] Scene {scene_index + 1}: no mechanism terms to search. Using illustrated motion.")
        return None

    pexels_key = pexels_api_key or os.environ.get("PEXELS_API_KEY", "")
    pixabay_key = pixabay_api_key or os.environ.get("PIXABAY_API_KEY", "")
    if not pexels_key and not pixabay_key:
        _log("[Stock] No Pexels or Pixabay key configured. Using illustrated motion.")
        return None

    candidates: List[dict] = []
    errors: List[str] = []
    if pexels_key:
        try:
            candidates.extend(search_pexels(query, pexels_key))
        except Exception as exc:
            errors.append(f"Pexels: {exc}")
    if pixabay_key:
        try:
            candidates.extend(search_pixabay(query, pixabay_key))
        except Exception as exc:
            errors.append(f"Pixabay: {exc}")
    for err in errors:
        _log(f"[Stock] {err}")

    ranked = []
    for candidate in candidates:
        score, overlap = score_stock_match(scene_text, candidate.get("title", ""), candidate.get("tags"))
        if score <= 0:
            continue
        ranked.append((score, overlap, candidate))
    ranked.sort(key=lambda item: item[0], reverse=True)

    if not ranked:
        _log(
            f"[Stock] Scene {scene_index + 1}: no clip matched the mechanism in '{query}'. "
            "Using a generated still with camera motion."
        )
        return None

    score, overlap, chosen = ranked[0]
    dest = os.path.join(storyboard_dir, f"stock_{scene_index + 1:02d}.mp4")
    try:
        ok = _download(chosen["download_url"], dest)
    except Exception as exc:
        _log(f"[Stock] Download failed ({exc}). Using illustrated motion.")
        return None
    if not ok:
        _log("[Stock] Download was empty. Using illustrated motion.")
        return None

    terms = sorted(specific_terms(scene_text))
    manifest.append({
        "path": dest,
        "terms": terms,
        "credit": chosen.get("credit", ""),
        "query": query,
        "score": score,
    })
    _save_manifest(storyboard_dir, manifest)
    project_dir = os.path.dirname(storyboard_dir)
    credit = chosen.get("credit") or chosen.get("source") or "stock"
    _append_credit(project_dir, f"Scene {scene_index + 1}: {credit} — matched {', '.join(sorted(overlap))}")
    _log(
        f"[Stock] Scene {scene_index + 1}: using {chosen.get('source', 'stock')} "
        f"({credit}) because it matches {', '.join(sorted(overlap))}."
    )
    return dest
