"""FastAPI 应用入口：注册路由 + 异常处理器"""

import logging
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from app.core.logger import setup_logging
from app.exceptions import BaseAppException
from app.routes import chat_router

# 初始化日志（FastAPI 入口也要调一次）
setup_logging()
logger = logging.getLogger(__name__)

# 创建 FastAPI 应用
app = FastAPI(
    title="角色扮演 Agent",
    description="为角色扮演服务的对话 Agent",
    version="0.1.0",
)

# 注册路由
app.include_router(chat_router)


# 异常处理器：把项目异常转成 HTTP 响应
@app.exception_handler(BaseAppException)
async def app_exception_handler(request: Request, exc: BaseAppException) -> JSONResponse:
    """所有 BaseAppException 子类自动走这里
    将来想细化（key 错返回 401、网络错返回 503），在这里加判断即可
    """
    logger.error(f"业务错误: {exc.message}", exc_info=True)
    return JSONResponse(
        status_code=400,
        content={"error": exc.message},
    )


@app.get("/")
async def root():
    """根路径：健康检查"""
    return {"status": "ok"}