"""默认不变事实的读取与保存接口。"""

from fastapi import APIRouter, Depends

from app.auth import require_local_user
from app.core.dependencies import get_fact_set_service
from app.fact_sets.schemas import FactSetResponse, FactSetUpdateRequest
from app.fact_sets.service import FactSetService


router = APIRouter(
    prefix="/fact-set",
    tags=["fact-set"],
    dependencies=[Depends(require_local_user)],
)


@router.get("", response_model=FactSetResponse)
async def get_fact_set(
    service: FactSetService = Depends(get_fact_set_service),
) -> FactSetResponse:
    fact_set = await service.get()
    return FactSetResponse(
        content=fact_set.content,
        updated_at=fact_set.updated_at,
    )


@router.put("", response_model=FactSetResponse)
async def replace_fact_set(
    request: FactSetUpdateRequest,
    service: FactSetService = Depends(get_fact_set_service),
) -> FactSetResponse:
    fact_set = await service.replace(request.content)
    return FactSetResponse(
        content=fact_set.content,
        updated_at=fact_set.updated_at,
    )
