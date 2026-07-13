"""FastAPI 应用入口：注册路由 + 异常处理器"""

import logging
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from app.core.logger import setup_logging
from app.exceptions import BaseAppException
from app.routes import chat_router, profile_router

setup_logging()
logger = logging.getLogger(__name__)

app = FastAPI(
    title="角色扮演 Agent",
    description="为角色扮演服务的对话 Agent",
    version="0.1.0",
)

# 注册路由
app.include_router(chat_router)
app.include_router(profile_router)


@app.exception_handler(BaseAppException)
async def app_exception_handler(request: Request, exc: BaseAppException) -> JSONResponse:
    logger.error(f"业务错误: {exc.message}", exc_info=True)
    return JSONResponse(
        status_code=400,
        content={"error": exc.message},
    )


@app.get("/")
async def root():
    return {"status": "ok"}