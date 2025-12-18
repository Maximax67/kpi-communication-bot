from aiogram.types import Message, CallbackQuery
from aiogram.filters.callback_data import CallbackData
from aiogram.utils.keyboard import InlineKeyboardBuilder

from bot.callback import MainCallback
from bot.utils.edit_callback_message import edit_callback_message


async def confirm_action(
    msg_or_callback: Message | CallbackQuery,
    callback: CallbackData | str | None = None,
    text: str | None = None,
) -> None:
    text = text if text else "Підтвердити дію?"

    kb = InlineKeyboardBuilder()
    kb.button(
        text="✅ Так",
        callback_data=callback,
    )
    kb.button(
        text="❌ Ні",
        callback_data=MainCallback(action="cancel"),
    )
    kb.adjust(1)
    reply_markup = kb.as_markup()

    if isinstance(msg_or_callback, Message):
        await msg_or_callback.edit_text(text, reply_markup=reply_markup)
        return

    await edit_callback_message(msg_or_callback, text, reply_markup)
