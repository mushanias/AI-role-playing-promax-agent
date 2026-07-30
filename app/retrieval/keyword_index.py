"""SQLite FTS5 关键词索引的只读适配器。"""

import sqlite3
from datetime import datetime
from pathlib import Path

from app.retrieval.contracts import KnowledgeHit


class SQLiteKeywordIndex:
    """每次查询打开只读连接，便于多线程和无状态部署。"""

    def __init__(self, database_path: str | Path) -> None:
        self.database_path = Path(database_path)

    def search(self, query: str, limit: int) -> list[KnowledgeHit]:
        """使用 FTS5 BM25 返回关键词结果。"""
        cleaned = query.strip()
        if not cleaned or limit <= 0:
            return []
        if not self.database_path.exists():
            raise FileNotFoundError("关键词索引不存在")

        uri = f"{self.database_path.resolve().as_uri()}?mode=ro"
        connection = sqlite3.connect(uri, uri=True)
        try:
            connection.row_factory = sqlite3.Row
            rows = connection.execute(
                """
                SELECT
                    chunk_id,
                    document_id,
                    title,
                    content,
                    url,
                    publisher,
                    published_at,
                    bm25(chunks) AS rank
                FROM chunks
                WHERE chunks MATCH ?
                ORDER BY rank
                LIMIT ?
                """,
                (_fts_query(cleaned), limit),
            ).fetchall()
        finally:
            connection.close()

        return [
            KnowledgeHit(
                chunk_id=row["chunk_id"],
                document_id=row["document_id"],
                title=row["title"],
                content=row["content"],
                url=row["url"] or None,
                publisher=row["publisher"] or None,
                published_at=_parse_datetime(row["published_at"]),
                score=1.0 / (1.0 + abs(float(row["rank"]))),
            )
            for row in rows
        ]


def _fts_query(query: str) -> str:
    """把用户文本变成不会改变 FTS 语法的短语查询。"""
    escaped = query.replace('"', '""')
    return f'"{escaped}"'


def _parse_datetime(value: str | None) -> datetime | None:
    return datetime.fromisoformat(value) if value else None
