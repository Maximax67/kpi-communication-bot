from aiogram.types import Message
from aiogram.enums import ChatType
from aiogram.fsm.context import FSMContext

from app.db.models.organization import Organization
from bot.middlewares.db_session import LazyDbSession
from bot.utils.chat_verify import chat_verify, verify_captain_private_chat


async def verify_handler(
    message: Message,
    state: FSMContext,
    lazy_db: LazyDbSession,
    organization: Organization,
) -> None:
    if (
        message.from_user is None
        or message.bot is None
        or organization.admin_chat_id is None
    ):
        return

    await state.clear()

    db = await lazy_db.get()
    is_private = message.chat.type == ChatType.PRIVATE

    if is_private:
        if not await verify_captain_private_chat(db, message, organization):
            await message.answer(
                "❌ У приватних повідомлення команда /verify призначена для ідентифікації старост. За моєю базою даних ви не є старостою академічної групи. Якщо ви дійсно староста, зв'яжіться з адміністраторами."
            )

        return

    if message.chat.id == organization.admin_chat_id:
        await message.answer("❌ Команда не може бути викликана в чаті модераторів")
        return

    await chat_verify(db, message, organization, is_bot_added=False)
