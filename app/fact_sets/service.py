"""不变事实的读取与整体替换用例。"""

from app.fact_sets.models import FactSet
from app.fact_sets.repository import FactSetRepository


class FactSetService:
    def __init__(self, repository: FactSetRepository) -> None:
        self.repository = repository

    async def get(self) -> FactSet:
        return await self.repository.load()

    async def replace(self, content: str) -> FactSet:
        return await self.repository.replace(content)
