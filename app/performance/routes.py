"""性能指标只读接口和轻量仪表盘。"""

from pathlib import Path
from typing import Dict, List

from fastapi import APIRouter, Depends, Query
from fastapi.responses import HTMLResponse

from app.auth import require_local_user
from app.core.dependencies import get_performance_recorder
from app.performance.recorder import (
    CsvPerformanceRecorder,
    PerformanceRow,
)


router = APIRouter(
    prefix="/performance",
    tags=["performance"],
    dependencies=[Depends(require_local_user)],
)
_DASHBOARD_PATH = Path(__file__).with_name("dashboard.html")


@router.get("", response_class=HTMLResponse, include_in_schema=False)
async def performance_dashboard() -> HTMLResponse:
    """返回不依赖前端框架的单文件性能面板。"""
    html = _DASHBOARD_PATH.read_text(encoding="utf-8")
    return HTMLResponse(html)


@router.get("/data")
async def get_performance_data(
    limit: int = Query(default=200, ge=1, le=5000),
    recorder: CsvPerformanceRecorder = Depends(
        get_performance_recorder
    ),
) -> Dict[str, List[PerformanceRow]]:
    """返回最近的性能记录，供仪表盘或其他工具读取。"""
    return {"records": await recorder.load_recent(limit)}
