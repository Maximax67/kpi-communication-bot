import html
from aiogram.types import Message
from aiogram.fsm.context import FSMContext
from sqlalchemy import select, exists
from sqlalchemy.orm import aliased

from app.db.models.organization import Organization
from app.db.models.telegram_bot import TelegramBot
from bot.middlewares.db_session import LazyDbSession


async def organizations_handler(
    message: Message,
    state: FSMContext,
    lazy_db: LazyDbSession,
) -> None:
    if message.from_user is None:
        return

    await state.clear()

    db = await lazy_db.get()

    Bot = aliased(TelegramBot)

    stmt = select(
        Organization,
        exists().where(Bot.organization_id == Organization.id).label("has_bot"),
    )

    result = await db.execute(stmt)
    rows = result.all()

    if not rows:
        await message.answer("❌ Жодна організація не створена")
        return

    message_lines = ["<b>Організації:</b>"]

    for org, has_bot in rows:
        title = html.escape(org.title)

        bot_emoji = "🤖" if has_bot else "❌"
        admin_emoji = "🛡️" if org.admin_chat_id else "❌"
        visibility_emoji = "🔒" if org.is_private else "🌐"

        line = f"{bot_emoji}{admin_emoji}{visibility_emoji} {title} "
        message_lines.append(line)

    message_to_send = "\n".join(message_lines)
    await message.answer(message_to_send, parse_mode="HTML")
