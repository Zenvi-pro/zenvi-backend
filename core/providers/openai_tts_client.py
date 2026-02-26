"""
OpenAI Text-to-Speech API client.

This module is logic-only (no Qt). Ported from core/src/classes/tts_generation/openai_tts_client.py.
"""

from __future__ import annotations

import os
import re
import subprocess
from dataclasses import dataclass
from typing import List, Optional, Tuple

from logger import log


@dataclass(frozen=True)
class TTSError(Exception):
    """Structured error for TTS API failures."""
    message: str
    status_code: Optional[int] = None
    detail: Optional[str] = None

    def __str__(self) -> str:
        bits = [self.message]
        if self.status_code is not None:
            bits.append(f"(status={self.status_code})")
        if self.detail:
            bits.append(self.detail)
        return " ".join(bits)


def _auth_headers(api_key: str) -> dict:
    key = (api_key or "").strip()
    if not key:
        raise TTSError("Missing OpenAI API key.")
    return {"Authorization": f"Bearer {key}"}


def openai_tts_generate(
    *,
    api_key: str,
    text: str,
    voice: str = "alloy",
    model: str = "tts-1",
    speed: float = 1.0,
    output_path: str,
    timeout_seconds: float = 60.0,
) -> None:
    """Generate speech from text using OpenAI TTS API. Raises TTSError on failure."""
    text_cleaned = (text or "").strip()
    if not text_cleaned:
        raise TTSError("Text is required for TTS generation.")

    if len(text_cleaned) > 4096:
        raise TTSError(
            f"Text too long ({len(text_cleaned)} chars). Maximum is 4096 per request.",
            detail="Use chunk_text_for_tts() to split long text.",
        )

    voice = (voice or "alloy").strip().lower()
    valid_voices = ["alloy", "echo", "fable", "onyx", "nova", "shimmer"]
    if voice not in valid_voices:
        raise TTSError(f"Invalid voice '{voice}'. Must be one of: {', '.join(valid_voices)}")

    model = (model or "tts-1").strip().lower()
    valid_models = ["tts-1", "tts-1-hd"]
    if model not in valid_models:
        raise TTSError(f"Invalid model '{model}'. Must be one of: {', '.join(valid_models)}")

    speed = float(speed)
    if not (0.25 <= speed <= 4.0):
        raise TTSError(f"Invalid speed {speed}. Must be between 0.25 and 4.0.")

    path = (output_path or "").strip()
    if not path:
        raise TTSError("output_path is required.")

    import requests

    url = "https://api.openai.com/v1/audio/speech"
    headers = _auth_headers(api_key)
    headers["Content-Type"] = "application/json"

    payload = {"model": model, "input": text_cleaned, "voice": voice, "speed": speed}

    try:
        log.debug("OpenAI TTS request: %d chars, voice=%s, model=%s", len(text_cleaned), voice, model)
        resp = requests.post(url, headers=headers, json=payload, timeout=float(timeout_seconds))
    except requests.RequestException as exc:
        raise TTSError(f"OpenAI TTS request failed: {exc}") from exc

    if resp.status_code == 401:
        raise TTSError("Authentication failed. Check your OpenAI API key.", status_code=401)
    elif resp.status_code == 429:
        raise TTSError("Rate limit exceeded. Please wait.", status_code=429)
    elif resp.status_code == 400:
        detail = ""
        try:
            error_data = resp.json()
            if isinstance(error_data, dict) and "error" in error_data:
                error_msg = error_data.get("error", {})
                detail = error_msg.get("message", "") if isinstance(error_msg, dict) else str(error_msg)
        except Exception:
            detail = (resp.text or "")[:500]
        raise TTSError("Bad request.", status_code=400, detail=detail)
    elif resp.status_code < 200 or resp.status_code >= 300:
        raise TTSError("OpenAI TTS request failed.", status_code=resp.status_code, detail=(resp.text or "")[:500])

    try:
        with open(path, "wb") as f:
            f.write(resp.content)
        log.info("OpenAI TTS generated: %s (%d bytes)", path, len(resp.content))
    except OSError as exc:
        raise TTSError(f"Could not write audio file: {exc}") from exc


def chunk_text_for_tts(text: str, max_chars: int = 4096) -> List[str]:
    """Split text into chunks suitable for TTS API, splitting on sentence boundaries."""
    text_cleaned = (text or "").strip()
    if not text_cleaned:
        return []
    if len(text_cleaned) <= max_chars:
        return [text_cleaned]

    chunks = []
    sentences = re.split(r'([.!?])\s+', text_cleaned)

    reconstructed = []
    for i in range(0, len(sentences), 2):
        if i + 1 < len(sentences):
            reconstructed.append(sentences[i] + sentences[i + 1])
        else:
            if sentences[i].strip():
                reconstructed.append(sentences[i])

    current_chunk = ""

    for sentence in reconstructed:
        sentence = sentence.strip()
        if not sentence:
            continue

        if len(sentence) > max_chars:
            if current_chunk:
                chunks.append(current_chunk.strip())
                current_chunk = ""

            parts = sentence.split(',')
            temp_part = ""

            for part in parts:
                part = part.strip()
                if not part:
                    continue
                if len(part) > max_chars:
                    if temp_part:
                        chunks.append(temp_part.strip())
                        temp_part = ""
                    words = part.split()
                    word_chunk = ""
                    for word in words:
                        if len(word_chunk) + len(word) + 1 <= max_chars:
                            word_chunk += (" " if word_chunk else "") + word
                        else:
                            if word_chunk:
                                chunks.append(word_chunk.strip())
                            word_chunk = word
                    if word_chunk:
                        temp_part = word_chunk
                elif len(temp_part) + len(part) + 2 <= max_chars:
                    temp_part += (", " if temp_part else "") + part
                else:
                    if temp_part:
                        chunks.append(temp_part.strip())
                    temp_part = part

            if temp_part:
                current_chunk = temp_part
            continue

        potential_chunk = current_chunk + (" " if current_chunk else "") + sentence
        if len(potential_chunk) <= max_chars:
            current_chunk = potential_chunk
        else:
            if current_chunk:
                chunks.append(current_chunk.strip())
            current_chunk = sentence

    if current_chunk:
        chunks.append(current_chunk.strip())

    log.info("Chunked text into %d chunks (max %d chars each)", len(chunks), max_chars)
    return chunks


def concatenate_audio_ffmpeg(audio_paths: List[str], output_path: str) -> Tuple[bool, Optional[str]]:
    """Concatenate audio files using ffmpeg concat demuxer."""
    if not audio_paths or not output_path:
        return False, "No inputs or output path"

    if len(audio_paths) == 1:
        try:
            import shutil
            shutil.copy(audio_paths[0], output_path)
            return True, None
        except Exception as e:
            return False, f"Failed to copy file: {e}"

    list_dir = os.path.dirname(output_path)
    list_path = os.path.join(list_dir, f"concat_list_{os.getpid()}.txt")

    try:
        with open(list_path, "w", encoding="utf-8") as f:
            for p in audio_paths:
                p_abs = os.path.abspath(p)
                p_escaped = p_abs.replace("'", "'\\''")
                f.write(f"file '{p_escaped}'\n")

        result = subprocess.run(
            ["ffmpeg", "-y", "-f", "concat", "-safe", "0", "-i", list_path, "-c", "copy", output_path],
            capture_output=True, text=True, timeout=600,
        )

        if result.returncode != 0:
            error = result.stderr or result.stdout or "ffmpeg failed"
            log.error("ffmpeg concatenation failed: %s", error)
            return False, error

        log.info("Concatenated %d audio files to %s", len(audio_paths), output_path)
        return True, None

    except subprocess.TimeoutExpired:
        return False, "ffmpeg timed out"
    except FileNotFoundError:
        return False, "ffmpeg not found."
    except Exception as e:
        log.error("concatenate_audio_ffmpeg: %s", e, exc_info=True)
        return False, str(e)
    finally:
        if os.path.isfile(list_path):
            try:
                os.remove(list_path)
            except Exception:
                pass
