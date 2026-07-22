"""集中定义当前项目使用的 LLM 模型。"""

import os
from dataclasses import dataclass

from dotenv import load_dotenv


load_dotenv()


@dataclass(frozen=True)
class LLMModel:
    """创建 LLM 客户端所需的模型连接配置。"""

    api_key: str
    base_url: str
    model: str


# 项目其他模块只导入这一个对象；切换模型时只需修改这里或对应环境变量。
llm_model = LLMModel(
    api_key=os.getenv("LLM_API_KEY", os.getenv("DEEPSEEK_API_KEY", "")),
    base_url=os.getenv(
        "LLM_BASE_URL",
        os.getenv("DEEPSEEK_BASE_URL", "https://api.deepseek.com"),
    ),
    model=os.getenv(
        "LLM_MODEL",
        os.getenv("DEEPSEEK_MODEL", "deepseek-chat"),
    ),
)
