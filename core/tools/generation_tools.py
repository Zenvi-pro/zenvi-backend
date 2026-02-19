"""
Server-side video generation tools (Runware/Vidu).
"""

from logger import log


def generate_video(prompt: str, duration_seconds: int = 4, resolution: str = "720p") -> str:
    """Generate a video using Runware/Vidu API."""
    try:
        from core.generation.runware_client import runware_generate_video, download_video_to_path
        from config import get_settings
        import tempfile
        import os

        settings = get_settings()
        api_key = settings.runware_api_key
        if not api_key:
            return "Error: Runware API key not configured."

        result = runware_generate_video(
            api_key=api_key,
            prompt=prompt,
            duration=duration_seconds,
        )
        if result and result.get("url"):
            output_dir = tempfile.mkdtemp(prefix="zenvi_gen_")
            output_path = os.path.join(output_dir, "generated_video.mp4")
            download_video_to_path(result["url"], output_path)
            return f"Video generated: {output_path}"
        return "Error: Video generation failed — no URL returned."
    except Exception as e:
        log.error("Video generation failed: %s", e)
        return f"Error: {e}"


def get_generation_tools_for_langchain():
    from langchain_core.tools import tool

    @tool
    def generate_video_tool(prompt: str, duration_seconds: int = 4) -> str:
        """Generate a video from a text prompt using AI video generation."""
        return generate_video(prompt, duration_seconds)

    return [generate_video_tool]
