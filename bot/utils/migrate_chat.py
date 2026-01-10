from aiogram.types import Message as TelegramMessage
from aiogram.enums import ChatType
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.chat import Chat
from app.db.models.message import Message
from app.db.models.organization import Organization
from bot.middlewares.db_session import LazyDbSession
from bot.utils.captains import get_captain
from bot.utils.set_bot_commands import (
    remove_bot_commands,
    set_bot_commands_for_external_chat,
)


async def migrate_chat(
    db: AsyncSession,
    message: TelegramMessage,
    organization: Organization,
) -> None:
    user = message.from_user
    if user is None or message.bot is None:
        return

    if message.chat.type in (
        ChatType.GROUP,
        ChatType.SUPERGROUP,
        ChatType.CHANNEL,
    ):
        if message.chat.id == organization.admin_chat_id:
            await message.answer("❌ Команда не може бути викликана в чаті модераторів")
            return

        chat_stmt = select(Chat).where(
            Chat.id == message.chat.id, Chat.organization_id == organization.id
        )
        chat_result = await db.execute(chat_stmt)
        chat_to_migrate = chat_result.scalar_one_or_none()

        if chat_to_migrate is None:
            await message.answer(
                "❌ Цей чат не прив'язаний до бота. Староста має верифікувати чат командою /verify"
            )
            return

        captain = await get_captain(db, organization.id, user.id, user.username)
        if captain is None:
            await message.answer("❌ Команда /migrate призначена лише для старост")
            return

        if captain.connected_chat_id is None:
            await message.answer(
                "❌ Ви ще не прив'язали чат своєї групи. Просто надішліть команду /verify у чат, який бажаєте зробити чатом вашої групи. Якщо чат має гілки, то повідомлення будуть надходити в гілку, де була викликана ця команда."
            )
            return

        if captain.connected_chat_id == message.chat.id:
            if (
                message.chat.is_forum
                and message.message_thread_id
                == chat_to_migrate.captain_connected_thread
            ):
                await message.answer("❌ Чат групи вже підв'язаний до цієї гілки")
                return

            chat_to_migrate.captain_connected_thread = message.message_thread_id
            await db.commit()
            await message.answer("✅ Успішно мігровано на цю гілку чату")
            return

        old_chat_id = chat_to_migrate.id
        chat_to_migrate.id = message.chat.id
        chat_to_migrate.captain_connected_thread = message.message_thread_id

        await db.commit()
        await message.answer("✅ Чат групи успішно мігровано")

        await set_bot_commands_for_external_chat(message.bot, message.chat.id)

        try:
            await remove_bot_commands(message.bot, old_chat_id)
        except Exception:
            pass


async def auto_migrate(message: TelegramMessage, lazy_db: LazyDbSession) -> None:
    migrate_id = message.migrate_to_chat_id
    if migrate_id:
        chat_id = message.chat.id
        db = await lazy_db.get()

        await db.execute(update(Chat).where(Chat.id == chat_id).values(id=migrate_id))
        await db.execute(
            update(Organization)
            .where(Organization.admin_chat_id == chat_id)
            .values(admin_chat_id=migrate_id)
        )
        await db.execute(
            update(Message).where(Message.chat_id == chat_id).values(chat_id=migrate_id)
        )
        await db.execute(
            update(Message)
            .where(Message.destination_chat_id == chat_id)
            .values(destination_chat_id=migrate_id)
        )
        await db.commit()
