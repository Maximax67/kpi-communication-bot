import html
from aiogram.types import Message
from aiogram.enums import ChatType
from sqlalchemy import exists, select

from app.core.settings import settings
from app.core.logger import logger
from app.db.models.organization import Organization
from bot.middlewares.db_session import LazyDbSession
from bot.middlewares.organization import OrganizationCache
from bot.root_bot import ROOT_BOT
from bot.utils.format_user import format_user_info
from bot.utils.set_bot_commands import set_bot_commands_for_admin_chat


async def set_admin_chat_handler(
    message: Message,
    organization: Organization,
    organization_cache: OrganizationCache,
    lazy_db: LazyDbSession,
) -> None:
    if not message.from_user or not message.bot:
        return

    if organization.bot and message.from_user.id != organization.owner:
        await message.answer(
            "❌ Тільки власник організації зі свого бота може встановити адмін чат"
        )
        return

    if message.chat.type == ChatType.PRIVATE:
        await message.answer(
            "❌ Не можна встановлювати чат для адміністраторів у приватних з ботом"
        )
        return

    if message.chat.type == ChatType.CHANNEL:
        await message.answer(
            "❌ Не можна встановлювати канал як чат для адміністраторів"
        )
        return

    if (
        organization.admin_chat_id == message.chat.id
        and organization.admin_chat_thread_id == message.message_thread_id
    ):
        await message.answer("❌ Наразі вже встановлений цей чат")
        return

    db = await lazy_db.get()

    check_if_org_exist_stmt = select(
        exists().where(Organization.admin_chat_id == message.chat.id)
    )
    check_result = await db.execute(check_if_org_exist_stmt)
    org_exists = check_result.scalar()

    if org_exists:
        await message.answer("❌ Вже існує організація, яка підв'язана до цього чату")
        return

    organization.admin_chat_id = message.chat.id
    organization.admin_chat_thread_id = message.message_thread_id
    db.add(organization)

    await db.commit()

    organization_cache.update(organization)

    chat_info = f"<b>Chat ID</b>: <code>{organization.admin_chat_id}</code>"
    if message.message_thread_id:
        chat_info += f"\n<b>Thread ID</b>: <code>{message.message_thread_id}</code>"

    admin_message = (
        f"<b>Новий чат задано для організації</b>\n\n"
        f"<b>Організація:</b> {html.escape(organization.title)} (ID: {organization.id})\n"
        f"<b>Чат:</b> {html.escape(message.chat.full_name)}\n"
        f"{chat_info}\n"
        f"<b>Встановив:</b> {html.escape(format_user_info(message.from_user))}"
    )

    try:
        await ROOT_BOT.send_message(
            settings.ROOT_ADMIN_CHAT_ID,
            admin_message,
            message_thread_id=settings.ROOT_ADMIN_LOGS_THREAD_ID,
            parse_mode="HTML",
        )
    except Exception as e:
        logger.error(e)

    await message.answer(
        f"✅ Адмін чат встановлено!\n{chat_info}",
        parse_mode="HTML",
    )

    await set_bot_commands_for_admin_chat(message.bot, message.chat.id)
