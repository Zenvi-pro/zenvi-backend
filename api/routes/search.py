"""
Search endpoints.
"""

from fastapi import APIRouter
from api.schemas import SearchRequest, SearchResponse, SearchResultItem

router = APIRouter(prefix="/search", tags=["search"])


@router.post("", response_model=SearchResponse)
def search_clips(req: SearchRequest):
    """Search for clips matching a query."""
    from core.indexing.twelvelabs import search_index

    results = search_index(req.query, index_id=req.index_id or "", top_k=req.top_k)
    return SearchResponse(
        results=[SearchResultItem(**r) for r in results],
        query=req.query,
    )
