"""全局角色设定接口的数据模型。"""

from typing import Dict
from pydantic import BaseModel


class ProfileResponse(BaseModel):
    """设定响应"""
    settings: Dict[str, str]


class ProfileUpdateRequest(BaseModel):
    """全量更新请求"""
    settings: Dict[str, str]


class SettingUpdateRequest(BaseModel):
    """单条增改请求"""
    key: str
    value: str
