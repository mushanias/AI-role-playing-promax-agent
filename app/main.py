"""FastAPI 应用的唯一入口。"""

import logging

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from app.conversations.routes import router as conversations_router
from app.core.error_mapping import map_app_exception
from app.core.logger import setup_logging
from app.exceptions import BaseAppException
from app.llm.routes import router as llm_router
from app.performance.routes import router as performance_router
from app.retrieval.routes import router as retrieval_router

setup_logging()
logger = logging.getLogger(__name__)

app = FastAPI(
    title="版本化会话引擎",
    description="支持会话分支、历史回退和上下文压缩的通用后端",
    version="0.2.0",
)

app.include_router(conversations_router)
app.include_router(llm_router)
app.include_router(performance_router)
app.include_router(retrieval_router)


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


@app.get("/")
async def root() -> dict[str, str]:
    return {"status": "ok"}
