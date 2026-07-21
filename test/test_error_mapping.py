"""领域异常到 HTTP 错误契约的映射测试。"""

import unittest

from app.core.error_mapping import map_app_exception
from app.exceptions import (
    BranchNotFoundError,
    InvalidBranchOperationError,
    LLMNetworkError,
    StorageCorruptionError,
)


class ErrorMappingTests(unittest.TestCase):
    def test_not_found_maps_to_404(self) -> None:
        result = map_app_exception(BranchNotFoundError("不存在"))

        self.assertEqual(result.status_code, 404)
        self.assertEqual(result.code, "branch_not_found")

    def test_branch_conflict_maps_to_409(self) -> None:
        result = map_app_exception(
            InvalidBranchOperationError("状态冲突")
        )

        self.assertEqual(result.status_code, 409)
        self.assertEqual(result.code, "invalid_branch_operation")

    def test_network_error_maps_to_503(self) -> None:
        result = map_app_exception(LLMNetworkError("网络失败"))

        self.assertEqual(result.status_code, 503)
        self.assertEqual(result.code, "llm_network_error")

    def test_corruption_maps_to_500(self) -> None:
        result = map_app_exception(StorageCorruptionError("文件损坏"))

        self.assertEqual(result.status_code, 500)
        self.assertEqual(result.code, "storage_corruption")


if __name__ == "__main__":
    unittest.main()
