"""Context 管理的数据模型"""

from datetime import datetime, timezone
from typing import Dict, Optional

from pydantic import BaseModel, Field


def utc_now() -> datetime:
    """返回当前 UTC 时间"""
    return datetime.now(timezone.utc)


class KeyState(BaseModel):
    """单个关键状态
    从被压缩的消息中提取，独立存储，不参与滚动压缩
    """
    key: str                                    # 状态名，如 "金币"
    value: str                                  # 状态值，如 "500"
    source_message_id: str                      # 来源消息 ID（追踪）
    updated_at: datetime = Field(default_factory=utc_now)  # 更新时间


class ContextState(BaseModel):
    """ContextBuilder 的缓存状态
    每次压缩后更新，记录"已压缩到哪"和"当前摘要"

    缓存失效条件（任一满足即失效重算）：
    - compressed_history_hash 不匹配（已压缩范围的消息被修改/删除/重排）
    - prompt_version 不匹配（压缩指令模板升级）
    - model 不匹配（换模型导致摘要可能不兼容）
    - schema_version 不匹配（数据结构变更，需迁移或重建）

    summary_version 不是失效条件，它只是摘要重压次数的计数。
    """
    schema_version: int = 1                     # 数据结构版本（结构变更时迁移/重建）
    conversation_id: str = "default"            # 会话 ID（MVP 默认 "default"）

    compressed_until_message_id: Optional[str] = None  # 压缩指针，指向最后一条已压缩消息的 ID
    compressed_history_hash: Optional[str] = None      # 已压缩消息范围的稳定哈希，检测消息被修改/删除/重排

    summary: str = ""                           # 当前摘要（滚动压缩的结果）
    summary_version: int = 0                    # 摘要重压次数（计数，非失效条件）
    key_states: Dict[str, KeyState] = Field(default_factory=dict)  # 关键状态（字典，key → KeyState）

    prompt_version: str = ""                    # 使用的 prompt 模板版本（变化则缓存失效）
    model: str = ""                             # 使用的模型（变化则缓存失效）
    updated_at: datetime = Field(default_factory=utc_now)  # 最后更新时间
