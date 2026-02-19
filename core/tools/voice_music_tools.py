"""
Stub tools for voice overlays and music generation.
Ported from zenvi-core verbatim.
"""

from logger import log


def tag_videos_via_azure(api_url: str = "", api_key: str = "") -> str:
    if not (api_url and api_key):
        return "Azure tagging API is not configured."
    return "Azure tagging not yet implemented."


def generate_storyline_from_tags() -> str:
    return "Storyline-from-tags is not yet implemented."


def generate_voice_overlay(text: str, voice_id: str = "default") -> str:
    if not (text or "").strip():
        return "Error: text is required for voice overlay."
    return "Voice overlay is not yet configured."


def generate_music(theme: str, duration_seconds: int = 60) -> str:
    if not (theme or "").strip():
        return "Error: theme is required."
    return "Music generation is not yet configured."


def get_voice_music_tools_for_langchain():
    from langchain_core.tools import tool

    @tool
    def tag_videos_via_azure_tool(api_url: str = "", api_key: str = "") -> str:
        """Tag project videos using the Azure tagging API."""
        return tag_videos_via_azure(api_url=api_url, api_key=api_key)

    @tool
    def generate_storyline_from_tags_tool() -> str:
        """Generate a storyline/script from the current video tags."""
        return generate_storyline_from_tags()

    @tool
    def generate_voice_overlay_tool(text: str, voice_id: str = "default") -> str:
        """Generate speech audio from text for voice-over."""
        return generate_voice_overlay(text=text, voice_id=voice_id)

    @tool
    def generate_music_tool(theme: str, duration_seconds: int = 60) -> str:
        """Generate background music."""
        return generate_music(theme=theme, duration_seconds=duration_seconds)

    return [tag_videos_via_azure_tool, generate_storyline_from_tags_tool, generate_voice_overlay_tool, generate_music_tool]
