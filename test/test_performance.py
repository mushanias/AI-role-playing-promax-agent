"""性能 CSV 记录器与只读展示接口测试。"""

import csv
import tempfile
import unittest
from pathlib import Path

from app.performance.recorder import CsvPerformanceRecorder, FIELDNAMES
from app.performance.routes import (
    get_performance_data,
    performance_dashboard,
)


class PerformanceRecorderTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self) -> None:
        self.temporary_directory = tempfile.TemporaryDirectory()
        self.file_path = Path(
            self.temporary_directory.name,
            "nested",
            "performance.csv",
        )
        self.recorder = CsvPerformanceRecorder(str(self.file_path))

    async def asyncTearDown(self) -> None:
        self.temporary_directory.cleanup()

    async def test_record_creates_csv_and_returns_typed_rows(self) -> None:
        await self.recorder.record(
            conversation_id="conversation-1",
            branch_id="branch-main",
            total_ms=125.678,
            context_ms=10.234,
            llm_ms=100.456,
            input_tokens=1234,
            compression_passes=2,
            quality_degraded=True,
        )

        rows = await self.recorder.load_recent()
        self.assertTrue(self.file_path.exists())
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["total_ms"], 125.68)
        self.assertEqual(rows[0]["input_tokens"], 1234)
        self.assertEqual(rows[0]["compression_passes"], 2)
        self.assertIs(rows[0]["quality_degraded"], True)

        with self.file_path.open(
            "r",
            encoding="utf-8",
            newline="",
        ) as file:
            reader = csv.reader(file)
            self.assertEqual(tuple(next(reader)), FIELDNAMES)

    async def test_load_recent_limits_from_the_end(self) -> None:
        for index in range(3):
            await self.recorder.record(
                conversation_id=f"conversation-{index}",
                branch_id="branch-main",
                total_ms=index,
                context_ms=index,
                llm_ms=index,
                input_tokens=index,
                compression_passes=0,
                quality_degraded=False,
            )

        rows = await self.recorder.load_recent(limit=2)
        self.assertEqual(
            [row["conversation_id"] for row in rows],
            ["conversation-1", "conversation-2"],
        )

    async def test_missing_file_returns_empty_rows(self) -> None:
        self.assertEqual(await self.recorder.load_recent(), [])

    async def test_data_endpoint_uses_injected_recorder(self) -> None:
        await self.recorder.record(
            conversation_id="conversation-endpoint",
            branch_id="branch-main",
            total_ms=1,
            context_ms=1,
            llm_ms=1,
            input_tokens=1,
            compression_passes=0,
            quality_degraded=False,
        )

        payload = await get_performance_data(
            limit=10,
            recorder=self.recorder,
        )
        self.assertEqual(
            payload["records"][0]["conversation_id"],
            "conversation-endpoint",
        )

    async def test_dashboard_is_single_self_contained_page(self) -> None:
        response = await performance_dashboard()
        html = response.body.decode("utf-8")

        self.assertIn("<title>性能面板</title>", html)
        self.assertIn("/performance/data", html)
        self.assertNotIn("<script src=", html)
        self.assertNotIn("<link rel=", html)


if __name__ == "__main__":
    unittest.main()
