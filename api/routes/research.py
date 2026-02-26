"""
REST endpoints for Perplexity-powered research.
"""

from fastapi import APIRouter, HTTPException
from api.schemas import ResearchRequest, ResearchResponse
from logger import log

router = APIRouter(prefix="/research", tags=["research"])


@router.post("/search", response_model=ResearchResponse)
async def research_search(req: ResearchRequest):
    """Search the web via Perplexity Sonar and return AI-powered answers."""
    try:
        from core.tools.research_tools import research_web
        result = research_web(
            query=req.query,
            max_images=req.max_images,
            search_domain_filter=req.search_domain_filter or "",
            search_recency_filter=req.search_recency_filter or "",
            timeout_seconds=req.timeout_seconds,
        )
        return ResearchResponse(result=result)
    except Exception as e:
        log.error("Research search failed: %s", e, exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/plan", response_model=ResearchResponse)
async def research_plan(req: ResearchRequest):
    """Research a topic for content planning (colours, mood, transitions)."""
    try:
        from core.tools.research_tools import research_for_content_planning
        result = research_for_content_planning(
            topic=req.query,
            content_type=req.content_type or "video",
            aspects=req.aspects or "",
            timeout_seconds=req.timeout_seconds,
        )
        return ResearchResponse(result=result)
    except Exception as e:
        log.error("Research plan failed: %s", e, exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))
