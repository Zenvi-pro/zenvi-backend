"""
LLM model listing and configuration endpoints.
"""

from fastapi import APIRouter
from api.schemas import ModelsResponse, ModelInfo

router = APIRouter(prefix="/models", tags=["models"])


@router.get("", response_model=ModelsResponse)
def list_models():
    """List all available LLM models."""
    from core.llm import list_models, list_all_models, get_default_model_id

    available = list_models()
    all_models = list_all_models()
    default = get_default_model_id()

    return ModelsResponse(
        models=[ModelInfo(model_id=mid, display_name=name) for mid, name in all_models],
        default_model_id=default,
    )


@router.get("/available", response_model=ModelsResponse)
def list_available_models():
    """List only models with valid API keys configured."""
    from core.llm import list_models, get_default_model_id

    available = list_models()
    default = get_default_model_id()

    return ModelsResponse(
        models=[ModelInfo(model_id=mid, display_name=name) for mid, name in available],
        default_model_id=default,
    )
