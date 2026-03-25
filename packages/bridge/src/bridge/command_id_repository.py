from sqlalchemy.dialects.sqlite import insert
from sqlalchemy.ext.asyncio import AsyncSession

from bridge.models import CommandId, now_utc


class CommandIdRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def next(self) -> CommandId:
        statement = (
            insert(CommandId)
            .values(id=1, value=1, updated_at=now_utc())
            .on_conflict_do_update(
                index_elements=[CommandId.id],
                set_={
                    CommandId.value: CommandId.value + 1,
                    CommandId.updated_at: now_utc(),
                },
            )
            .returning(CommandId)
            .execution_options(populate_existing=True)
        )
        result = await self._session.execute(statement)
        return result.scalar_one()
