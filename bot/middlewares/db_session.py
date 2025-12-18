from typing import Any, Callable, Awaitable
from aiogram import BaseMiddleware
from aiogram.types import TelegramObject
from sqlalchemy.ext.asyncio import async_sessionmaker, AsyncSession


class LazyDbSession:
    def __init__(self, sessionmaker: async_sessionmaker[AsyncSession]):
        self._sessionmaker = sessionmaker
        self._session: AsyncSession | None = None

    async def get(self) -> AsyncSession:
        if self._session is None:
            self._session = self._sessionmaker()

        return self._session

    async def close(self) -> None:
        if self._session:
            await self._session.close()
            self._session = None


class DbSessionMiddleware(BaseMiddleware):
    def __init__(self, sessionmaker: async_sessionmaker[AsyncSession]):
        super().__init__()
        self._sessionmaker = sessionmaker

    async def __call__(
        self,
        handler: Callable[[TelegramObject, dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: dict[str, Any],
    ) -> Any:
        lazy_db = LazyDbSession(self._sessionmaker)
        data["lazy_db"] = lazy_db

        try:
            return await handler(event, data)
        finally:
            await lazy_db.close()
