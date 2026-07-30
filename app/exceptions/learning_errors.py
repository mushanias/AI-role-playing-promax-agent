"""学习 Agent 产品域异常。"""

from app.exceptions.base import BaseAppException


class LearningGraphRuleError(BaseAppException):
    """节点、端口或分支操作违反学习图不变量。"""

