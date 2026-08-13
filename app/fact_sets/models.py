"""单个本地不变事实文档的数据模型。"""

from datetime import datetime
from typing import Literal, Optional

from pydantic import BaseModel, ConfigDict


class FactSet(BaseModel):
    """独立于会话历史保存的用户设定文档。"""

    model_config = ConfigDict(extra="forbid")

    schema_version: Literal[1] = 1
    content: str = ""
    updated_at: Optional[datetime] = None
