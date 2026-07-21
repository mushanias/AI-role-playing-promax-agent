"""对话、历史、重写与分支切换的 HTTP 数据契约。"""

from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel, Field

from app.models.conversation import TurnStatus


class ConversationCreateResponse(BaseModel):
    conversation_id: str
    active_branch_id: str


class SendTurnRequest(BaseModel):
    message: str = Field(min_length=1)
    branch_id: Optional[str] = None


class RewriteTurnRequest(BaseModel):
    message: str = Field(min_length=1)
    source_branch_id: Optional[str] = None


class ChatTurnResponse(BaseModel):
    conversation_id: str
    branch_id: str
    turn_id: str
    reply: str
    warnings: List[str]
    compression_passes: int
    quality_degraded: bool


class HistoryTurnResponse(BaseModel):
    turn_id: str
    parent_turn_id: Optional[str]
    user_content: str
    assistant_content: Optional[str]
    status: TurnStatus
    created_at: datetime
    completed_at: Optional[datetime]
    variant_index: int
    variant_count: int
    has_variants: bool


class ConversationHistoryResponse(BaseModel):
    conversation_id: str
    branch_id: str
    active_branch_id: str
    turns: List[HistoryTurnResponse]


class TurnVariantResponse(BaseModel):
    turn_id: str
    branch_id: str
    user_content: str
    created_at: datetime
    is_active: bool


class TurnVariantsResponse(BaseModel):
    variants: List[TurnVariantResponse]


class BranchActivationResponse(BaseModel):
    conversation_id: str
    active_branch_id: str
    head_turn_id: Optional[str]
    active_summary_id: Optional[str]
