"""
Suno music generation tools for LangChain agent.

- generate_music_tool: server-side (generates music via Suno API, downloads MP3)
- add_music_to_timeline_tool: frontend-delegated (adds file to Qt timeline)
- test_suno_token_tool: server-side (validates Suno token)
"""

import os
import tempfile

from logger import log


def generate_music(
    topic: str = "",
    tags: str = "",
    prompt: str = "",
    make_instrumental: bool = True,
) -> str:
    """Generate music via Suno and return the local MP3 path."""
    try:
        from config import get_settings
        from core.providers.suno_client import generate_wait_download_mp3, SunoError

        settings = get_settings()
        token = settings.suno_token
        if not token:
            return "Error: Suno token not configured. Set SUNO_TOKEN in .env."

        # Build destination path
        out_dir = tempfile.mkdtemp(prefix="zenvi_suno_")
        safe_name = (topic or prompt or "music")[:40].replace(" ", "_").replace("/", "_")
        dest_path = os.path.join(out_dir, f"{safe_name}.mp3")

        final_clip = generate_wait_download_mp3(
            token=token,
            topic=topic,
            tags=tags,
            prompt=prompt,
            make_instrumental=make_instrumental,
            dest_path=dest_path,
        )

        title = final_clip.get("title", "Suno Music")
        return f"Music generated: {dest_path} (title: {title})"

    except Exception as e:
        log.error("Music generation failed: %s", e, exc_info=True)
        return f"Error: {e}"


def test_suno_token() -> str:
    """Validate the Suno token."""
    try:
        from config import get_settings
        from core.providers.suno_client import suno_get_clips, SunoError

        settings = get_settings()
        token = settings.suno_token
        if not token:
            return "Error: Suno token not configured. Set SUNO_TOKEN in .env."

        # Try a lightweight API call to validate
        try:
            suno_get_clips(token=token, ids=["test_nonexistent"], timeout_seconds=10.0)
        except SunoError as e:
            if e.status_code == 401:
                return "Error: Invalid Suno token."
            # 404 or other errors mean the token works but clip doesn't exist = token valid
            pass

        return "Suno token is valid."
    except Exception as e:
        return f"Error: {e}"


# Frontend-delegated stub
_NO_FRONTEND = "Error: This tool requires the frontend. Use via WebSocket chat."


def add_music_to_timeline(file_path: str = "", position_seconds: str = "", track: str = "") -> str:
    """Add a generated music file to the timeline. (Frontend-delegated)"""
    return _NO_FRONTEND


def get_music_tools_for_langchain():
    """Return Suno music tools for LangChain."""
    from langchain_core.tools import tool

    @tool
    def generate_music_and_add_to_timeline_tool(
        topic: str = "",
        tags: str = "",
        prompt: str = "",
        make_instrumental: bool = True,
    ) -> str:
        """Generate background music with Suno AI and add to timeline. Use topic+tags for simple mode, or prompt for custom lyrics. Prefer instrumental for background music."""
        return generate_music(topic=topic, tags=tags, prompt=prompt, make_instrumental=make_instrumental)

    @tool
    def test_suno_token_tool() -> str:
        """Test if the Suno music API token is valid."""
        return test_suno_token()

    @tool
    def add_music_to_timeline_tool(file_path: str = "", position_seconds: str = "", track: str = "") -> str:
        """Add a generated music file to the timeline at a given position."""
        return add_music_to_timeline(file_path, position_seconds, track)

    return [generate_music_and_add_to_timeline_tool, test_suno_token_tool, add_music_to_timeline_tool]


# Tool names that need frontend execution
MUSIC_FRONTEND_TOOL_NAMES = {
    "add_music_to_timeline_tool",
}
