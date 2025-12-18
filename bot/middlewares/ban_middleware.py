from typing import Any, Awaitable, Callable
from aiogram import BaseMiddleware
from aiogram.types import TelegramObject, Message, Update, CallbackQuery
from cachetools import TTLCache
from sqlalchemy import delete, exists, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.banned_user import BannedUser
from app.db.models.organization import Organization
from bot.middlewares.db_session import LazyDbSession


class BanController:
    def __init__(self, ttl_seconds: int = 300, maxsize: int = 1000):
        self._cache: TTLCache[tuple[int, int], bool] = TTLCache(
            maxsize=maxsize,
            ttl=ttl_seconds,
        )

    async def get(
        self, db: AsyncSession | LazyDbSession, user_id: int, organization_id: int
    ) -> bool | None:
        cached = self._cache.get((user_id, organization_id))
        if cached is not None:
            return cached

        if isinstance(db, LazyDbSession):
            db = await db.get()

        return await self.get_from_database(db, user_id, organization_id)

    async def get_from_database(
        self, db: AsyncSession, user_id: int, organization_id: int
    ) -> bool:
        stmt = select(
            exists().where(
                BannedUser.organization_id == organization_id,
                BannedUser.user_id == user_id,
            )
        )
        result = await db.execute(stmt)
        is_banned = bool(result.scalar())

        self._set_cache(user_id, organization_id, is_banned)

        return is_banned

    def _set_cache(self, user_id: int, organization_id: int, banned: bool) -> None:
        self._cache[(user_id, organization_id)] = banned

    async def ban_user(
        self,
        db: AsyncSession,
        user_id: int,
        organization_id: int,
        banned_by: int,
        reason: str | None = None,
    ) -> bool:
        if await self.get(db, user_id, organization_id):
            return False

        banned_user = BannedUser(
            organization_id=organization_id,
            user_id=user_id,
            banned_by=banned_by,
            reason=reason,
        )

        db.add(banned_user)
        await db.commit()

        self._set_cache(user_id, organization_id, True)

        return True

    async def unban_user(
        self, db: AsyncSession, user_id: int, organization_id: int
    ) -> bool:
        if not await self.get(db, user_id, organization_id):
            return False

        delete_query = delete(BannedUser).where(
            BannedUser.organization_id == organization_id,
            BannedUser.user_id == user_id,
        )
        await db.execute(delete_query)
        await db.commit()

        self._set_cache(user_id, organization_id, False)

        return True


class BanMiddleware(BaseMiddleware):
    def __init__(self, ttl_seconds: int = 300, maxsize: int = 1000):
        super().__init__()
        self._controller = BanController(ttl_seconds, maxsize)

    async def __call__(
        self,
        handler: Callable[[TelegramObject, dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: dict[str, Any],
    ) -> Any:
        lazy_db: LazyDbSession = data["lazy_db"]
        organization: Organization = data["organization"]

        user_id: int | None = None
        chat_id: int | None = None
        callback: CallbackQuery | None = None

        if isinstance(event, Update):
            tg_object = event.message or event.edited_message
            if tg_object:
                if tg_object.from_user:
                    user_id = tg_object.from_user.id
                    chat_id = tg_object.chat.id

            elif event.callback_query:
                callback = event.callback_query
                user_id = event.callback_query.from_user.id
                msg = event.callback_query.message
                if msg:
                    chat_id = msg.chat.id

        elif isinstance(event, Message):
            chat_id = event.chat.id
            if event.from_user:
                user_id = event.from_user.id

        elif isinstance(event, CallbackQuery):
            user_id = event.from_user.id
            callback = event
            if event.message:
                chat_id = event.message.chat.id

        if (
            user_id
            and chat_id != organization.admin_chat_id
            and await self._controller.get(lazy_db, user_id, organization.id)
        ):
            if callback:
                await callback.answer("❌ Вас було заблоковано")

            return

        data["ban_controller"] = self._controller

        return await handler(event, data)
