from app.exceptions.base import BaseAppException


class ContextBudgetError(BaseAppException):
    """压缩后仍无法满足 Context 预算。"""