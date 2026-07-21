"""剧情分支相关异常。"""

from app.exceptions.base import BaseAppException


class BranchException(BaseAppException):
    """剧情分支错误的基类。"""


class BranchNotFoundError(BranchException):
    """指定剧情分支不存在。"""


class TurnNotFoundError(BranchException):
    """指定原始轮次不存在。"""


class InvalidBranchOperationError(BranchException):
    """当前状态不允许执行指定分支操作。"""
