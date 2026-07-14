"""LLM 指令模板：从外部文件加载，不写死在代码里

prompt 内容放在 app/prompts/ 目录下的 .md 文件中。
修改 prompt 文件后，版本号（hash）自动变化，触发缓存失效重算。
"""

import json
import logging

from app.prompts.loader import PromptLoader

logger = logging.getLogger(__name__)

# 加载器实例（模块级单例，启动时读一次文件，之后用内存缓存）
_loader = PromptLoader("app/prompts")

# 加载压缩 prompt
COMPRESSION_PROMPT, COMPRESSION_PROMPT_VERSION = _loader.load("compression_prompt")


def build_compression_input(
    old_summary: str,
    current_key_states: dict,
    messages_batch: list[dict],
    target_summary_tokens: int,
) -> str:
    """拼装压缩调用的用户输入（JSON 格式）
    Args:
        old_summary: 之前的摘要（可能为空）
        current_key_states: 当前已有的关键状态（key → {value, source_message_id}）
        messages_batch: 本批被淘汰的原始消息列表（每条含 message_id, role, content）
        target_summary_tokens: 摘要的目标 token 上限
    Returns:
        JSON 格式的用户输入文本
    """
    payload = {
        "previous_summary": old_summary,
        "current_key_states": current_key_states,
        "messages": messages_batch,
        "target_summary_tokens": target_summary_tokens,
    }
    return json.dumps(payload, ensure_ascii=False, indent=2)