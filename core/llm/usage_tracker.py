"""
Zenvi Backend API usage tracker.

Records API usage events locally in a JSON buffer, then flushes them to
Supabase in batches.  This keeps the hot-path latency-free: AI calls are
never blocked waiting for a network write.

Ported from zenvi-core's usage_tracker.py (commit e49b9580c) and adapted
for the backend:
  - No dependency on classes.info — uses ~/.zenvi-backend/ for storage
  - No AuthManager — token is forwarded from the frontend via set_token()
  - SUPABASE_URL / SUPABASE_ANON_KEY come from config.py

Flush triggers
--------------
  - Every FLUSH_INTERVAL seconds (background timer thread)
  - After FLUSH_THRESHOLD records accumulate
  - Explicitly via flush() — call from app shutdown handler

Thread safety
-------------
  All public methods are protected by a single re-entrant lock.
  The flush runs in a daemon thread so it never blocks request handlers.
"""

import json
import logging
import os
import threading
import time
from datetime import datetime, timezone

import requests

log = logging.getLogger(__name__)

_DATA_DIR = os.path.expanduser("~/.zenvi-backend")
BUFFER_FILE = os.path.join(_DATA_DIR, "usage_buffer.json")
FLUSH_INTERVAL = 300    # seconds between automatic flushes
FLUSH_THRESHOLD = 20    # flush after this many buffered records


class UsageTracker:
    """Singleton usage tracker — one instance shared across the whole backend."""

    _instance: "UsageTracker | None" = None
    _lock = threading.Lock()

    @classmethod
    def instance(cls) -> "UsageTracker":
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = cls()
        return cls._instance

    def __init__(self) -> None:
        self._buf_lock = threading.RLock()
        self._buffer: list[dict] = []
        self._token: str = ""
        self._load_buffer()
        self._start_timer()

    # ── Public API ─────────────────────────────────────────────────────────────

    def set_token(self, token: str) -> None:
        """Store the current user's JWT, forwarded from the frontend request."""
        self._token = token or ""

    def record(
        self,
        provider: str,
        model: str,
        operation: str,
        input_tokens: int = 0,
        output_tokens: int = 0,
        units: int = 1,
    ) -> None:
        """
        Record a single API usage event.  Thread-safe; never blocks.

        Parameters
        ----------
        provider      : 'openai' | 'anthropic' | 'runware' | 'google'
        model         : model name, e.g. 'gpt-4o-mini'
        operation     : 'chat' | 'tts' | 'video_generation' | 'vision'
        input_tokens  : prompt / input tokens consumed
        output_tokens : completion / output tokens produced
        units         : for flat-rate APIs (1 Runware generation = 1 unit)
        """
        try:
            from config import get_settings
            app_version = get_settings().get("app-version", "unknown")
        except Exception:
            app_version = "unknown"

        event = {
            "provider": provider,
            "model": model or "",
            "operation": operation,
            "input_tokens": int(input_tokens),
            "output_tokens": int(output_tokens),
            "units": int(units),
            "app_version": app_version,
            "recorded_at": datetime.now(timezone.utc).isoformat(),
        }

        with self._buf_lock:
            self._buffer.append(event)
            self._save_buffer()
            if len(self._buffer) >= FLUSH_THRESHOLD:
                threading.Thread(
                    target=self.flush, daemon=True, name="usage-flush"
                ).start()

    def flush(self) -> bool:
        """
        Upload all buffered records to Supabase and clear the buffer.
        Safe to call from any thread.  Returns True on success.
        """
        with self._buf_lock:
            if not self._buffer:
                return True
            batch = list(self._buffer)

        token = self._token
        if not token:
            log.debug("Usage flush skipped — no auth token set.")
            return False

        try:
            from config import get_settings
            cfg = get_settings()
            supabase_url = cfg.supabase_url
            anon_key = cfg.supabase_anon_key
        except Exception as exc:
            log.warning("Usage flush: could not load config: %s", exc)
            return False

        if not anon_key:
            log.debug("Usage flush skipped — SUPABASE_ANON_KEY not configured.")
            return False

        headers = {
            "apikey": anon_key,
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
        }

        try:
            resp = requests.post(
                f"{supabase_url}/rest/v1/rpc/batch_record_api_usage",
                headers=headers,
                json={"records": batch},
                timeout=15,
            )
            if resp.status_code == 200:
                with self._buf_lock:
                    del self._buffer[: len(batch)]
                    self._save_buffer()
                log.debug("Flushed %d usage records.", len(batch))
                return True
            else:
                log.warning(
                    "Usage flush failed (%s): %s", resp.status_code, resp.text[:200]
                )
        except requests.RequestException as exc:
            log.warning("Usage flush network error: %s", exc)

        return False

    def check_allowed(self, estimated_cost: float = 0.0) -> bool:
        """
        Ask Supabase if the current user is still within their monthly budget.
        Returns True if allowed (or if the check fails — fail open).
        """
        token = self._token
        if not token:
            return True  # unauthenticated — let through, quota not enforced

        try:
            from config import get_settings
            cfg = get_settings()
            supabase_url = cfg.supabase_url
            anon_key = cfg.supabase_anon_key
        except Exception:
            return True

        if not anon_key:
            return True

        headers = {
            "apikey": anon_key,
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
        }
        try:
            resp = requests.post(
                f"{supabase_url}/rest/v1/rpc/check_usage_allowed",
                headers=headers,
                json={"p_estimated_cost": round(estimated_cost, 6)},
                timeout=5,
            )
            if resp.status_code == 200:
                result = resp.json()
                if isinstance(result, list):
                    return bool(result[0]) if result else True
                return bool(result)
        except Exception as exc:
            log.debug("check_allowed request failed (fail open): %s", exc)

        return True  # fail open

    # ── Internal helpers ───────────────────────────────────────────────────────

    def _load_buffer(self) -> None:
        try:
            if os.path.exists(BUFFER_FILE):
                with open(BUFFER_FILE, "r", encoding="utf-8") as fh:
                    data = json.load(fh)
                    if isinstance(data, list):
                        self._buffer = data
                        if self._buffer:
                            log.info(
                                "Restored %d buffered usage records from disk.",
                                len(self._buffer),
                            )
        except Exception as exc:
            log.warning("Could not load usage buffer: %s", exc)

    def _save_buffer(self) -> None:
        try:
            os.makedirs(_DATA_DIR, exist_ok=True)
            with open(BUFFER_FILE, "w", encoding="utf-8") as fh:
                json.dump(self._buffer, fh)
        except Exception as exc:
            log.warning("Could not save usage buffer: %s", exc)

    def _start_timer(self) -> None:
        def _tick():
            while True:
                time.sleep(FLUSH_INTERVAL)
                try:
                    self.flush()
                except Exception as exc:
                    log.warning("Periodic usage flush error: %s", exc)

        threading.Thread(target=_tick, daemon=True, name="usage-timer").start()
