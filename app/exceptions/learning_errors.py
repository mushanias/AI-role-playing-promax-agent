"""学习 Agent 产品域异常。"""

from app.exceptions.base import BaseAppException


class LearningGraphRuleError(BaseAppException):
    """节点、端口或分支操作违反学习图不变量。"""


class LearningContextError(BaseAppException):
    """当前学习路径无法在不破坏必要信息的情况下组装。"""
