"""
Tool Registry for Directors.

Provides a catalog of available tools with signatures for LLM plan generation.
Maps vision analysis scores to executable tool parameters.
Pure logic — no Qt or backend-specific dependencies.

Ported from core/src/classes/ai_directors/tool_registry.py.
"""

from typing import Dict, Any
from logger import log


class ToolRegistry:

    @staticmethod
    def get_tool_catalog() -> str:
        """Returns formatted tool catalog for LLM consumption."""
        return """
AVAILABLE TOOLS FOR PLAN EXECUTION:

VIDEO AGENT TOOLS:
------------------
add_effect(clip_id: str, effect_type: str, **parameters)
  Types: brightness_contrast, color_correction, saturation, blur
  Parameters: brightness (0.5-2.0), contrast (0.5-2.0), saturation (0.0-2.0)

adjust_audio(clip_id: str, volume: float, fade_in: float = 0.0, fade_out: float = 0.0)
  volume: 0.0-2.0

split_clip(clip_id: str, split_time: float)
  split_time: seconds from clip start

add_transition(clip1_id: str, clip2_id: str, transition_name: str, duration: float)
  transition_name: fade, dissolve, wipe_left, wipe_right, circle_in, circle_out
  duration: 0.5-3.0s

remove_clip(clip_id: str)

reorder_clip(clip_id: str, new_position: float, new_layer: int)

TRANSITIONS AGENT TOOLS:
-----------------------
search_transitions(query: str) -> List[transition_name]
add_transition_between_clips(clip1_id, clip2_id, transition_name, duration)

TTS AGENT TOOLS:
---------------
generate_tts(text: str, voice: str, position: float, track: int)
  voice: alloy, echo, fable, onyx, nova, shimmer

MUSIC AGENT TOOLS:
-----------------
generate_music(prompt: str, tags: List[str], position: float, track: int)

PARAMETER CALCULATION FROM VISION ANALYSIS:
------------------------------------------
Lighting score < 0.7 → brightness: 1.0 + (0.7 - score) * 0.5
Low contrast → contrast: 1.0 + (0.7 - score) * 0.3
Low saturation → saturation: 1.0 + (0.7 - score) * 0.2
"""

    @staticmethod
    def map_vision_score_to_params(score: float, param_type: str) -> float:
        """Convert vision analysis score to tool parameter value."""
        if param_type == "brightness":
            if score < 0.7:
                return round(1.0 + (0.7 - score) * 0.5, 2)
            return 1.0
        elif param_type == "contrast":
            if score < 0.7:
                return round(1.0 + (0.7 - score) * 0.3, 2)
            return 1.0
        elif param_type == "saturation":
            if score < 0.7:
                return round(1.0 + (0.7 - score) * 0.2, 2)
            return 1.0
        else:
            log.warning("Unknown param_type: %s", param_type)
            return 1.0

    @staticmethod
    def calculate_effect_params_from_vision(vision_data: Dict[str, Any]) -> Dict[str, float]:
        """Calculate effect parameters from vision analysis data."""
        params: Dict[str, float] = {}
        vision_analysis = vision_data.get("vision_analysis", {})
        composition = vision_analysis.get("composition", {})
        lighting_score = composition.get("lighting_score", 1.0)
        color_harmony = composition.get("color_harmony_score", 1.0)

        if lighting_score < 0.7:
            params["brightness"] = ToolRegistry.map_vision_score_to_params(lighting_score, "brightness")
            params["contrast"] = ToolRegistry.map_vision_score_to_params(lighting_score, "contrast")
        if color_harmony < 0.7:
            params["saturation"] = ToolRegistry.map_vision_score_to_params(color_harmony, "saturation")
        return params

    @staticmethod
    def format_tool_call(tool_name: str, tool_args: Dict[str, Any]) -> str:
        """Format a tool call for display / logging."""
        args_str = ", ".join(f"{k}={repr(v)}" for k, v in tool_args.items())
        return f"{tool_name}({args_str})"


_tool_registry = None


def get_tool_registry() -> ToolRegistry:
    global _tool_registry
    if _tool_registry is None:
        _tool_registry = ToolRegistry()
    return _tool_registry
