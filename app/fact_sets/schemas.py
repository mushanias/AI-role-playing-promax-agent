"""不变事实 HTTP 接口的数据契约。"""

from datetime import datetime
from typing import Optional

from pydantic import BaseModel


class FactSetUpdateRequest(BaseModel):
    content: str


class FactSetResponse(BaseModel):
    content: str
    updated_at: Optional[datetime]
