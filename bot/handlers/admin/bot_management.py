import html
from aiogram import Bot
from aiogram.types import Message
from sqlalchemy import select, delete
import secrets

from app.core.bot_cache import remove_telegram_bot
from app.core.settings import settings
from app.core.crypto import crypto
from app.core.enums import CryptoInfo
from app.core.logger import logger
from app.db.models.telegram_bot import TelegramBot
from bot.middlewares.db_session import LazyDbSession
from bot.root_bot import ROOT_BOT
from bot.utils.format_user import format_user_info
from bot.utils.get_organization import get_organization_from_message
from bot.utils.set_bot_commands import set_bot_commands_for_private_chats
from bot.utils.set_webhook import init_webhook


async def set_bot_handler(
    message: Message,
    lazy_db: LazyDbSession,
) -> None:
    if not message.text or not message.from_user:
        return

    db = await lazy_db.get()
    organization = await get_organization_from_message(db, message)

    if organization is None:
        await message.answer(
            "❌ Команда доступна для виконання лише з чату адміністраторів організації або власнику організації"
        )
        return

    if organization.id == 0:
        await message.answer("❌ Команда недоступна для root організації")
        return

    if not organization.is_verified:
        await message.answer("❌ Організація ще не верифікована!")
        return

    command_parts = message.text.split(maxsplit=1)

    if len(command_parts) < 2:
        await message.answer("❌ Використання: /set_bot токен_бота")
        return

    bot_token = command_parts[1].strip()
    temp_bot: Bot | None = None

    try:
        temp_bot = Bot(bot_token)
        me = await temp_bot.get_me()
        bot_id = me.id
        bot_username = me.username
    except Exception as e:
        logger.error(e)
        if temp_bot:
            try:
                await temp_bot.session.close()
            except Exception:
                pass

        await message.answer("❌ Помилка перевірки токену через Telegram Bot API")
        return

    result = await db.execute(select(TelegramBot).where(TelegramBot.id == bot_id))
    existing_bot = result.scalar_one_or_none()

    if existing_bot and existing_bot.organization_id != organization.id:
        await message.answer(
            f"❌ Цей бот вже прив'язаний до іншої організації (ID: {existing_bot.organization_id})"
        )
        return

    token_stripped = bot_token.split(":", 1)[1]
    token_encrypted = crypto.encrypt_data(token_stripped, CryptoInfo.BOT_TOKEN)

    if existing_bot is None:
        secret_token = secrets.token_urlsafe(32)
        secret_token_encrypted = crypto.encrypt_data(
            secret_token, CryptoInfo.WEBHOOK_SECRET
        )

        if organization.bot:
            await db.execute(
                delete(TelegramBot).where(TelegramBot.id == organization.bot.id)
            )

        new_bot = TelegramBot(
            id=bot_id,
            token=token_encrypted,
            username=bot_username,
            secret=secret_token_encrypted,
            owner=message.from_user.id,
            organization_id=organization.id,
        )
        db.add(new_bot)
    else:
        existing_bot.token = token_encrypted
        existing_bot.owner = message.from_user.id
        existing_bot.organization_id = organization.id
        secret_token = crypto.decrypt_data(
            existing_bot.secret, CryptoInfo.WEBHOOK_SECRET
        )

    await db.commit()

    try:
        await init_webhook(temp_bot, secret_token)
        await set_bot_commands_for_private_chats(temp_bot)
    finally:
        await temp_bot.session.close()

    admin_message = (
        f"<b>Бот встановлено для організації</b>\n\n"
        f"<b>Організація:</b> {html.escape(organization.title)} (ID: {organization.id})\n"
        f"<b>Bot ID:</b> <code>{bot_id}</code>\n"
        f"@{bot_username}\n"
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
        f"✅ Бот успішно встановлено!\nBot ID: {bot_id}\n@{bot_username}"
    )


async def delete_bot_handler(
    message: Message,
    lazy_db: LazyDbSession,
) -> None:
    if not message.from_user:
        return

    db = await lazy_db.get()
    organization = await get_organization_from_message(db, message)

    if organization is None:
        await message.answer(
            "❌ Команда доступна для виконання лише з чату адміністраторів організації або власнику організації"
        )
        return

    if organization.id == 0:
        await message.answer("❌ Команда недоступна для root організації")
        return

    if not organization.bot:
        await message.answer("❌ У організації немає бота")
        return

    bot_id = organization.bot.id
    bot_username = None
    temp_bot: Bot | None = None

    try:
        token_decrypted = crypto.decrypt_data(
            organization.bot.token, CryptoInfo.BOT_TOKEN
        )
        token = f"{bot_id}:{token_decrypted}"
        temp_bot = Bot(token)
        await temp_bot.delete_webhook(drop_pending_updates=True)
        me = await temp_bot.get_me()
        bot_username = me.username
    except Exception as e:
        logger.error(e)
    finally:
        if temp_bot:
            try:
                await temp_bot.session.close()
            except Exception:
                pass

    await db.delete(organization.bot)
    await db.commit()

    remove_telegram_bot(organization.bot.id)

    admin_message = (
        f"<b>Бот видалено з організації</b>\n\n"
        f"<b>Організація:</b> {html.escape(organization.title)} (ID: {organization.id})\n"
        f"<b>Bot ID:</b> <code>{bot_id}</code>\n"
        f"@{bot_username}\n"
        f"<b>Видалив:</b> {html.escape(format_user_info(message.from_user))}"
    )

    if message.from_user.username:
        admin_message += f" (@{message.from_user.username})"

    try:
        await ROOT_BOT.send_message(
            settings.ROOT_ADMIN_CHAT_ID,
            admin_message,
            message_thread_id=settings.ROOT_ADMIN_LOGS_THREAD_ID,
            parse_mode="HTML",
        )
    except Exception as e:
        logger.error(e)

    await message.answer(f"✅ Бот успішно видалено!\nBot ID: {bot_id}")
