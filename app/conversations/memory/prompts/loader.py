"""会话 Memory 的 Prompt 文件加载。"""

from pathlib import Path


PROMPTS_DIR = Path(__file__).resolve().parent


def load_roleplay_compression_prompt() -> str:
    """读取角色扮演压缩 Prompt。"""
    prompt_path = PROMPTS_DIR / "roleplay_compression.md"
    return prompt_path.read_text(encoding="utf-8").strip()
