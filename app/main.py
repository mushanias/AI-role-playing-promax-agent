"""FastAPI 应用的唯一入口。"""

import logging

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.auth.routes import router as auth_router
from app.conversations.routes import (
    generations_router,
    router as conversations_router,
)
from app.core.config import CORS_ALLOW_ORIGINS
from app.core.error_mapping import map_app_exception
from app.core.logger import setup_logging
from app.exceptions import BaseAppException
from app.fact_sets.routes import router as fact_set_router
from app.llm.routes import router as llm_router
from app.performance.routes import router as performance_router

setup_logging()
logger = logging.getLogger(__name__)

app = FastAPI(
    title="版本化会话引擎",
    description="支持会话分支、历史回退和上下文压缩的通用后端",
    version="0.2.0",
)


@app.middleware("http")
async def unexpected_exception_middleware(
    request: Request,
    call_next,
):
    """在 CORS 内层把未预期异常转换为稳定的 JSON 响应。"""
    try:
        return await call_next(request)
    except Exception as exc:
        return await unexpected_exception_handler(request, exc)


app.add_middleware(
    CORSMiddleware,
    allow_origins=list(CORS_ALLOW_ORIGINS),
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE"],
    allow_headers=["Content-Type"],
)

app.include_router(auth_router)
app.include_router(conversations_router)
app.include_router(generations_router)
app.include_router(fact_set_router)
app.include_router(llm_router)
app.include_router(performance_router)


@app.exception_handler(BaseAppException)
async def app_exception_handler(
    request: Request,
    exc: BaseAppException,
) -> JSONResponse:
    logger.error("业务错误: %s", exc.message, exc_info=True)
    descriptor = map_app_exception(exc)
    return JSONResponse(
        status_code=descriptor.status_code,
        content={
            "error": {
                "code": descriptor.code,
                "message": descriptor.message,
            }
        },
    )


async def unexpected_exception_handler(
    request: Request,
    exc: Exception,
) -> JSONResponse:
    """把未预期的后端异常稳定返回为 JSON，避免前端误判为断网。"""
    logger.error(
        "未处理的后端错误: %s %s",
        request.method,
        request.url.path,
        exc_info=(type(exc), exc, exc.__traceback__),
    )
    return JSONResponse(
        status_code=500,
        content={
            "error": {
                "code": "internal_server_error",
                "message": "后端处理请求时发生内部错误，请查看后端日志",
            }
        },
    )


@app.get("/")
async def root() -> dict[str, str]:
    return {"status": "ok"}
