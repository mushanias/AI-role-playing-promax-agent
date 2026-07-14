"""Prompt 加载器：从外部文件读取 prompt，自动计算版本号

注意：
- 修改 prompt 文件后，需要重启应用才会生效（lru_cache 缓存在进程内）。
- 新版本号（hash）会与旧 ContextState 的 prompt_version 不匹配，触发缓存失效重算。
"""

import os
import re
import hashlib
import logging
from functools import lru_cache

logger = logging.getLogger(__name__)

# prompt 名称格式限制：字母、数字、下划线、短横线，1-64 字符
# 防止将来把外部输入直接传进来时出现路径穿越
_PROMPT_NAME_PATTERN = re.compile(r"^[A-Za-z0-9_-]{1,64}$")


class PromptLoader:
    """从外部文件加载 prompt 内容

    - prompt 内容不写死在代码里，从 prompts 目录读取 .md 文件
    - 版本号 = 文件内容的 hash（前 16 位），文件改了版本自动变
    - lru_cache 缓存在内存，同一进程内不重复读文件
    - 修改 prompt 文件后需重启应用，新版本才生效
    """

    def __init__(self, prompts_dir: str):
        """初始化
        Args:
            prompts_dir: prompt 文件所在目录的绝对路径
        """
        self.prompts_dir = str(prompts_dir)
        logger.debug(f"PromptLoader 初始化，目录: {self.prompts_dir}")

    @lru_cache(maxsize=32)
    def load(self, prompt_name: str) -> tuple[str, str]:
        """加载 prompt（带缓存）

        同一进程内对相同 prompt_name 只读一次文件。
        修改 prompt 文件后需重启应用或调用 load.cache_clear() 才能重新读取。

        Args:
            prompt_name: 文件名（不含扩展名），如 "compression_prompt"
        Returns:
            (prompt_content, version)
            - prompt_content: 文件文本内容
            - version: 文件内容的 hash 前 16 位，文件改了自动变
        """
        # 校验 prompt 名称，防止路径穿越
        if not _PROMPT_NAME_PATTERN.fullmatch(prompt_name):
            raise ValueError(f"非法的 prompt 名称: {prompt_name}")

        file_path = os.path.join(self.prompts_dir, f"{prompt_name}.md")

        if not os.path.exists(file_path):
            raise FileNotFoundError(f"Prompt 文件不存在: {file_path}")

        with open(file_path, "r", encoding="utf-8") as f:
            content = f.read()

        # 版本号 = 文件内容的 hash 前 16 位
        version = hashlib.sha256(content.encode("utf-8")).hexdigest()[:16]

        logger.debug(f"加载 prompt: {prompt_name}，版本: {version}，长度: {len(content)}")
        return content, version
