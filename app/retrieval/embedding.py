"""基于 FastEmbed 的固定中文向量模型适配器。"""

from collections.abc import Sequence
from typing import Any

import numpy as np


DEFAULT_EMBEDDING_MODEL = "BAAI/bge-small-zh-v1.5"
DEFAULT_EMBEDDING_DIMENSION = 512


class FastEmbedTextEmbedder:
    """延迟加载本地模型，避免空知识库和普通请求占用内存。"""

    def __init__(
        self,
        model_name: str = DEFAULT_EMBEDDING_MODEL,
        dimension: int = DEFAULT_EMBEDDING_DIMENSION,
    ) -> None:
        self._model_name = model_name
        self._dimension = dimension
        self._model: Any | None = None

    @property
    def model_name(self) -> str:
        return self._model_name

    @property
    def dimension(self) -> int:
        return self._dimension

    def embed(self, texts: Sequence[str]) -> list[list[float]]:
        """生成单位长度向量，并验证索引绑定的向量维度。"""
        if not texts:
            return []

        model = self._get_model()
        vectors: list[list[float]] = []
        for vector in model.embed(list(texts)):
            array = np.asarray(vector, dtype="float32")
            if array.shape != (self.dimension,):
                raise ValueError(
                    f"向量维度不一致：期望 {self.dimension}，"
                    f"实际 {array.shape}"
                )
            norm = float(np.linalg.norm(array))
            if norm > 0:
                array = array / norm
            vectors.append(array.tolist())
        return vectors

    def _get_model(self):
        if self._model is None:
            from fastembed import TextEmbedding

            self._model = TextEmbedding(model_name=self.model_name)
        return self._model
