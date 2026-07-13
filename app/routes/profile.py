"""设定路由：CRUD（异步）"""

from fastapi import APIRouter, Depends, Query

from app.schemas.profile import (
    ProfileResponse,
    ProfileUpdateRequest,
    SettingUpdateRequest,
)
from app.storage.profile_storage import ProfileStorage
from app.core.dependencies import get_profile_storage

router = APIRouter(prefix="/profile", tags=["profile"])


@router.get("", response_model=ProfileResponse)
async def get_profile(
    storage: ProfileStorage = Depends(get_profile_storage),
) -> ProfileResponse:
    """获取全部设定"""
    settings = await storage.load_profile()
    return ProfileResponse(settings=settings)


@router.put("", response_model=ProfileResponse)
async def update_profile(
    request: ProfileUpdateRequest,
    storage: ProfileStorage = Depends(get_profile_storage),
) -> ProfileResponse:
    """全量更新设定（覆盖）"""
    await storage.save_profile(request.settings)
    return ProfileResponse(settings=request.settings)


@router.post("/setting", response_model=ProfileResponse)
async def set_setting(
    request: SettingUpdateRequest,
    storage: ProfileStorage = Depends(get_profile_storage),
) -> ProfileResponse:
    """新增或修改单个设定项"""
    await storage.set_setting(request.key, request.value)
    settings = await storage.load_profile()
    return ProfileResponse(settings=settings)


@router.delete("/setting", response_model=ProfileResponse)
async def delete_setting(
    key: str = Query(..., description="要删除的设定项 key"),
    storage: ProfileStorage = Depends(get_profile_storage),
) -> ProfileResponse:
    """删除单个设定项"""
    await storage.delete_setting(key)
    settings = await storage.load_profile()
    return ProfileResponse(settings=settings)
