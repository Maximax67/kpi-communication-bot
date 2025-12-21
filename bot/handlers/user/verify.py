from aiogram.types import Message
from aiogram.enums import ChatType as TelegramChatType

from app.core.enums import ChatType
from app.db.models.organization import Organization
from bot.middlewares.db_session import LazyDbSession
from bot.utils.chat_verify import chat_verify, verify_captain_private_chat


async def verify_handler(
    message: Message,
    lazy_db: LazyDbSession,
    organization: Organization,
) -> None:
    if (
        message.from_user is None
        or message.bot is None
        or organization.admin_chat_id is None
    ):
        return

    db = await lazy_db.get()

    if message.chat.type == TelegramChatType.PRIVATE:
        if not await verify_captain_private_chat(db, message, organization):
            await message.answer(
                "❌ У приватних повідомлення команда /verify призначена для ідентифікації старост. За моєю базою даних ви не є старостою академічної групи. Якщо ви дійсно староста, зв'яжіться з адміністраторами."
            )

        return

    if message.chat.id == organization.admin_chat_id:
        await message.answer("❌ Команда не може бути викликана в чаті модераторів")
        return

    await chat_verify(db, message, organization, is_bot_added=False)


async def verify_with_type(
    message: Message,
    lazy_db: LazyDbSession,
    organization: Organization,
    verify_type: ChatType,
) -> None:
    if (
        message.from_user is None
        or message.bot is None
        or organization.admin_chat_id is None
    ):
        return

    if message.chat.type == TelegramChatType.PRIVATE:
        await message.answer("❌ Команда не може бути викликана в приватному чаті")
        return

    if message.chat.id == organization.admin_chat_id:
        await message.answer("❌ Команда не може бути викликана в чаті модераторів")
        return

    db = await lazy_db.get()

    await chat_verify(
        db, message, organization, is_bot_added=False, verify_type=verify_type
    )


async def verify_external_handler(
    message: Message,
    lazy_db: LazyDbSession,
    organization: Organization,
) -> None:
    await verify_with_type(message, lazy_db, organization, ChatType.EXTERNAL)


async def verify_internal_handler(
    message: Message,
    lazy_db: LazyDbSession,
    organization: Organization,
) -> None:
    await verify_with_type(message, lazy_db, organization, ChatType.INTERNAL)
