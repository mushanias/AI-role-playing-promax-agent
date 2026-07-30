"""不提供原生联网能力的普通模型适配器。"""

from app.exceptions import InvalidLLMConfigurationError
from app.llm.contracts import (
    LLMGenerateRequest,
    LLMGenerateResult,
    WebSearchPolicy,
)
from app.llm.providers.common import BaseLLMAdapter


class PlainLLMAdapter(BaseLLMAdapter):
    """普通问答适配器；明确处理不支持联网时的降级边界。"""

    async def generate(
        self,
        request: LLMGenerateRequest,
    ) -> LLMGenerateResult:
        warnings: tuple[str, ...] = ()
        if request.web_search != WebSearchPolicy.DISABLED:
            if request.web_search == WebSearchPolicy.REQUIRED:
                raise InvalidLLMConfigurationError(
                    f"{self.provider} 当前不支持原生联网搜索"
                )
            warnings = ("当前模型不支持联网搜索，已使用普通回答",)
        return await self.generate_plain(request, warnings=warnings)
