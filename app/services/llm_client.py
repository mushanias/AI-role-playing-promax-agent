"""LLM 客户端：封装调用 DeepSeek 的细节"""

from typing import List, Dict
from openai import OpenAI


class LLMClient:
    """LLM 客户端，封装 DeepSeek 调用"""

    def __init__(self, api_key: str, base_url: str, model: str):
        """初始化 openai SDK 客户端
        Args:
            api_key: DeepSeek 的 API Key
            base_url: DeepSeek 接口地址
            model: 模型名，如 "deepseek-chat"
        """
        self.client = OpenAI(api_key=api_key, base_url=base_url)
        self.model = model

    def chat(self, messages: List[Dict]) -> str:
        """调用 LLM 获取回复
        Args:
            messages: 历史消息列表，格式如：
                [{"role": "user", "content": "你好"},
                 {"role": "assistant", "content": "你好！"}]
            注意：传给 LLM 时只需 role 和 content，不需要 timestamp
        Returns:
            助手回复的纯文本
        """
        response = self.client.chat.completions.create(
            model=self.model,
            messages=messages,
        )
        return response.choices[0].message.content