"""
CRAYON STUDIO — Live API Credit Health & Token/Cost Telemetry Engine
Tracks real-time Gemini API health (Active, Depleted HTTP 402, Invalid Key, Offline),
session & all-time token/image/video usage, and upfront pre-render USD cost estimates.
"""

from __future__ import annotations

import json
import logging
import os
from typing import Any, Callable, Dict, List, Optional

from database.db import init_db, record_usage_event, get_usage_summary

logger = logging.getLogger("crayon_studio.usage_tracker")

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CONFIG_PATH = os.path.join(BASE_DIR, "config.json")


class UsageTracker:
    """Singleton telemetry tracker for Gemini API health, token usage, and USD cost estimation."""

    _instance: Optional["UsageTracker"] = None

    # Reference pricing rates (USD)
    TOKEN_RATES_PER_1M = {
        "gemini-3.8-flash": (0.15, 0.60),
        "gemini-3.5-flash-lite": (0.075, 0.30),
    }
    IMAGE_RATES = {
        "gemini-nano-banana-2.1": 0.02,
        "gemini-3.1-flash-lite-image": 0.01,
        "gemini-3-pro-image": 0.035,
    }
    VIDEO_RATE_PER_SEC_720P = 0.030
    VIDEO_RATE_PER_SEC_1080P = 0.045

    def __new__(cls) -> "UsageTracker":
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self) -> None:
        if getattr(self, "_initialized", False):
            return
        self._initialized = True
        self.api_status: str = "Unknown"  # Active | Depleted_402 | Invalid_Key | Offline
        self.api_status_detail: str = "Checking Gemini API status..."
        self.session_tokens: int = 0
        self.session_images: int = 0
        self.session_video_seconds: float = 0.0
        self.session_cost_usd: float = 0.0
        self.session_calls: int = 0
        self._listeners: List[Callable[[Dict[str, Any]], None]] = []
        try:
            init_db()
        except Exception:
            pass

    def add_listener(self, callback: Callable[[Dict[str, Any]], None]) -> None:
        if callback not in self._listeners:
            self._listeners.append(callback)

    def _notify(self) -> None:
        snap = self.get_snapshot()
        for cb in list(self._listeners):
            try:
                cb(snap)
            except Exception:
                pass

    @staticmethod
    def _resolve_api_key(api_key: Optional[str] = None) -> str:
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

    def probe_api_health(self, api_key: Optional[str] = None) -> Dict[str, Any]:
        """Lightweight 1-token ping to verify live Gemini API key health and billing status."""
        key = self._resolve_api_key(api_key)
        if not key:
            self.api_status = "Offline"
            self.api_status_detail = "No API Key — Free Built-In Mode Active"
            self._notify()
            return self.get_snapshot()

        try:
            from google import genai

            client = genai.Client(api_key=key)
            inter = client.interactions.create(
                model="gemini-3.5-flash-lite",
                input="ok",
                store=False,
            )
            self.record_interaction("gemini-3.5-flash-lite", "health_probe", inter)
            self.api_status = "Active"
            self.api_status_detail = "Gemini API Connected & Funded"
        except Exception as e:
            self.record_error("gemini-3.5-flash-lite", "health_probe", e)

        self._notify()
        return self.get_snapshot()

    def record_interaction(
        self,
        model_name: str,
        operation: str,
        interaction: Any = None,
        images_generated: int = 0,
        video_seconds: float = 0.0,
        prompt_chars: int = 0,
        output_chars: int = 0,
    ) -> Dict[str, Any]:
        """Record a successful Gemini Interactions API call and compute its token/media cost."""
        in_tok = 0
        out_tok = 0
        usage = getattr(interaction, "usage", None) if interaction is not None else None
        if usage is not None:
            in_tok = int(
                getattr(usage, "input_tokens", 0)
                or getattr(usage, "prompt_token_count", 0)
                or 0
            )
            out_tok = int(
                getattr(usage, "output_tokens", 0)
                or getattr(usage, "candidates_token_count", 0)
                or 0
            )
        if in_tok == 0 and prompt_chars > 0:
            in_tok = max(1, prompt_chars // 4)
        if out_tok == 0 and output_chars > 0:
            out_tok = max(1, output_chars // 4)
        elif out_tok == 0 and interaction is not None:
            out_txt = getattr(interaction, "output_text", "") or ""
            if out_txt:
                out_tok = max(1, len(out_txt) // 4)

        in_rate, out_rate = self.TOKEN_RATES_PER_1M.get(model_name, (0.15, 0.60))
        token_cost = (in_tok / 1_000_000.0) * in_rate + (out_tok / 1_000_000.0) * out_rate
        img_cost = images_generated * self.IMAGE_RATES.get(model_name, 0.02)
        vid_cost = video_seconds * self.VIDEO_RATE_PER_SEC_720P
        total_cost = round(token_cost + img_cost + vid_cost, 5)

        self.api_status = "Active"
        self.api_status_detail = "Gemini API Connected & Active"
        self.session_tokens += in_tok + out_tok
        self.session_images += int(images_generated)
        self.session_video_seconds += float(video_seconds)
        self.session_cost_usd = round(self.session_cost_usd + total_cost, 4)
        self.session_calls += 1

        try:
            record_usage_event(
                model_name=model_name,
                operation=operation,
                input_tokens=in_tok,
                output_tokens=out_tok,
                images_generated=images_generated,
                video_seconds=video_seconds,
                estimated_cost_usd=total_cost,
                status="ok",
            )
        except Exception as e:
            logger.debug("Could not log usage event to SQLite: %s", e)

        self._notify()
        return self.get_snapshot()

    def record_error(self, model_name: str, operation: str, error: Exception | str) -> Dict[str, Any]:
        """Inspect API error to update live billing/key health status immediately."""
        err_str = str(error)
        err_lower = err_str.lower()

        if "402" in err_str or "prepayment credits are depleted" in err_lower or "resource_exhausted" in err_lower:
            self.api_status = "Depleted_402"
            self.api_status_detail = "Credits Depleted (HTTP 402) — Free Mode Active"
            status_code = "error_402"
        elif any(k in err_lower for k in ("401", "403", "api_key_invalid", "invalid api key", "permission_denied")):
            self.api_status = "Invalid_Key"
            self.api_status_detail = "Invalid API Key — Check Settings"
            status_code = "error_auth"
        else:
            self.api_status = "Offline"
            self.api_status_detail = "API Unreachable — Free Mode Active"
            status_code = "error_net"

        try:
            record_usage_event(
                model_name=model_name,
                operation=operation,
                status=status_code,
            )
        except Exception:
            pass

        self._notify()
        return self.get_snapshot()

    def estimate_render_cost(
        self,
        scenes: Optional[List[Dict[str, Any]]] = None,
        render_mode: str = "smart_hybrid",
        image_model: str = "gemini-nano-banana-2.1",
        omni_resolution: str = "720p",
    ) -> Dict[str, Any]:
        """Calculate upfront estimated USD cost and media counts before the user clicks Render."""
        # If credits are depleted or offline, rendering uses the free local procedural engine ($0.00)
        if self.api_status in ("Depleted_402", "Offline", "Invalid_Key"):
            return {
                "cost_usd": 0.0,
                "uncached_keyframes": 0,
                "uncached_omni_seconds": 0.0,
                "cached_scenes": 0,
                "total_scenes": len(scenes) if scenes else 6,
                "badge": "$0.00 (Free Built-In Mode)",
                "summary": "Using free built-in procedural 3D cutaway graphics (0 API credits used).",
            }

        scene_list = scenes if scenes else [{"scene_idx": i, "duration": 7.5} for i in range(6)]
        total_scenes = len(scene_list)
        cached_count = 0
        uncached_keyframes = 0
        uncached_omni_sec = 0.0

        for idx, sc in enumerate(scene_list):
            has_hash = bool(sc.get("scene_hash"))
            img_ok = bool(sc.get("image_path") and os.path.exists(str(sc.get("image_path"))))
            if has_hash and img_ok:
                cached_count += 1
                continue

            override = sc.get("render_mode", "auto")
            if override in ("omni_video", "keyframe"):
                eff = override
            elif render_mode == "full_omni":
                eff = "omni_video"
            elif render_mode == "keyframe_only":
                eff = "keyframe"
            else:
                climax_idx = max(1, total_scenes // 2)
                eff = "omni_video" if idx in (0, climax_idx) else "keyframe"

            uncached_keyframes += 1
            if eff == "omni_video":
                dur = min(10.0, max(4.0, float(sc.get("duration", 7.5))))
                uncached_omni_sec += dur

        img_rate = self.IMAGE_RATES.get(image_model, 0.02)
        vid_rate = self.VIDEO_RATE_PER_SEC_1080P if omni_resolution == "1080p" else self.VIDEO_RATE_PER_SEC_720P
        est_cost = round(uncached_keyframes * img_rate + uncached_omni_sec * vid_rate, 2)

        if cached_count == total_scenes and total_scenes > 0:
            badge = "Est. $0.00 (All Scenes Cached)"
        else:
            badge = f"Est. ~${est_cost:.2f}"

        return {
            "cost_usd": est_cost,
            "uncached_keyframes": uncached_keyframes,
            "uncached_omni_seconds": round(uncached_omni_sec, 1),
            "cached_scenes": cached_count,
            "total_scenes": total_scenes,
            "badge": badge,
            "summary": (
                f"{uncached_keyframes} keyframes + {int(uncached_omni_sec)}s Omni video "
                f"({cached_count}/{total_scenes} cached)"
            ),
        }

    def get_snapshot(self) -> Dict[str, Any]:
        """Return combined live session and all-time SQLite telemetry."""
        try:
            all_time = get_usage_summary()
        except Exception:
            all_time = {
                "total_tokens": 0,
                "total_images": 0,
                "total_video_seconds": 0.0,
                "total_cost_usd": 0.0,
                "total_calls": 0,
            }

        return {
            "api_status": self.api_status,
            "api_status_detail": self.api_status_detail,
            "session_tokens": self.session_tokens,
            "session_images": self.session_images,
            "session_video_seconds": round(self.session_video_seconds, 1),
            "session_cost_usd": round(self.session_cost_usd, 4),
            "session_calls": self.session_calls,
            "all_time_tokens": int(all_time.get("total_tokens", 0)),
            "all_time_images": int(all_time.get("total_images", 0)),
            "all_time_video_seconds": round(float(all_time.get("total_video_seconds", 0.0)), 1),
            "all_time_cost_usd": round(float(all_time.get("total_cost_usd", 0.0)), 4),
        }


usage_tracker = UsageTracker()
