"""
NVIDIA Edge LLM Provider — routes ``nvidia-edge/*`` model IDs to the
local NVIDIA device running LLM inference.

Ported from core/src/classes/nvidia_edge_provider.py.
"""

from __future__ import annotations

from typing import Any, Optional


def is_available(model_id: str, settings: Any) -> bool:
    """Check if this model should be handled by the edge provider."""
    if not model_id.startswith("nvidia-edge/"):
        return False
    edge_url = getattr(settings, "nvidia_edge_url", "") or ""
    return bool(edge_url)


def build_chat_model(model_id: str, settings: Any):
    """Build a LangChain ChatOpenAI pointed at the local NVIDIA edge device."""
    from langchain_openai import ChatOpenAI

    edge_url = getattr(settings, "nvidia_edge_url", "")
    if not edge_url:
        raise ValueError("NVIDIA_EDGE_URL not configured. Set it in .env to use edge inference.")
    # Strip the nvidia-edge/ prefix to get the actual model name
    actual_model = model_id.replace("nvidia-edge/", "", 1)

    return ChatOpenAI(
        model=actual_model,
        openai_api_base=f"{edge_url}/v1",
        openai_api_key="n/a",  # Edge device does not require an API key
        temperature=0.7,
    )
