"""
LLM registry — resolve model_id to a LangChain ChatModel.
Ported from zenvi-core; uses backend Settings instead of app.get_settings().
"""

from logger import log
from core.providers import (
    PROVIDER_LIST,
    build_model as _build_model,
    list_available_models as _list_available,
    list_all_models as _list_all_models,
)


def get_settings():
    """Return the backend Settings singleton."""
    from config import get_settings as _get
    return _get()


def get_model(model_id):
    """Return a LangChain BaseChatModel for the given model_id, or None."""
    settings = get_settings()
    return _build_model(model_id, settings)


def list_models():
    """Return (model_id, display_name) for models available with current settings."""
    settings = get_settings()
    return _list_available(settings)


def list_all_models():
    """Return (model_id, display_name) for all registered models."""
    return _list_all_models()


def get_default_model_id():
    """Return the default model id from settings, or first available."""
    models = list_models()
    settings = get_settings()
    if settings:
        default = settings.get("ai-default-model")
        if default and any(mid == default for mid, _ in models):
            return default
    if models:
        return models[0][0]
    if PROVIDER_LIST:
        return PROVIDER_LIST[0][0]
    return "openai/gpt-4o-mini"
