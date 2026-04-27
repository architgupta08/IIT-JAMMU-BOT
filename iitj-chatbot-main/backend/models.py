"""
models.py — Pydantic schemas for IIT Jammu Chatbot API
"""
from pydantic import BaseModel, Field
from typing import Optional, List
from enum import Enum


class ChatRequest(BaseModel):
    message: str = Field(..., min_length=1, max_length=2000, description="User's message")
    session_id: Optional[str] = Field(None, description="Optional session ID for conversation history")
    language: Optional[str] = Field(None, description="Override language (ISO 639-1 code). Auto-detected if not provided.")

    class Config:
        json_schema_extra = {
            "example": {
                "message": "What is the B.Tech fee structure at IIT Jammu?",
                "session_id": "user_abc123",
                "language": None
            }
        }


class SourceNode(BaseModel):
    title: str
    path: str  # e.g. "Programs > B.Tech > Fees"
    node_id: str


class ConfidenceMeta(BaseModel):
    """Breakdown of the confidence score components."""
    score: float = Field(..., ge=0.0, le=1.0, description="Overall confidence score")
    label: str = Field(..., description="Human-readable label: high / medium / low")
    source_count: int = Field(..., description="Number of knowledge-base nodes used")


class ChatResponse(BaseModel):
    answer: str
    detected_language: str
    sources: List[SourceNode] = []
    confidence: float = Field(..., ge=0.0, le=1.0)
    confidence_meta: Optional[ConfidenceMeta] = Field(
        None, description="Detailed confidence breakdown"
    )
    suggestions: List[str] = Field(
        default_factory=list,
        description="Follow-up question suggestions related to the answer",
    )
    session_id: Optional[str] = None
    response_time_ms: Optional[float] = Field(
        None, description="Server-side response time in milliseconds"
    )


class HealthResponse(BaseModel):
    status: str
    index_loaded: bool
    total_nodes: int
    gemini_model: str


class IndexStatsResponse(BaseModel):
    total_sections: int
    total_nodes: int
    top_level_sections: List[str]
    last_updated: Optional[str]


class SuggestedQuestionsResponse(BaseModel):
    questions: List[str]
