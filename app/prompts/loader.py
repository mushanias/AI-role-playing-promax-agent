"""Prompt 加载器：从外部文件读取 prompt，自动计算版本号"""

import os
import hashlib
import logging
from functools import lru_cache

logger = logging.getLogger(__name__)


class PromptLoader:
    """从外部文件加载 prompt 内容

    - prompt 内容不写死在代码里，从 app/prompts/ 目录读取
    - 版本号 = 文件内容的 hash，文件改了版本自动变
    - 加载后缓存在内存，不重复读文件
    """

    def __init__(self, prompts_dir: str):
        """初始化
        Args:
            prompts_dir: prompt 文件所在目录，如 "app/prompts"
        """
        self.prompts_dir = prompts_dir
        logger.debug(f"PromptLoader 初始化，目录: {prompts_dir}")

    def load(self, prompt_name: str) -> tuple[str, str]:
        """加载 prompt
        Args:
            prompt_name: 文件名（不含扩展名），如 "compression_prompt"
        Returns:
            (prompt_content, version)
            - prompt_content: 文件文本内容
            - version: 文件内容的 hash（前 8 位），文件改了自动变
        """
        file_path = os.path.join(self.prompts_dir, f"{prompt_name}.md")

        if not os.path.exists(file_path):
            raise FileNotFoundError(f"Prompt 文件不存在: {file_path}")

        with open(file_path, "r", encoding="utf-8") as f:
            content = f.read()

        # 版本号 = 文件内容的 hash 前 8 位
        version = hashlib.sha256(content.encode("utf-8")).hexdigest()[:8]

        logger.debug(f"加载 prompt: {prompt_name}，版本: {version}，长度: {len(content)}")
        return content, version