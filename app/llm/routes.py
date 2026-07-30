"""LLM 模型目录与无状态连接测试接口。"""

from fastapi import APIRouter

from app.llm import (
    DEFAULT_LLM_MODEL,
    DEFAULT_LLM_PROVIDER,
    MODEL_SETTINGS,
    build_llm_model,
)
from app.llm.connection_service import LLMConnectionService
from app.llm.schemas import (
    LLMConnectionTestRequest,
    LLMConnectionTestResponse,
    LLMPresetListResponse,
    LLMProviderResponse,
)

router = APIRouter(prefix="/llm", tags=["llm"])


@router.get("/presets", response_model=LLMPresetListResponse)
async def list_llm_presets() -> LLMPresetListResponse:
    """返回浏览器可展示的内置模型预设，不包含 API Key。"""
    return LLMPresetListResponse(
        default_provider=DEFAULT_LLM_PROVIDER,
        default_model=DEFAULT_LLM_MODEL,
        providers=[
            LLMProviderResponse(
                id=provider,
                name=setting["name"],
                models=list(setting["models"]),
                default_model=setting["request_params"]["model"],
                docs_url=setting["docs_url"],
                supports_native_search=setting["supports_native_search"],
                context_window=setting["context_window"],
            )
            for provider, setting in MODEL_SETTINGS.items()
        ],
    )

#这个路由暴露热插拔llm
@router.post(
    "/connection-test",
    response_model=LLMConnectionTestResponse,
)
async def test_llm_connection(
    request: LLMConnectionTestRequest,
) -> LLMConnectionTestResponse:
    """使用内置或自定义预设执行一次无状态连接测试。"""
    api_key = request.api_key.get_secret_value()
    if request.custom_preset is not None:
        custom = request.custom_preset
        token_parameter = (
            "max_output_tokens"
            if custom.sdk == "openai_responses"
            else "max_tokens"
        )
        custom_setting = {
            "name": custom.name,
            "sdk": custom.sdk,
            "client_params": {
                "base_url": str(custom.base_url).rstrip("/"),
            },
            "request_params": {
                "model": custom.model,
                token_parameter: custom.max_tokens,
            },
        }
        model = build_llm_model(
            api_key=api_key,
            custom_setting=custom_setting,
        )
    else:
        provider = request.provider or DEFAULT_LLM_PROVIDER
        selected_model = request.model
        if request.provider is None and selected_model is None:
            selected_model = DEFAULT_LLM_MODEL
        model = build_llm_model(
            api_key=api_key,
            provider=provider,
            model=selected_model,
        )

    success = await LLMConnectionService().test_connection(model)
    message = (
        "连接成功"
        if success
        else "模型已响应，但没有严格返回“连接成功”"
    )
    return LLMConnectionTestResponse(success=success, message=message)
