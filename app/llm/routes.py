"""LLM 模型目录、连接测试与运行时模型切换接口。"""

from fastapi import APIRouter, Depends

from app.auth import require_local_user
from app.core.dependencies import get_versioned_llm_client
from app.llm import (
    DEFAULT_LLM_MODEL,
    DEFAULT_LLM_PROVIDER,
    LLMModel,
    MODEL_SETTINGS,
    build_llm_model,
)
from app.llm.client import LLMClient
from app.llm.connection_service import LLMConnectionService
from app.llm.schemas import (
    LLMActivationResponse,
    LLMActiveModelResponse,
    LLMConnectionTestRequest,
    LLMConnectionTestResponse,
    LLMPresetListResponse,
    LLMProviderResponse,
)

router = APIRouter(
    prefix="/llm",
    tags=["llm"],
    dependencies=[Depends(require_local_user)],
)


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
            )
            for provider, setting in MODEL_SETTINGS.items()
        ],
    )

@router.post(
    "/connection-test",
    response_model=LLMConnectionTestResponse,
)
async def test_llm_connection(
    request: LLMConnectionTestRequest,
) -> LLMConnectionTestResponse:
    """使用内置或自定义预设执行一次无状态连接测试。"""
    model = _build_requested_model(request)
    success = await LLMConnectionService().test_connection(model)
    message = (
        "连接成功"
        if success
        else "模型已响应，但没有严格返回“连接成功”"
    )
    return LLMConnectionTestResponse(success=success, message=message)


@router.get("/active", response_model=LLMActiveModelResponse)
async def get_active_llm(
    client: LLMClient = Depends(get_versioned_llm_client),
) -> LLMActiveModelResponse:
    """返回当前聊天实际使用的模型，不暴露 API Key。"""
    return LLMActiveModelResponse.model_validate(
        client.describe_active_model()
    )


@router.put("/active", response_model=LLMActivationResponse)
async def activate_llm(
    request: LLMConnectionTestRequest,
    client: LLMClient = Depends(get_versioned_llm_client),
) -> LLMActivationResponse:
    """连接测试成功后，原子替换后续聊天使用的模型。"""
    model = _build_requested_model(request)
    success = await LLMConnectionService().test_connection(model)
    provider = str(model.get("provider", "custom"))
    selected_model = str(model["request_params"]["model"])

    if success:
        await client.reconfigure(model)

    return LLMActivationResponse(
        success=success,
        message=(
            "连接成功，模型已启用"
            if success
            else "模型已响应，但没有严格返回“连接成功”"
        ),
        provider=provider,
        model=selected_model,
    )


def _build_requested_model(
    request: LLMConnectionTestRequest,
) -> LLMModel:
    """把 HTTP 请求转换为统一 LLM 参数字典。"""
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
        return build_llm_model(
            api_key=api_key,
            custom_setting=custom_setting,
        )

    provider = request.provider or DEFAULT_LLM_PROVIDER
    selected_model = request.model
    if request.provider is None and selected_model is None:
        selected_model = DEFAULT_LLM_MODEL
    return build_llm_model(
        api_key=api_key,
        provider=provider,
        model=selected_model,
    )
