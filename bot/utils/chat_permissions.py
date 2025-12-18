from aiogram import Bot
from aiogram.enums import ChatMemberStatus
from aiogram.types import Message
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logger import logger
from app.core.enums import ChatType
from app.db.models.chat import Chat
from app.db.models.organization import Organization


async def is_chat_admin(bot: Bot, chat_id: int, user_id: int) -> bool:
    try:
        member = await bot.get_chat_member(chat_id, user_id)
        return member.status in (
            ChatMemberStatus.CREATOR,
            ChatMemberStatus.ADMINISTRATOR,
        )
    except Exception as e:
        logger.error(e)
        return False


async def check_internal_chat(message: Message, chat: Chat | None) -> bool:
    if not chat or chat.type != ChatType.INTERNAL:
        await message.answer(
            "❌ Ця команда доступна лише у внутрішніх чатах організації"
        )
        return False

    return True


async def check_chat_admin_permission(
    message: Message,
    bot: Bot,
    chat: Chat | None,
    user_id: int | None = None,
) -> bool:
    if not message.from_user:
        return False

    if not await check_internal_chat(message, chat):
        return False

    if not await is_chat_admin(bot, message.chat.id, user_id or message.from_user.id):
        await message.answer("❌ Ця команда доступна лише адміністраторам чату")
        return False

    return True


async def check_org_admin_chat(message: Message, organization: Organization) -> bool:
    if message.chat.id != organization.admin_chat_id:
        await message.answer(
            "❌ Ця команда доступна лише з чату адміністраторів організації"
        )
        return False

    return True


async def get_chat_if_admin(
    db: AsyncSession,
    message: Message,
    bot: Bot,
    organization_id: int,
    user_id: int | None = None,
) -> Chat | None:
    if user_id is None:
        if message.from_user is None:
            return None

        user_id = message.from_user.id

    result = await db.execute(
        select(Chat).where(
            Chat.id == message.chat.id, Chat.organization_id == organization_id
        )
    )
    chat = result.scalar_one_or_none()

    if chat is None or not await check_chat_admin_permission(
        message, bot, chat, user_id
    ):
        return None

    return chat
