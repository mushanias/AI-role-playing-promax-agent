"""LLM 模型目录与连接测试接口的数据模型。"""

from typing import Literal, Optional

from pydantic import (
    AliasChoices,
    AnyHttpUrl,
    BaseModel,
    ConfigDict,
    Field,
    SecretStr,
)


class LLMProviderResponse(BaseModel):
    id: str
    name: str
    models: list[str]
    default_model: str
    docs_url: str


class LLMPresetListResponse(BaseModel):
    default_provider: str
    default_model: str
    providers: list[LLMProviderResponse]


class CustomLLMPresetRequest(BaseModel):
    name: str = Field(min_length=1, max_length=50)
    sdk: Literal[
        "openai_chat",
        "openai_responses",
        "anthropic",
    ] = Field(validation_alias=AliasChoices("sdk", "adapter"))
    base_url: AnyHttpUrl
    model: str = Field(min_length=1, max_length=100)
    max_tokens: int = Field(default=4096, gt=0)
    docs_url: Optional[AnyHttpUrl] = None


class LLMConnectionTestRequest(BaseModel):
    model_config = ConfigDict(
        json_schema_extra={
            "examples": [
                {"api_key": "你的 API Key"},
                {
                    "api_key": "你的 API Key",
                    "provider": "minimax",
                    "model": "MiniMax-M3",
                },
                {
                    "api_key": "你的 API Key",
                    "custom_preset": {
                        "name": "自定义模型",
                        "sdk": "openai_chat",
                        "base_url": "https://example.com/v1",
                        "model": "custom-model",
                        "max_tokens": 4096,
                    },
                },
            ]
        }
    )

    api_key: SecretStr = Field(min_length=1)
    provider: Optional[str] = None
    model: Optional[str] = None
    custom_preset: Optional[CustomLLMPresetRequest] = None


class LLMConnectionTestResponse(BaseModel):
    success: bool
    message: str


class LLMActiveModelResponse(BaseModel):
    provider: str
    model: str
    connected: bool


class LLMActivationResponse(LLMConnectionTestResponse):
    provider: str
    model: str
