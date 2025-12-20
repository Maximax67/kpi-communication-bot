from aiogram.types import Message
from aiogram.enums import ChatType

from app.db.models.organization import Organization
from bot.middlewares.db_session import LazyDbSession
from bot.utils.migrate_chat import migrate_chat


async def migrate_handler(
    message: Message,
    lazy_db: LazyDbSession,
    organization: Organization,
) -> None:
    user = message.from_user
    if user is None or organization.admin_chat_id is None:
        return

    if message.chat.type == ChatType.PRIVATE:
        await message.answer("❌ Ця команда не доступна в приватному чаті з ботом!")
        return

    db = await lazy_db.get()
    await migrate_chat(db, message, organization)
