from app.exceptions import ContextBudgetError
from app.services.context_builder import (
    ContextBuilder,
    ContextBuildResult,
)
from app.services.context_compression_service import (
    ContextCompressionService,
)
from app.storage.base import BaseStorage
from app.storage.context_state_storage import ContextStateStorage
from app.storage.profile_storage import ProfileStorage


class ContextManager:
    """读取 Context 数据、执行压缩循环并返回最终上下文。"""

    def __init__(
        self,
        context_builder: ContextBuilder,
        compression_service: ContextCompressionService,
        message_storage: BaseStorage,
        profile_storage: ProfileStorage,
        state_storage: ContextStateStorage,
        max_compression_passes: int,
    ) -> None:
        if max_compression_passes < 1:
            raise ValueError("最大压缩次数必须大于 0")

        self.context_builder = context_builder
        self.compression_service = compression_service
        self.message_storage = message_storage
        self.profile_storage = profile_storage
        self.state_storage = state_storage
        self.max_compression_passes = max_compression_passes

    async def build(self) -> ContextBuildResult:
        profile = await self.profile_storage.load_profile()
        history = await self.message_storage.load_messages()
        state = await self.state_storage.load()

        for pass_number in range(
            self.max_compression_passes + 1
        ):
            result = self.context_builder.build(
                profile=profile,
                history=history,
                state=state,
            )

            if not result.needs_compression:
                return result

            if pass_number == self.max_compression_passes:
                break

            attempt = await self.compression_service.compress(
                state=state,
                recent_messages=result.recent_messages,
            )

            if not attempt.compressed:
                break

            state = attempt.next_state

            # 每次成功压缩后立即保存有效状态。
            await self.state_storage.save(state)

        raise ContextBudgetError(
            "上下文超过预算，且无法继续压缩。"
            "请缩短当前输入或减少角色设定。"
        )