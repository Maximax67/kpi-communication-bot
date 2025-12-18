from typing import Optional
from aiogram.types import CallbackQuery, Message
from aiogram.fsm.context import FSMContext


async def close_handler(call: CallbackQuery, state: FSMContext) -> None:
    last_message_id: Optional[int] = await state.get_value("last_message_id")

    if (
        not last_message_id
        or not call.message
        or call.message.message_id >= last_message_id
    ):
        await state.clear()

    if call.message and isinstance(call.message, Message):
        try:
            await call.message.edit_reply_markup(reply_markup=None)
        except Exception:
            await call.message.delete()

    await call.answer()
