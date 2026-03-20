"""
Zenvi Backend — FastAPI application entry point.
"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from config import get_settings
from logger import setup_logging


def create_app() -> FastAPI:
    settings = get_settings()
    setup_logging("DEBUG" if settings.debug else "INFO")

    app = FastAPI(
        title="Zenvi Backend",
        description="AI/LLM backend for the Zenvi video editor. Provides chat, media analysis, search, indexing, video generation, and management APIs.",
        version="0.1.0",
    )

    # CORS
    origins = [o.strip() for o in settings.cors_origins.split(",") if o.strip()]
    app.add_middleware(
        CORSMiddleware,
        allow_origins=origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Include all routers
    from api.routes.models import router as models_router
    from api.routes.chat import router as chat_router
    from api.routes.search import router as search_router
    from api.routes.indexing import router as indexing_router
    from api.routes.generation import router as generation_router
    from api.routes.tags import router as tags_router
    from api.routes.faces import router as faces_router
    from api.routes.collections import router as collections_router
    from api.routes.media import router as media_router
    from api.routes.research import router as research_router
    from api.routes.directors import router as directors_router
    from api.routes.pexels import router as pexels_router

    api_prefix = "/api/v1"
    app.include_router(models_router, prefix=api_prefix)
    app.include_router(chat_router, prefix=api_prefix)
    app.include_router(search_router, prefix=api_prefix)
    app.include_router(indexing_router, prefix=api_prefix)
    app.include_router(generation_router, prefix=api_prefix)
    app.include_router(tags_router, prefix=api_prefix)
    app.include_router(faces_router, prefix=api_prefix)
    app.include_router(collections_router, prefix=api_prefix)
    app.include_router(media_router, prefix=api_prefix)
    app.include_router(research_router, prefix=api_prefix)
    app.include_router(directors_router, prefix=api_prefix)
    app.include_router(pexels_router, prefix=api_prefix)

    @app.get("/health")
    def health():
        return {"status": "ok", "service": "zenvi-backend"}

    return app


app = create_app()
