"""Anthropic 原生联网搜索适配器。"""

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
from app.llm.providers.errors import call_anthropic


class AnthropicSearchAdapter(BaseLLMAdapter):
    """把 Anthropic 服务端搜索块归一化为统一来源契约。"""

    async def generate(
        self,
        request: LLMGenerateRequest,
    ) -> LLMGenerateResult:
        if request.web_search == WebSearchPolicy.DISABLED:
            return await self.generate_plain(request)

        messages = messages_to_dicts(request)
        system_parts = [
            item["content"] for item in messages if item["role"] == "system"
        ]
        chat_messages = [
            item for item in messages if item["role"] != "system"
        ]
        if request.web_search == WebSearchPolicy.REQUIRED:
            system_parts.insert(
                0,
                "本次回答必须先使用联网搜索，并引用搜索来源。",
            )

        sdk_request = dict(self.client.model["request_params"])
        sdk_request["messages"] = chat_messages
        sdk_request["tools"] = [
            {
                "type": "web_search_20250305",
                "name": "web_search",
                "max_uses": 5,
            }
        ]
        if system_parts:
            sdk_request["system"] = "\n\n".join(system_parts)
        response = await call_anthropic(
            self.client.client.messages.create(**sdk_request)
        )
        content = "".join(
            read_field(block, "text", "") or ""
            for block in as_sequence(read_field(response, "content"))
            if read_field(block, "type") == "text"
        )
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
    for block in as_sequence(read_field(response, "content")):
        for citation in as_sequence(read_field(block, "citations")):
            source = source_from_fields(citation)
            if source is not None:
                sources.append(source)
    return tuple(sources)


def _has_search_call(response: object) -> bool:
    search_block_types = {"server_tool_use", "web_search_tool_result"}
    for block in as_sequence(read_field(response, "content")):
        if read_field(block, "type") not in search_block_types:
            continue
        name = read_field(block, "name")
        if name in (None, "web_search"):
            return True
    return False


def _extract_usage(response: object) -> LLMUsage:
    usage = read_field(response, "usage")
    return LLMUsage(
        input_tokens=int(read_field(usage, "input_tokens", 0) or 0),
        output_tokens=int(read_field(usage, "output_tokens", 0) or 0),
    )
