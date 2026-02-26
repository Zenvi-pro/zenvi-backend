"""
Pydantic schemas for API request/response models.
"""

from datetime import datetime
from typing import List, Dict, Any, Optional
from enum import Enum
from pydantic import BaseModel, Field


# ---- Common ----
class StatusResponse(BaseModel):
    success: bool
    message: str = ""
    data: Optional[Dict[str, Any]] = None


# ---- Models / LLM ----
class ModelInfo(BaseModel):
    model_id: str
    display_name: str


class ModelsResponse(BaseModel):
    models: List[ModelInfo]
    default_model_id: str = ""


# ---- Chat ----
class ChatMessageSchema(BaseModel):
    role: str  # user, assistant, system
    content: str
    context: Optional[Dict[str, Any]] = None
    timestamp: Optional[str] = None


class ChatRequest(BaseModel):
    message: str
    model_id: Optional[str] = None
    context: Optional[Dict[str, Any]] = None
    session_id: Optional[str] = None


class ChatResponse(BaseModel):
    response: str
    session_id: str = ""
    model_id: str = ""


class ChatSessionInfo(BaseModel):
    session_id: str
    model: str = ""
    message_count: int = 0
    created_at: str = ""
    updated_at: str = ""


class ChatHistoryResponse(BaseModel):
    messages: List[ChatMessageSchema]
    session_info: ChatSessionInfo


# ---- WebSocket tool execution ----
class ToolCallMessage(BaseModel):
    """Sent from backend to frontend via WebSocket — execute this tool locally."""
    type: str = "tool_call"
    tool_name: str
    tool_args: Dict[str, Any] = {}
    call_id: str = ""


class ToolResultMessage(BaseModel):
    """Sent from frontend to backend via WebSocket — result of tool execution."""
    type: str = "tool_result"
    call_id: str
    result: str
    error: Optional[str] = None


class ChatStreamMessage(BaseModel):
    """Wrapper for all WebSocket messages."""
    type: str  # "user_message", "assistant_response", "tool_call", "tool_result", "error", "done"
    data: Dict[str, Any] = {}


# ---- Media Analysis ----
class AnalyzeRequest(BaseModel):
    file_path: str
    provider: str = "openai"  # openai, google, aws


class AnalysisResultSchema(BaseModel):
    objects: List[str] = []
    scenes: List[str] = []
    activities: List[str] = []
    mood: List[str] = []
    colors: Dict[str, Any] = {}
    description: str = ""
    provider: str = ""
    confidence: float = 0.0


# ---- Search ----
class SearchRequest(BaseModel):
    query: str
    top_k: int = 5
    index_id: Optional[str] = None


class SearchResultItem(BaseModel):
    video_id: Optional[str] = None
    score: float = 0.0
    start: float = 0.0
    end: float = 0.0
    filename: str = ""


class SearchResponse(BaseModel):
    results: List[SearchResultItem]
    query: str


# ---- Indexing (TwelveLabs) ----
class IndexRequest(BaseModel):
    file_path: str
    index_name: str
    filename: Optional[str] = None
    existing_index_id: Optional[str] = None


class IndexResultSchema(BaseModel):
    status: str
    index_id: Optional[str] = None
    asset_id: Optional[str] = None
    video_id: Optional[str] = None
    filename: Optional[str] = None
    error: Optional[str] = None


# ---- Video Generation ----
class GenerateVideoRequest(BaseModel):
    prompt: str
    duration_seconds: int = 5
    model: str = "klingai:kling@o1"
    width: int = 1280
    height: int = 720
    input_video_url: Optional[str] = None


class GenerateMorphVideoRequest(BaseModel):
    prompt: str
    start_image_url: str
    end_image_url: str
    duration_seconds: int = 5
    model: str = "klingai:kling@o1"
    width: int = 1280
    height: int = 720


class GenerateVideoResponse(BaseModel):
    video_url: Optional[str] = None
    local_path: Optional[str] = None
    error: Optional[str] = None


class ResearchRequest(BaseModel):
    query: str
    max_images: int = 3
    search_domain_filter: Optional[str] = None
    search_recency_filter: Optional[str] = None
    content_type: Optional[str] = "video"
    aspects: Optional[str] = ""
    timeout_seconds: float = 120.0


class ResearchResponse(BaseModel):
    result: str = ""
    error: Optional[str] = None


class GitHubRepoRequest(BaseModel):
    repo_url: str


class GitHubRepoResponse(BaseModel):
    repo_info: Optional[Dict[str, Any]] = None
    readme: str = ""
    owner: str = ""
    repo: str = ""
    error: Optional[str] = None


# ---- Tags ----
class TagsUpdateRequest(BaseModel):
    file_id: str
    tags: Dict[str, Any]


class TagSearchRequest(BaseModel):
    tag_value: str
    tag_type: Optional[str] = None


# ---- Faces ----
class PersonSchema(BaseModel):
    person_id: str
    name: str = ""
    thumbnail_path: Optional[str] = None
    created_at: Optional[float] = None


class CreatePersonRequest(BaseModel):
    person_id: str
    name: str = ""


class RenamePersonRequest(BaseModel):
    name: str


# ---- Collections ----
class CreateCollectionRequest(BaseModel):
    collection_id: str
    name: str
    collection_type: str = "manual"


class CollectionSchema(BaseModel):
    collection_id: str
    name: str
    type: str = "manual"
    file_ids: List[str] = []
    created_at: Optional[float] = None


class AddFileToCollectionRequest(BaseModel):
    file_id: str


# ---- Video Tagging / Analysis ----
class VideoTagRequest(BaseModel):
    video_path: str


class AnalysisQueueRequest(BaseModel):
    file_id: str
    file_path: str
    media_type: str = "video"


class AnalysisQueueStatus(BaseModel):
    pending: int = 0
    processing: int = 0
    total: int = 0
    current_file: str = ""
    queue: List[Dict[str, Any]] = []


# ---- Indexing extras ----
class DeleteIndexedVideoParams(BaseModel):
    index_id: str
    video_id: str
