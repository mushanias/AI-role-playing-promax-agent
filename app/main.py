"""CLI 入口：组装依赖，运行对话循环"""

from app.core.config import DEEPSEEK_API_KEY, DEEPSEEK_BASE_URL, DEEPSEEK_MODEL, STORAGE_PATH
from app.storage.json_storage import JsonStorage
from app.services.llm_client import LLMClient
from app.services.chat_service import ChatService


def main():
    """程序入口：组装依赖并运行对话循环"""
    # 1. 组装依赖（这是唯一知道"具体用哪个实现"的地方）
    storage = JsonStorage(STORAGE_PATH)
    llm_client = LLMClient(DEEPSEEK_API_KEY, DEEPSEEK_BASE_URL, DEEPSEEK_MODEL)
    chat = ChatService(storage, llm_client)

    # 2. 打印欢迎语
    print("=" * 40)
    print("  角色扮演 Agent 已启动")
    print("  输入 'quit' 退出对话")
    print("=" * 40)
    print()

    # 3. 对话循环
    while True:
        # 读取用户输入
        user_input = input("你: ").strip()

        # 空输入跳过
        if not user_input:
            continue

        # 退出指令
        if user_input.lower() == "quit":
            print("再见！")
            break

        # 发送给对话服务，拿回复
        try:
            reply = chat.send(user_input)
            print(f"AI: {reply}")
            print()  # 空行分隔，让输出更易读
        except Exception as e:
            print(f"发生错误: {e}")
            print("请检查配置或网络后重试。")
            print()


if __name__ == "__main__":
    main()