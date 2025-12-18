from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup
from app.core.logger import logger


async def edit_callback_message(
    callback: CallbackQuery,
    new_text: str,
    reply_markup: InlineKeyboardMarkup | None = None,
    parse_mode: str | None = None,
    answer: bool = True,
) -> None:
    is_success = False
    message = callback.message

    if isinstance(message, Message):
        try:
            await message.edit_text(
                new_text, reply_markup=reply_markup, parse_mode=parse_mode
            )
            is_success = True
        except Exception as e:
            if "message is not modified" in str(e):
                is_success = True
            else:
                logger.error(e)

        if not is_success and callback.bot:
            try:
                await callback.bot.send_message(
                    message.chat.id,
                    new_text,
                    reply_markup=reply_markup,
                    message_thread_id=message.message_thread_id,
                    parse_mode=parse_mode,
                )
                is_success = True
            except Exception as e:
                logger.error(e)

    if is_success and answer:
        await callback.answer()
        return

    raise Exception("Can not edit callback message or send a new one")
