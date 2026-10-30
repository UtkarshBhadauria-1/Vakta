from typing import Literal

from pydantic import BaseModel, Field, field_validator


class ConversationTurn(BaseModel):
    role: Literal["user", "assistant"]
    content: str = Field(min_length=1, max_length=1500)

    @field_validator("content")
    @classmethod
    def content_must_not_be_blank(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("Conversation content must not be blank")
        return value


class ChatRequest(BaseModel):
    question: str = Field(min_length=1, max_length=1200)
    conversation: list[ConversationTurn] = Field(default_factory=list, max_length=8)
    session_id: str | None = Field(default=None, max_length=64)

    @field_validator("question")
    @classmethod
    def question_must_not_be_blank(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("Question must not be blank")
        return value


class SourceReference(BaseModel):
    id: str
    title: str
    source: str
    excerpt: str
    score: float = Field(ge=-1.0, le=1.0)
    page: int | None = None


class ChatResponse(BaseModel):
    answer: str
    sources: list[SourceReference]
    used_context: bool
    session_id: str | None = None
    intent: str | None = None
    confidence_score: float | None = None
    user_query_type: str | None = None
    escalated: bool = False
    escalation_reason: str | None = None
    requires_clarification: bool = False
    sentiment_label: Literal["positive", "neutral", "negative"] = "neutral"
    sentiment_score: float = Field(default=0.0, ge=-1.0, le=1.0)


class FeedbackRequest(BaseModel):
    session_id: str = Field(min_length=1, max_length=64)
    user_rating: int = Field(ge=1, le=5)

    @field_validator("session_id")
    @classmethod
    def session_id_must_not_be_blank(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("session_id must not be blank")
        return value


class FeedbackResponse(BaseModel):
    success: bool = True
    session_id: str
    user_rating: int
    message: str = "Feedback recorded successfully."
