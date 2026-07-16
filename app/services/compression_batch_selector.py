from typing import Dict, List


class CompressionBatchSelector:
    """选择应压缩的旧消息，保留最近完整对话轮次。"""

    def __init__(self, recent_turns_keep: int) -> None:
        if recent_turns_keep < 1:
            raise ValueError("最近保留轮次必须大于 0")

        self.recent_turns_keep = recent_turns_keep

    def select(
        self,
        messages: List[Dict[str, str]],
    ) -> List[Dict[str, str]]:
        """返回本次应压缩的最早完整轮次消息。"""
        keep_message_count = self.recent_turns_keep * 2

        if len(messages) <= keep_message_count:
            return []

        batch = messages[:-keep_message_count]

        # 压缩批次必须结束在 assistant 消息，
        # 不能把一轮对话中的 user 消息单独压缩。
        while batch and batch[-1]["role"] != "assistant":
            batch.pop()

        return batch