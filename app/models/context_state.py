from typing import Optional

from pydantic import BaseModel


class ContextState(BaseModel):
    """Context 的派生状态，不保存原始消息。"""

    summary: str = ""
    compressed_until_message_id: Optional[str] = None