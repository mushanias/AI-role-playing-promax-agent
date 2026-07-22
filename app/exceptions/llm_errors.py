"""LLM 相关异常"""

from app.exceptions.base import BaseAppException


class LLMException(BaseAppException):
    """LLM 相关错误的基类"""


class LLMAuthError(LLMException):
    """API Key 错误或失效"""


class LLMNetworkError(LLMException):
    """网络连接失败或超时"""


class LLMResponseError(LLMException):
    """LLM 返回格式异常（如空回复）"""


class InvalidLLMConfigurationError(LLMException):
    """模型厂商、模型名或自定义预设无效。"""
