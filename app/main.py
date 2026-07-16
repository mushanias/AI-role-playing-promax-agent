"""CLI 入口：组装依赖，运行对话循环"""

import asyncio
import logging

from app.core.dependencies import get_chat_service
from app.core.logger import setup_logging
from app.exceptions import BaseAppException

logger = logging.getLogger(__name__)


def main():
    setup_logging()
    logger.info("程序启动")
    chat = get_chat_service()

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
            reply = asyncio.run(chat.send(user_input))
            print(f"AI: {reply}")
            print()
        except BaseAppException as error:
            logger.error(f"业务错误: {error.message}", exc_info=True)
            print(f"[错误] {error.message}")


if __name__ == "__main__":
    main()
