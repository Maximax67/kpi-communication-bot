from aiogram import Bot
from aiogram.types import CallbackQuery, Message
from sqlalchemy import or_, select

from app.core.crypto import crypto
from app.core.logger import logger
from app.core.enums import CryptoInfo, MessageType, MessageStatus
from app.db.models.chat import Chat
from app.db.models.message import Message as MessageDB
from app.db.models.organization import Organization
from app.db.models.telegram_bot import TelegramBot
from bot.middlewares.db_session import LazyDbSession
from bot.callback import MessageCallback
from bot.utils.request_statuses import get_request_status_keyboard, get_status_label


async def request_status_handler(
    callback: CallbackQuery,
    callback_data: MessageCallback,
    lazy_db: LazyDbSession,
) -> None:
    if (
        not callback.message
        or not callback.from_user
        or not callback.bot
        or not isinstance(callback.message, Message)
        or not callback.message.text
    ):
        return

    db = await lazy_db.get()
    stmt = select(MessageDB).where(
        MessageDB.destination_chat_id == callback.message.chat.id,
        MessageDB.destination_message_id == callback.message.message_id,
        MessageDB.type == MessageType.SERVICE,
        MessageDB.status.is_not(None),
    )
    result = await db.execute(stmt)
    service_msg = result.scalar_one_or_none()

    if not service_msg:
        await callback.answer("❌ Повідомлення не знайдено")
        return

    new_status = MessageStatus(callback_data.data)
    new_label = get_status_label(new_status)

    old_service_text = callback.message.text.rsplit("\n", 1)[0]
    user_info = (
        f"@{callback.from_user.username}"
        if callback.from_user.username
        else callback.from_user.full_name
    )
    updated_text = f"{old_service_text}\n{new_label} [{user_info}]"

    service_msg.status = new_status
    service_msg.status_changed_by_user = callback.from_user.id
    service_msg.text = updated_text

    new_keyboard = get_request_status_keyboard(new_status)

    try:
        await callback.message.edit_text(
            text=updated_text,
            reply_markup=new_keyboard,
            parse_mode="HTML",
        )
    except Exception:
        try:
            await callback.bot.send_message(
                callback.message.chat.id,
                f"Не вдалось змінити повідомлення. Статус змінено на: {new_label} [{user_info}]",
                message_thread_id=callback.message.message_thread_id,
                reply_to_message_id=callback.message.message_id,
            )
        except Exception as e:
            logger.error(e)

    stmt2 = select(MessageDB).where(
        MessageDB.chat_id == service_msg.destination_chat_id,
        MessageDB.message_id == service_msg.destination_message_id,
        MessageDB.type == MessageType.SERVICE,
        MessageDB.status.is_not(None),
        MessageDB.is_status_reference.is_(True),
    )
    result2 = await db.execute(stmt2)
    service_msg_reference = result2.scalar_one_or_none()

    if service_msg_reference:
        if service_msg_reference.text:
            if service_msg_reference.is_within_organization:
                bot = callback.bot
            else:
                query = (
                    select(TelegramBot.id, TelegramBot.token)
                    .join(Organization)
                    .outerjoin(Chat)
                    .where(
                        or_(
                            Chat.id == service_msg_reference.destination_chat_id,
                            Organization.admin_chat_id
                            == service_msg_reference.destination_chat_id,
                        )
                    )
                    .limit(1)
                )
                bot_result_db = await db.execute(query)
                bot_result = bot_result_db.tuples().one_or_none()

                if bot_result is None:
                    await callback.answer(
                        "❌ Не вдалось знайти бота або чат через якого було надіслано повідомлення"
                    )
                    return

                bot_id, bot_token_encrypted = bot_result
                token_stripped = crypto.decrypt_data(
                    bot_token_encrypted, CryptoInfo.BOT_TOKEN
                )
                token = f"{bot_id}:{token_stripped}"
                bot = Bot(token)

            service_text = service_msg_reference.text.split("\n", 1)[1]
            updated_reference_text = f"{new_label}\n{service_text}"

            try:
                await bot.edit_message_text(
                    text=updated_reference_text,
                    chat_id=service_msg_reference.destination_chat_id,
                    message_id=service_msg_reference.destination_message_id,
                )
            except Exception:
                try:
                    await bot.send_message(
                        service_msg_reference.destination_chat_id,
                        f"Не вдалось змінити повідомлення. Статус змінено на: {new_label}",
                        message_thread_id=service_msg_reference.destination_thread_id,
                        reply_to_message_id=service_msg_reference.destination_message_id,
                    )
                except Exception as e:
                    logger.error(e)
            finally:
                if not service_msg_reference.is_within_organization:
                    await bot.session.close()

            service_msg_reference.text = updated_reference_text

        service_msg_reference.status = new_status
        service_msg_reference.status_changed_by_user = callback.from_user.id

    await db.commit()
    await callback.answer()
