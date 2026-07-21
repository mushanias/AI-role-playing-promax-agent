"""CLI 入口：使用新版会话与分支服务运行单个对话。"""

import asyncio
import logging

from app.core.dependencies import get_conversation_service
from app.core.logger import setup_logging
from app.exceptions import BaseAppException

logger = logging.getLogger(__name__)


async def run_chat_loop() -> None:
    """在同一事件循环中创建会话并持续发送消息。"""
    service = get_conversation_service()
    conversation = await service.create_conversation()

    print("=" * 40)
    print("  角色扮演 Agent 已启动")
    print(f"  会话 ID: {conversation.conversation_id}")
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
            result = await service.send_message(
                conversation_id=conversation.conversation_id,
                user_input=user_input,
            )
            print(f"AI: {result.reply}")
            for warning in result.warnings:
                print(f"[提示] {warning}")
            print()
        except BaseAppException as error:
            logger.error(f"业务错误: {error.message}", exc_info=True)
            print(f"[错误] {error.message}")


def main() -> None:
    setup_logging()
    logger.info("程序启动")
    asyncio.run(run_chat_loop())


if __name__ == "__main__":
    main()
