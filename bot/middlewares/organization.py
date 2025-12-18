from typing import Any, Callable, Awaitable
from aiogram import BaseMiddleware, Bot
from aiogram.types import TelegramObject, Message, Update
from sqlalchemy import select
from sqlalchemy.orm import joinedload
from sqlalchemy.ext.asyncio import AsyncSession
from cachetools import TTLCache

from app.db.models.organization import Organization
from app.db.models.telegram_bot import TelegramBot
from bot.middlewares.db_session import LazyDbSession


class OrganizationCache:
    def __init__(self, ttl_seconds: int = 3600, maxsize: int = 100):
        self._cache: TTLCache[int, Organization] = TTLCache(
            maxsize=maxsize, ttl=ttl_seconds
        )

    async def get(self, db: LazyDbSession | AsyncSession, bot_id: int) -> Organization:
        if bot_id in self._cache:
            return self._cache[bot_id]

        if isinstance(db, LazyDbSession):
            async_session = await db.get()
            organization = await self.get_from_db(async_session, bot_id)
        else:
            organization = await self.get_from_db(db, bot_id)

        self._cache[bot_id] = organization

        return organization

    def update(self, organization: Organization) -> None:
        if organization.bot:
            self._cache[organization.bot.id] = organization

    def remove(self, bot_id: int) -> None:
        self._cache.pop(bot_id, None)

    @staticmethod
    async def get_from_db(
        db: AsyncSession,
        bot_id: int,
    ) -> Organization:
        q = (
            select(Organization)
            .options(joinedload(Organization.bot))
            .join(Organization.bot)
            .where(TelegramBot.id == bot_id)
            .limit(1)
        )
        result = await db.execute(q)
        organization = result.scalar_one_or_none()

        if organization is None:
            raise Exception("Bot without organization")

        return organization


class OrganizationMiddleware(BaseMiddleware):
    def __init__(self, ttl_seconds: int = 3600, maxsize: int = 100):
        super().__init__()
        self._cache = OrganizationCache(ttl_seconds, maxsize)

    async def __call__(
        self,
        handler: Callable[[TelegramObject, dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: dict[str, Any],
    ) -> Any:
        bot: Bot = data["bot"]
        bot_id = bot.id

        lazy_db: LazyDbSession = data["lazy_db"]
        organization = await self._cache.get(lazy_db, bot_id)

        if organization.admin_chat_id is None:
            message: Message | None = None

            if isinstance(event, Update):
                message = event.message
            elif isinstance(event, Message):
                message = event

            if message and organization.bot and message.from_user:
                if message.from_user.id == organization.bot.owner:
                    if message.text is None or (
                        not message.text == "/set_admin_chat"
                        and not message.text.startswith("/set_admin_chat ")
                        and not message.text.startswith("/set_admin_chat@")
                    ):
                        await message.answer(
                            "Вам необхідно задати чат для адміністраторів. Надішліть команду /set_admin_chat у бажаний чат з ботом. Якщо чат має гілки, бот надсилатиме повідомлення в гілку де вона викликана. Команда не доступна в приватному чаті з ботом."
                        )
                        return
                else:
                    return
            else:
                return

        data["organization"] = organization
        data["organization_cache"] = self._cache

        return await handler(event, data)
