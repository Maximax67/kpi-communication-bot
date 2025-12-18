from aiogram.types import Message
from aiogram.enums import ChatType
from aiogram.fsm.context import FSMContext

from app.db.models.organization import Organization
from bot.middlewares.db_session import LazyDbSession
from bot.utils.chat_verify import chat_verify


async def bot_added_handler(
    message: Message,
    state: FSMContext,
    lazy_db: LazyDbSession,
    organization: Organization,
) -> None:
    if (
        message.from_user is None
        or organization.admin_chat_id is None
        or message.chat.type == ChatType.PRIVATE
        or message.chat.id == organization.admin_chat_id
    ):
        return

    await state.clear()

    db = await lazy_db.get()
    await chat_verify(db, message, organization, is_bot_added=True)
