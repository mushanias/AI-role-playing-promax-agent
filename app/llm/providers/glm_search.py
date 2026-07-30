"""智谱 GLM 对话内联网搜索适配器。"""

from app.exceptions import LLMResponseError
from app.llm.contracts import (
    LLMGenerateRequest,
    LLMGenerateResult,
    LLMSource,
    LLMUsage,
    WebSearchPolicy,
)
from app.llm.providers.common import (
    BaseLLMAdapter,
    as_sequence,
    messages_to_dicts,
    read_field,
    source_from_fields,
)
from app.llm.providers.errors import call_openai


class GLMSearchAdapter(BaseLLMAdapter):
    """调用 GLM Web Search in Chat，并尽可能提取结构化来源。"""

    async def generate(
        self,
        request: LLMGenerateRequest,
    ) -> LLMGenerateResult:
        if request.web_search == WebSearchPolicy.DISABLED:
            return await self.generate_plain(request)

        messages = messages_to_dicts(request)
        if request.web_search == WebSearchPolicy.REQUIRED:
            messages.insert(
                0,
                {
                    "role": "system",
                    "content": "本次回答必须先使用联网搜索，并引用搜索来源。",
                },
            )
        response = await call_openai(
            self.client.client.chat.completions.create(
                messages=messages,
                tools=[
                    {
                        "type": "web_search",
                        "web_search": {
                            "enable": "True",
                            "search_engine": "search_pro",
                            "search_result": "True",
                            "count": "5",
                            "content_size": "medium",
                        },
                    }
                ],
                tool_choice="auto",
                **self.client.model["request_params"],
            )
        )
        choices = as_sequence(read_field(response, "choices"))
        if not choices:
            raise LLMResponseError("LLM 返回结果中没有候选回答")
        message = read_field(choices[0], "message")
        content = read_field(message, "content", "") or ""
        sources = _extract_sources(response, message)
        searched = bool(sources) or "ref_" in content
        if (
            request.web_search == WebSearchPolicy.REQUIRED
            and not searched
        ):
            raise LLMResponseError("已要求联网搜索，但模型没有执行搜索")

        warnings: tuple[str, ...] = ()
        if searched and not sources:
            warnings = ("厂商执行了联网搜索，但未返回可解析的结构化来源",)
        return self.build_result(
            content=content,
            sources=sources,
            usage=_extract_usage(response),
            warnings=warnings,
        )


def _extract_sources(
    response: object,
    message: object,
) -> tuple[LLMSource, ...]:
    sources: list[LLMSource] = []
    candidate_fields = (
        read_field(response, "web_search"),
        read_field(response, "search_result"),
        read_field(message, "web_search"),
        read_field(message, "search_result"),
    )
    for candidate in candidate_fields:
        for item in as_sequence(candidate):
            nested = read_field(item, "search_result")
            values = as_sequence(nested) if nested is not None else (item,)
            for value in values:
                source = source_from_fields(value)
                if source is not None:
                    sources.append(source)
    return tuple(sources)


def _extract_usage(response: object) -> LLMUsage:
    usage = read_field(response, "usage")
    return LLMUsage(
        input_tokens=int(read_field(usage, "prompt_tokens", 0) or 0),
        output_tokens=int(read_field(usage, "completion_tokens", 0) or 0),
    )
