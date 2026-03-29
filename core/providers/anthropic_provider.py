"""
Anthropic provider — LangChain ChatAnthropic from settings.
Ported from zenvi-core.
"""

from logger import log

# Anthropic requires full versioned model IDs — map short aliases to canonical names
_MODEL_ALIASES = {
    "claude-3-5-sonnet":        "claude-3-5-sonnet-20241022",
    "claude-3-5-haiku":         "claude-3-5-haiku-20241022",
    "claude-3-haiku":           "claude-3-haiku-20240307",
    "claude-3-sonnet":          "claude-3-sonnet-20240229",
    "claude-3-opus":            "claude-3-opus-20240229",
}


def is_available(model_id, settings):
    if not model_id.startswith("anthropic/"):
        return False
    key = (settings.get("anthropic-api-key") or "").strip()
    return bool(key)


def build_chat_model(model_id, settings):
    try:
        from langchain_anthropic import ChatAnthropic
    except ImportError:
        log.warning("langchain-anthropic not installed")
        return None

    api_key = (settings.get("anthropic-api-key") or "").strip()
    if not api_key:
        return None

    model_name = model_id.split("/", 1)[-1] if "/" in model_id else model_id
    model_name = _MODEL_ALIASES.get(model_name, model_name)
    return ChatAnthropic(model=model_name, api_key=api_key, temperature=0.2)
