"""
OpenShot timeline tools for the LangChain agent.

These tools are registered with the LLM so it can call them. Tools that
manipulate the live Qt application (project state, playback, timeline) are
delegated to the frontend via WebSocket. Tools that run purely server-side
(search, video generation, ffmpeg processing) execute locally.
"""

from core.tools.openshot.project_tools import get_project_tools
from core.tools.openshot.playback_tools import get_playback_tools
from core.tools.openshot.timeline_tools import get_timeline_tools
from core.tools.openshot.export_tools import get_export_tools
from core.tools.openshot.clip_tools import get_clip_tools
from core.tools.openshot.search_clip_tools import get_search_clip_tools
from core.tools.openshot.video_gen_tools import get_video_gen_tools
from core.tools.openshot.transitions_tools import get_transitions_tools


def get_all_openshot_tools():
    """Return every OpenShot tool for LLM binding."""
    tools = []
    tools.extend(get_project_tools())
    tools.extend(get_playback_tools())
    tools.extend(get_timeline_tools())
    tools.extend(get_export_tools())
    tools.extend(get_clip_tools())
    tools.extend(get_search_clip_tools())
    tools.extend(get_video_gen_tools())
    tools.extend(get_transitions_tools())
    return tools


# Names of tools that MUST execute on the frontend (they call _get_app() / Qt).
FRONTEND_TOOL_NAMES = {
    # project_tools
    "get_project_info_tool",
    "list_files_tool",
    "list_clips_tool",
    "list_layers_tool",
    "list_markers_tool",
    "new_project_tool",
    "save_project_tool",
    "open_project_tool",
    # playback_tools
    "play_tool",
    "go_to_start_tool",
    "go_to_end_tool",
    "undo_tool",
    "redo_tool",
    # timeline_tools
    "add_track_tool",
    "add_marker_tool",
    "remove_clip_tool",
    "zoom_in_tool",
    "zoom_out_tool",
    "center_on_playhead_tool",
    "import_files_tool",
    # export_tools
    "export_video_tool",
    "get_export_settings_tool",
    "set_export_setting_tool",
    "export_video_now_tool",
    # clip_tools
    "get_file_info_tool",
    "split_file_add_clip_tool",
    "add_clip_to_timeline_tool",
    "slice_clip_at_playhead_tool",
    # search_clip_tools
    "search_selected_clip_scenes_tool",
    "slice_selected_clip_at_best_match_tool",
    # video_gen_tools
    "generate_video_and_add_to_timeline_tool",
    "insert_kling_v2v_clip_into_selected_clip_tool",
    "generate_transition_clip_tool",
    "replace_object_in_selected_clip_tool",
    # transitions_tools
    "list_transitions_tool",
    "search_transitions_tool",
    "add_transition_between_clips_tool",
    "add_transition_to_clip_tool",
    # tts_tools (frontend-delegated: timeline insertion)
    "add_tts_audio_to_timeline_tool",
    # director_tools (frontend-delegated: project analysis via Qt)
    "analyze_timeline_structure_tool",
    "analyze_pacing_tool",
    "analyze_audio_levels_tool",
    "analyze_transitions_tool",
    "analyze_clip_content_tool",
    "analyze_music_sync_tool",
    "get_project_metadata_tool",
    "analyze_clip_visual_content_tool",
    # remotion_tools (frontend-delegated: download from Supabase + import to project)
    "fetch_remotion_video_from_supabase_tool",
}
