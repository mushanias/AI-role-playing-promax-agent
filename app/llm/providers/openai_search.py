"""OpenAI Responses 兼容厂商的原生联网搜索适配器。"""

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


class OpenAIResponsesSearchAdapter(BaseLLMAdapter):
    """适配 OpenAI 与 xAI 的 Responses API 搜索结果。"""

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
            self.client.client.responses.create(
                input=messages,
                tools=[{"type": "web_search"}],
                **self.client.model["request_params"],
            )
        )
        content = read_field(response, "output_text", "") or ""
        sources = _extract_sources(response)
        searched = _has_search_call(response) or bool(sources)
        if (
            request.web_search == WebSearchPolicy.REQUIRED
            and not searched
        ):
            raise LLMResponseError("已要求联网搜索，但模型没有执行搜索")
        return self.build_result(
            content=content,
            sources=sources,
            usage=_extract_usage(response),
        )


def _extract_sources(response: object) -> tuple[LLMSource, ...]:
    sources: list[LLMSource] = []
    for item in as_sequence(read_field(response, "output")):
        for block in as_sequence(read_field(item, "content")):
            for annotation in as_sequence(
                read_field(block, "annotations")
            ):
                source = source_from_fields(annotation)
                if source is not None:
                    sources.append(source)

    for citation in as_sequence(read_field(response, "citations")):
        if isinstance(citation, str):
            source = source_from_fields({"url": citation})
        else:
            source = source_from_fields(citation)
        if source is not None:
            sources.append(source)
    return tuple(sources)


def _has_search_call(response: object) -> bool:
    return any(
        read_field(item, "type") == "web_search_call"
        for item in as_sequence(read_field(response, "output"))
    )


def _extract_usage(response: object) -> LLMUsage:
    usage = read_field(response, "usage")
    return LLMUsage(
        input_tokens=int(read_field(usage, "input_tokens", 0) or 0),
        output_tokens=int(read_field(usage, "output_tokens", 0) or 0),
    )
