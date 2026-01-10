from aiogram.types import ChatMemberUpdated
from aiogram.enums import ChatType
from aiogram.fsm.context import FSMContext
from sqlalchemy import select

from app.core.settings import settings
from app.db.models.chat import Chat
from app.db.models.organization import Organization
from bot.middlewares.db_session import LazyDbSession
from bot.middlewares.organization import OrganizationCache
from bot.root_bot import ROOT_BOT
from bot.utils.captains import get_captain
from bot.utils.format_user import format_user_info


async def bot_removed_handler(
    update: ChatMemberUpdated,
    state: FSMContext,
    lazy_db: LazyDbSession,
    organization: Organization,
    organization_cache: OrganizationCache,
) -> None:
    if (
        update.from_user is None
        or update.bot is None
        or organization.admin_chat_id is None
    ):
        return

    await state.clear()
    db = await lazy_db.get()

    if update.chat.type == ChatType.PRIVATE:
        captain = await get_captain(
            db, organization.id, update.from_user.id, update.from_user.username
        )

        if captain is None:
            return

        captain.is_bot_blocked = True
        await db.commit()
        await update.bot.send_message(
            organization.admin_chat_id,
            f"Староста {captain.chat_title} {format_user_info(update.from_user)} заблокував бота!",
            message_thread_id=organization.admin_chat_thread_id,
        )
        return

    if organization.admin_chat_id == update.chat.id:
        organization.admin_chat_id = None
        organization.admin_chat_thread_id = None
        await db.merge(organization)
        await db.commit()

        organization_cache.update(organization)

        await ROOT_BOT.send_message(
            settings.ROOT_ADMIN_CHAT_ID,
            f"Бота було видалено з адмін чату організації {organization.title}!",
            message_thread_id=settings.ROOT_ADMIN_LOGS_THREAD_ID,
        )
        return

    chat_stmt = select(Chat).where(
        Chat.id == update.chat.id, Chat.organization_id == organization.id
    )
    chat_result = await db.execute(chat_stmt)
    chat_from_kicked = chat_result.scalar_one_or_none()

    if chat_from_kicked is None:
        return

    await db.delete(chat_from_kicked)
    await db.commit()

    await update.bot.send_message(
        organization.admin_chat_id,
        f"Бота було видалено з чату {chat_from_kicked.title} користувачем {format_user_info(update.from_user)}",
        message_thread_id=organization.admin_chat_thread_id,
    )
