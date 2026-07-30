"""厂商适配器共享的参数转换与响应归一化工具。"""

from collections.abc import Iterable
from urllib.parse import urlparse

from app.exceptions import LLMResponseError
from app.llm.client import LLMClient
from app.llm.contracts import (
    LLMGenerateRequest,
    LLMGenerateResult,
    LLMSource,
    LLMUsage,
    ProviderCapabilities,
)


class BaseLLMAdapter:
    """提供厂商无关的模型元数据和普通问答能力。"""

    def __init__(
        self,
        provider: str,
        model: str,
        capabilities: ProviderCapabilities,
        client: LLMClient,
    ) -> None:
        self.provider = provider
        self.model = model
        self._capabilities = capabilities
        self.client = client

    @property
    def capabilities(self) -> ProviderCapabilities:
        return self._capabilities

    async def generate_plain(
        self,
        request: LLMGenerateRequest,
        warnings: tuple[str, ...] = (),
    ) -> LLMGenerateResult:
        """复用稳定的普通模型调用，并包装为统一结果。"""
        content = await self.client.chat(messages_to_dicts(request))
        return self.build_result(content=content, warnings=warnings)

    def build_result(
        self,
        content: str,
        sources: tuple[LLMSource, ...] = (),
        usage: LLMUsage | None = None,
        warnings: tuple[str, ...] = (),
    ) -> LLMGenerateResult:
        """检查正文并构造上游只需依赖的统一结果。"""
        if not content.strip():
            raise LLMResponseError("LLM 返回了空回复")
        return LLMGenerateResult(
            content=content,
            provider=self.provider,
            model=self.model,
            sources=deduplicate_sources(sources),
            usage=usage or LLMUsage(),
            warnings=warnings,
        )


def messages_to_dicts(
    request: LLMGenerateRequest,
) -> list[dict[str, str]]:
    """把契约消息转换为厂商 SDK 接受的基础字典。"""
    return [
        {
            "role": message.role.value,
            "content": message.content,
        }
        for message in request.messages
    ]


def read_field(value: object, name: str, default=None):
    """同时读取 SDK 对象属性和测试/兼容接口中的字典字段。"""
    if isinstance(value, dict):
        return value.get(name, default)
    return getattr(value, name, default)


def as_sequence(value: object) -> tuple[object, ...]:
    """把可能缺失、单值或列表的字段统一为元组。"""
    if value is None:
        return ()
    if isinstance(value, (str, bytes, dict)):
        return (value,)
    if isinstance(value, Iterable):
        return tuple(value)
    return (value,)


def source_from_fields(
    value: object,
    *,
    url_names: tuple[str, ...] = ("url", "link"),
    title_names: tuple[str, ...] = ("title", "name"),
) -> LLMSource | None:
    """从不同厂商的常见字段名中提取来源。"""
    url = next(
        (
            read_field(value, name)
            for name in url_names
            if read_field(value, name)
        ),
        None,
    )
    if not isinstance(url, str) or not url.strip():
        return None
    title = next(
        (
            read_field(value, name)
            for name in title_names
            if read_field(value, name)
        ),
        None,
    )
    if not isinstance(title, str) or not title.strip():
        title = urlparse(url).netloc or url
    publisher = read_field(value, "publisher") or read_field(value, "media")
    if not isinstance(publisher, str):
        publisher = None
    return LLMSource(title=title, url=url, publisher=publisher)


def deduplicate_sources(
    sources: Iterable[LLMSource],
) -> tuple[LLMSource, ...]:
    """按 URL 去重，并保持厂商返回的原始顺序。"""
    unique: list[LLMSource] = []
    seen: set[str] = set()
    for source in sources:
        if source.url in seen:
            continue
        seen.add(source.url)
        unique.append(source)
    return tuple(unique)
