"""CLI 入口：组装依赖，运行对话循环"""

import logging

from app.core.config import DEEPSEEK_API_KEY, DEEPSEEK_BASE_URL, DEEPSEEK_MODEL, STORAGE_PATH
from app.core.logger import setup_logging
from app.storage.json_storage import JsonStorage
from app.services.llm_client import LLMClient
from app.services.chat_service import ChatService
from app.exceptions import BaseAppException

logger = logging.getLogger(__name__)


def main():
    """程序入口：组装依赖并运行对话循环"""
    setup_logging()
    logger.info("程序启动")

    storage = JsonStorage(STORAGE_PATH)
    llm_client = LLMClient(DEEPSEEK_API_KEY, DEEPSEEK_BASE_URL, DEEPSEEK_MODEL)
    chat = ChatService(storage, llm_client)
    logger.debug("依赖组装完成")

    print("=" * 40)
    print("  角色扮演 Agent 已启动")
    print("  输入 'quit' 退出对话")
    print("=" * 40)
    print()

    while True:
        user_input = input("你: ").strip()

        if not user_input:
            continue

        if user_input.lower() == "quit":
            logger.info("用户退出对话")
            print("再见！")
            break

        try:
            reply = chat.send(user_input)
            print(f"AI: {reply}")
            print()
        except BaseAppException as e:
            logger.error(f"业务错误: {e.message}", exc_info=True)
            print(f"[错误] {e.message}")
            print()


if __name__ == "__main__":
    main()