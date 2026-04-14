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


class ChatResponse(BaseModel):
    answer: str
    detected_language: str
    sources: List[SourceNode] = []
    confidence: float = Field(..., ge=0.0, le=1.0)
    session_id: Optional[str] = None


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
