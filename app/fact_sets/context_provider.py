"""把不变事实转换为一次性的主对话前缀。"""

from typing import Dict, Tuple

from app.context import ContextPrefixRequest
from app.fact_sets.service import FactSetService


class FactSetContextProvider:
    """只暴露通用 messages，不把 FactSet 模型泄露给会话模块。"""

    def __init__(self, service: FactSetService) -> None:
        self.service = service

    async def get_messages(
        self,
        request: ContextPrefixRequest,
    ) -> Tuple[Dict[str, str], ...]:
        del request
        fact_set = await self.service.get()
        content = fact_set.content.strip()
        if not content:
            return ()

        return ({
            "role": "system",
            "content": f"【不变事实】\n{content}",
        },)
