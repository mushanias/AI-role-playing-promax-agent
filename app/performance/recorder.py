"""把每次成功对话的核心性能指标追加到 CSV。"""

import asyncio
import csv
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Protocol, Union


MetricValue = Union[str, int, float, bool]
PerformanceRow = Dict[str, MetricValue]

FIELDNAMES = (
    "timestamp",
    "conversation_id",
    "branch_id",
    "total_ms",
    "context_ms",
    "llm_ms",
    "input_tokens",
    "compression_passes",
    "quality_degraded",
)


class PerformanceSink(Protocol):
    """聊天服务唯一依赖的性能记录接口。"""

    async def record(
        self,
        *,
        conversation_id: str,
        branch_id: str,
        total_ms: float,
        context_ms: float,
        llm_ms: float,
        input_tokens: int,
        compression_passes: int,
        quality_degraded: bool,
    ) -> None:
        ...


class CsvPerformanceRecorder:
    """线程安全地追加和读取单个 CSV 指标文件。"""

    def __init__(self, file_path: str) -> None:
        self.file_path = Path(file_path)
        self._lock = asyncio.Lock()

    async def record(
        self,
        *,
        conversation_id: str,
        branch_id: str,
        total_ms: float,
        context_ms: float,
        llm_ms: float,
        input_tokens: int,
        compression_passes: int,
        quality_degraded: bool,
    ) -> None:
        row: PerformanceRow = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "conversation_id": conversation_id,
            "branch_id": branch_id,
            "total_ms": round(total_ms, 2),
            "context_ms": round(context_ms, 2),
            "llm_ms": round(llm_ms, 2),
            "input_tokens": input_tokens,
            "compression_passes": compression_passes,
            "quality_degraded": quality_degraded,
        }
        async with self._lock:
            await asyncio.to_thread(self._append, row)

    async def load_recent(self, limit: int = 200) -> List[PerformanceRow]:
        """按时间正序返回最近的指标，便于前端直接绘图。"""
        if limit < 1:
            return []
        async with self._lock:
            rows = await asyncio.to_thread(self._read_all)
        return rows[-limit:]

    def _append(self, row: PerformanceRow) -> None:
        self.file_path.parent.mkdir(parents=True, exist_ok=True)
        needs_header = (
            not self.file_path.exists()
            or self.file_path.stat().st_size == 0
        )
        with self.file_path.open(
            "a",
            encoding="utf-8",
            newline="",
        ) as file:
            writer = csv.DictWriter(file, fieldnames=FIELDNAMES)
            if needs_header:
                writer.writeheader()
            writer.writerow(row)

    def _read_all(self) -> List[PerformanceRow]:
        if not self.file_path.exists():
            return []

        with self.file_path.open(
            "r",
            encoding="utf-8",
            newline="",
        ) as file:
            return [
                self._parse_row(row)
                for row in csv.DictReader(file)
            ]

    @staticmethod
    def _parse_row(row: Dict[str, str]) -> PerformanceRow:
        return {
            "timestamp": row["timestamp"],
            "conversation_id": row["conversation_id"],
            "branch_id": row["branch_id"],
            "total_ms": float(row["total_ms"]),
            "context_ms": float(row["context_ms"]),
            "llm_ms": float(row["llm_ms"]),
            "input_tokens": int(row["input_tokens"]),
            "compression_passes": int(row["compression_passes"]),
            "quality_degraded": (
                row["quality_degraded"].strip().lower() == "true"
            ),
        }
