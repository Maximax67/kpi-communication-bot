from typing import Any, Callable, Awaitable
from aiogram import BaseMiddleware
from aiogram.enums import ChatMemberStatus, ChatType
from aiogram.types import TelegramObject, Message, ChatMemberUpdated, Update
from cachetools import TTLCache
from sqlalchemy.ext.asyncio import AsyncSession

from bot.middlewares.db_session import LazyDbSession
from bot.utils.register_user import (
    delete_user_from_chat,
    register_chat_user,
    register_user,
)


class UserCache:
    def __init__(self, ttl_seconds: int = 600, maxsize: int = 5000):
        self._users: TTLCache[int, bool] = TTLCache(maxsize=maxsize, ttl=ttl_seconds)
        self._chat_users: TTLCache[tuple[int, int], bool] = TTLCache(
            maxsize=maxsize, ttl=ttl_seconds
        )

    def has_user(self, user_id: int) -> bool:
        return user_id in self._users

    def has_chat_user(self, user_id: int, chat_id: int) -> bool:
        return (user_id, chat_id) in self._chat_users

    def add_user(self, user_id: int) -> None:
        self._users[user_id] = True

    def add_chat_user(self, user_id: int, chat_id: int) -> None:
        self._chat_users[(user_id, chat_id)] = True

    def delete_chat_user(self, user_id: int, chat_id: int) -> None:
        self._chat_users.pop((user_id, chat_id), None)


class UserMiddleware(BaseMiddleware):
    def __init__(self, ttl_seconds: int = 600, maxsize: int = 5000):
        super().__init__()
        self._cache = UserCache(ttl_seconds, maxsize)

    async def __call__(
        self,
        handler: Callable[[TelegramObject, dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: dict[str, Any],
    ) -> Any:
        lazy_db: LazyDbSession = data["lazy_db"]

        if isinstance(event, Update):
            msg = event.message or event.edited_message
            if msg:
                db = await lazy_db.get()
                if msg.chat.type == ChatType.PRIVATE:
                    await self.process_user(msg, db)
                else:
                    await self.process_chat_user(msg, db)
            elif event.chat_member:
                db = await lazy_db.get()
                await self.process_member_update(event.chat_member, db)

        elif isinstance(event, Message):
            msg = event

            db = await lazy_db.get()
            if event.chat.type == ChatType.PRIVATE:
                await self.process_user(event, db)
            else:
                await self.process_chat_user(event, db)

        elif isinstance(event, ChatMemberUpdated):
            db = await lazy_db.get()
            await self.process_member_update(event, db)

        return await handler(event, data)

    async def process_user(self, message: Message, db: AsyncSession) -> None:
        user = message.from_user
        if not user or user.is_bot:
            return

        if not self._cache.has_user(user.id):
            await register_user(db, user)
            self._cache.add_user(user.id)

    async def process_chat_user(self, message: Message, db: AsyncSession) -> None:
        user = message.from_user
        if not user or user.is_bot:
            return

        chat_id = message.chat.id

        if not self._cache.has_chat_user(user.id, chat_id):
            await register_chat_user(db, user, chat_id)
            self._cache.add_chat_user(user.id, chat_id)
            self._cache.add_user(user.id)

    async def process_member_update(
        self, event: ChatMemberUpdated, db: AsyncSession
    ) -> None:
        user = event.new_chat_member.user
        chat_id = event.chat.id

        if event.new_chat_member.status in (
            ChatMemberStatus.MEMBER,
            ChatMemberStatus.CREATOR,
            ChatMemberStatus.ADMINISTRATOR,
            ChatMemberStatus.RESTRICTED,
        ):
            if event.chat.type == ChatType.PRIVATE:
                if not self._cache.has_user(user.id):
                    await register_user(db, user)
                    self._cache.add_user(user.id)

                return

            if not self._cache.has_chat_user(user.id, chat_id):
                await register_chat_user(db, user, chat_id)
                self._cache.add_chat_user(user.id, chat_id)

        elif (
            event.new_chat_member.status
            in (
                ChatMemberStatus.LEFT,
                ChatMemberStatus.KICKED,
            )
            and event.chat.type != ChatType.PRIVATE
        ):
            await delete_user_from_chat(db, user.id, chat_id)
            self._cache.delete_chat_user(user.id, chat_id)
