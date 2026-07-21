"""把领域异常转换为稳定的 HTTP 状态码与机器可读错误码。"""

from dataclasses import dataclass

from app.exceptions import (
    BaseAppException,
    BranchNotFoundError,
    InvalidBranchOperationError,
    LLMAuthError,
    LLMNetworkError,
    LLMResponseError,
    StorageConflictError,
    StorageCorruptionError,
    StorageIOError,
    StorageNotFoundError,
    TurnNotFoundError,
)


@dataclass(frozen=True)
class ErrorDescriptor:
    """HTTP 层可直接使用的错误描述。"""

    status_code: int
    code: str
    message: str


def map_app_exception(error: BaseAppException) -> ErrorDescriptor:
    """按最具体的异常类型返回状态码和稳定错误码。"""
    mappings = (
        (StorageNotFoundError, 404, "storage_not_found"),
        (BranchNotFoundError, 404, "branch_not_found"),
        (TurnNotFoundError, 404, "turn_not_found"),
        (StorageConflictError, 409, "storage_conflict"),
        (
            InvalidBranchOperationError,
            409,
            "invalid_branch_operation",
        ),
        (LLMAuthError, 502, "llm_auth_error"),
        (LLMNetworkError, 503, "llm_network_error"),
        (LLMResponseError, 502, "llm_response_error"),
        (StorageCorruptionError, 500, "storage_corruption"),
        (StorageIOError, 500, "storage_io_error"),
    )

    for exception_type, status_code, code in mappings:
        if isinstance(error, exception_type):
            return ErrorDescriptor(status_code, code, error.message)

    return ErrorDescriptor(400, "application_error", error.message)
