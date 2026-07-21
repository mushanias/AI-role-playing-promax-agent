"""异常统一导出：其他模块只需 from app.exceptions import XXXError"""

from app.exceptions.base import BaseAppException
from app.exceptions.llm_errors import (
    LLMException,
    LLMAuthError,
    LLMNetworkError,
    LLMResponseError,
)
from app.exceptions.storage_errors import (
    StorageException,
    StorageCorruptionError,
    StorageIOError,
    StorageNotFoundError,
    StorageConflictError,
)
from app.exceptions.context_errors import ContextBudgetError
