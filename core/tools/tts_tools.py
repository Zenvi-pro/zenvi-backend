"""
TTS (Text-to-Speech) LangChain tools for the voice/music agent.

Server-side tools call the OpenAI TTS API directly.
Frontend-delegated tools add the generated audio to the OpenShot timeline.
"""

from __future__ import annotations

import os
import tempfile
from typing import List

from langchain_core.tools import StructuredTool

from config import get_settings
from logger import log
from core.providers.openai_tts_client import (
    TTSError,
    openai_tts_generate,
    chunk_text_for_tts,
    concatenate_audio_ffmpeg,
)


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

TTS_FRONTEND_TOOL_NAMES = {"add_tts_audio_to_timeline_tool"}

_NO_FRONTEND = (
    "This tool manipulates the OpenShot timeline and must be executed by the "
    "desktop front-end.  The backend returns this sentinel so the WebSocket "
    "agent runner knows to delegate."
)

# ---------------------------------------------------------------------------
# Server-side tools
# ---------------------------------------------------------------------------


def generate_tts_audio(
    text: str,
    voice: str = "alloy",
    model: str = "tts-1",
    speed: float = 1.0,
) -> str:
    """Generate speech audio from text using OpenAI TTS. Returns the path to the generated audio file.

    Args:
        text: The text to convert to speech.
        voice: Voice to use. Options: alloy, echo, fable, onyx, nova, shimmer.
        model: TTS model. Options: tts-1, tts-1-hd.
        speed: Speech speed (0.25 to 4.0, default 1.0).
    """
    settings = get_settings()
    api_key = settings.openai_api_key
    if not api_key:
        return "Error: OpenAI API key not configured in backend .env"

    text = (text or "").strip()
    if not text:
        return "Error: No text provided for TTS generation."

    try:
        chunks = chunk_text_for_tts(text, max_chars=4096)

        if len(chunks) <= 1:
            # Single chunk – generate directly
            out_dir = tempfile.mkdtemp(prefix="zenvi_tts_")
            out_path = os.path.join(out_dir, "tts_output.mp3")

            openai_tts_generate(
                api_key=api_key,
                text=text,
                voice=voice,
                model=model,
                speed=speed,
                output_path=out_path,
            )
            return f"TTS audio generated successfully: {out_path}"
        else:
            # Multiple chunks – generate each, then concatenate
            out_dir = tempfile.mkdtemp(prefix="zenvi_tts_")
            chunk_paths: List[str] = []

            for idx, chunk in enumerate(chunks):
                chunk_path = os.path.join(out_dir, f"chunk_{idx:03d}.mp3")
                openai_tts_generate(
                    api_key=api_key,
                    text=chunk,
                    voice=voice,
                    model=model,
                    speed=speed,
                    output_path=chunk_path,
                )
                chunk_paths.append(chunk_path)
                log.info("Generated TTS chunk %d/%d", idx + 1, len(chunks))

            final_path = os.path.join(out_dir, "tts_output.mp3")
            ok, err = concatenate_audio_ffmpeg(chunk_paths, final_path)

            if not ok:
                return f"Error concatenating audio chunks: {err}"

            # Clean up chunk files
            for p in chunk_paths:
                try:
                    os.remove(p)
                except OSError:
                    pass

            return f"TTS audio generated successfully ({len(chunks)} chunks merged): {final_path}"

    except TTSError as exc:
        log.error("TTS generation failed: %s", exc)
        return f"Error: {exc}"
    except Exception as exc:
        log.error("TTS generation unexpected error: %s", exc, exc_info=True)
        return f"Error: {exc}"


def test_openai_tts_api_key() -> str:
    """Test if the configured OpenAI API key is valid for TTS."""
    settings = get_settings()
    api_key = settings.openai_api_key
    if not api_key:
        return "Error: OpenAI API key not configured in backend .env"

    try:
        out_dir = tempfile.mkdtemp(prefix="zenvi_tts_test_")
        test_path = os.path.join(out_dir, "test.mp3")

        openai_tts_generate(
            api_key=api_key,
            text="Hello",
            voice="alloy",
            model="tts-1",
            speed=1.0,
            output_path=test_path,
        )

        # Clean up test file
        try:
            os.remove(test_path)
            os.rmdir(out_dir)
        except OSError:
            pass

        return "OpenAI TTS API key is valid and working."

    except TTSError as exc:
        return f"OpenAI TTS API key test failed: {exc}"
    except Exception as exc:
        return f"Error testing TTS key: {exc}"


# ---------------------------------------------------------------------------
# Frontend-delegated tools (timeline manipulation)
# ---------------------------------------------------------------------------


def add_tts_audio_to_timeline(
    audio_path: str,
    track: int = 0,
    position: float = 0.0,
) -> str:
    """Add a generated TTS audio file to the OpenShot timeline.

    Args:
        audio_path: Path to the audio file to add.
        track: Track number (0-based).
        position: Position in seconds on the timeline.
    """
    return _NO_FRONTEND


# ---------------------------------------------------------------------------
# Tool factory
# ---------------------------------------------------------------------------


def get_tts_tools_for_langchain() -> List[StructuredTool]:
    """Return all TTS-related LangChain tools."""
    return [
        StructuredTool.from_function(
            func=generate_tts_audio,
            name="generate_tts_audio_tool",
            description=(
                "Generate speech audio from text using OpenAI TTS API. "
                "Supports voices: alloy, echo, fable, onyx, nova, shimmer. "
                "Models: tts-1 (fast) or tts-1-hd (high quality). "
                "Returns the file path to the generated MP3. "
                "For long text, automatically splits and concatenates."
            ),
        ),
        StructuredTool.from_function(
            func=test_openai_tts_api_key,
            name="test_openai_tts_api_key_tool",
            description="Test if the configured OpenAI API key works for TTS.",
        ),
        StructuredTool.from_function(
            func=add_tts_audio_to_timeline,
            name="add_tts_audio_to_timeline_tool",
            description=(
                "Add a generated TTS audio file to the OpenShot timeline at the "
                "specified track and position. Must be run in the desktop frontend."
            ),
        ),
    ]
