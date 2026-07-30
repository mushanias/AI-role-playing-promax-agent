"""异常统一导出：其他模块只需 from app.exceptions import XXXError"""

from app.exceptions.base import BaseAppException
from app.exceptions.llm_errors import (
    InvalidLLMConfigurationError,
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
from app.exceptions.branch_errors import (
    BranchException,
    BranchNotFoundError,
    InvalidBranchOperationError,
    TurnNotFoundError,
)
from app.exceptions.learning_errors import LearningGraphRuleError
