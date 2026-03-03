"""
Directors REST endpoints.

Exposes the backend's director registry so zenvi-core can list,
load, and trigger director analysis without touching the filesystem directly.
"""

from fastapi import APIRouter, HTTPException
from api.schemas import StatusResponse
from logger import log

router = APIRouter(prefix="/directors", tags=["directors"])


def _load_director_loader():
    from core.directors.director_loader import get_director_loader
    return get_director_loader()


@router.get("")
def list_directors():
    """List all available directors (built-in + user-installed)."""
    try:
        loader = _load_director_loader()
        available = loader.list_available_directors()
        directors = [
            {
                "id": d.id,
                "name": d.name,
                "description": d.description,
                "author": getattr(d, "author", ""),
                "version": getattr(d, "version", "1.0.0"),
                "tags": getattr(d, "tags", []),
                "expertise": getattr(getattr(d, "personality", None), "expertise_areas", []),
                "focus": getattr(getattr(d, "personality", None), "analysis_focus", []),
            }
            for d in available
        ]
        return {"directors": directors}
    except Exception as e:
        log.error("Failed to list directors: %s", e, exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{director_id}")
def get_director(director_id: str):
    """Get details for a specific director."""
    try:
        loader = _load_director_loader()
        director = loader.load_director(director_id)
        if director is None:
            raise HTTPException(status_code=404, detail=f"Director '{director_id}' not found")
        return {
            "id": director.id,
            "name": director.name,
            "description": director.description,
            "author": getattr(director, "author", ""),
            "version": getattr(director, "version", "1.0.0"),
            "tags": getattr(director, "tags", []),
            "expertise": getattr(getattr(director, "personality", None), "expertise_areas", []),
            "focus": getattr(getattr(director, "personality", None), "analysis_focus", []),
        }
    except HTTPException:
        raise
    except Exception as e:
        log.error("Failed to get director %s: %s", director_id, e, exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))
