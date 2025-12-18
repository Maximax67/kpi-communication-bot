from aiogram.types import Message
from aiogram.enums import ChatType
from aiogram.fsm.context import FSMContext

from app.db.models.organization import Organization
from bot.middlewares.db_session import LazyDbSession
from bot.utils.chat_verify import chat_verify, verify_captain_private_chat


async def start_handler(
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

    if organization.id == 0:
        if is_private and organization.is_admins_accept_messages:
            if organization.greeting_message:
                await message.answer(organization.greeting_message)
            else:
                await message.answer(
                    f"Це бот для комунікації з {organization.title}. Аби звернутись до нас просто напишіть ваше повідомлення.",
                )

            return

        if message.chat.id == organization.admin_chat_id:
            await message.answer(
                "Вітаю, якщо потрібна допомога надішліть команду /help"
            )
            return

        await message.answer(
            "❌ Цей бот не призначений для використання в цьому чаті. Будь ласка створіть власну організацію командою /create_organization"
        )
        return

    if is_private:
        await verify_captain_private_chat(db, message, organization)

        if organization.is_admins_accept_messages:
            if organization.greeting_message:
                await message.answer(organization.greeting_message)
            else:
                await message.answer(
                    f"Це бот для комунікації з {organization.title}. Аби звернутись до нас просто напишіть ваше повідомлення.",
                )
        else:
            await message.answer(
                "Дякую що завітали у ботика. Адміністратори не приймають повідомлень з приватних повідомлень. Бот лише для листування між внутрішніми чатами організації."
            )
            return

    else:
        if message.chat.id == organization.admin_chat_id:
            await message.answer(
                "Вітаю, якщо потрібна допомога надішліть команду /help"
            )
            return

        await chat_verify(db, message, organization, is_bot_added=False)
