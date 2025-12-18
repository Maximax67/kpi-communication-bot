from aiogram.types import Message
from aiogram.enums import ChatType as TelegramChatType
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.enums import ChatType, VisibilityLevel
from app.db.models.chat import Chat
from app.db.models.organization import Organization
from bot.utils.captains import get_captain
from bot.utils.format_user import format_user_info
from bot.utils.set_bot_commands import (
    set_bot_commands_for_external_chat,
    set_bot_commands_for_internal_chat,
)


async def chat_verify(
    db: AsyncSession,
    message: Message,
    organization: Organization,
    is_bot_added: bool = False,
) -> None:
    user = message.from_user
    if user is None or message.bot is None:
        return

    if message.chat.type in (
        TelegramChatType.GROUP,
        TelegramChatType.SUPERGROUP,
        TelegramChatType.CHANNEL,
    ):
        if organization.id == 0:
            await message.answer(
                "❌ Цей бот не призначений для використання в цьому чаті. Будь ласка створіть власну організацію командою /create_organization"
            )
            return

        chat_org_stmt = select(Chat.organization_id, Chat.type).where(
            Chat.id == message.chat.id
        )
        chat_org_result = await db.execute(chat_org_stmt)
        chat_organization = chat_org_result.tuples().one_or_none()
        if chat_organization:
            chat_organization_id, chat_type = chat_organization
            if chat_organization_id != organization.id:
                await message.answer(
                    "❌ Чат не можливо верифікувати, адже він належить до іншої організації",
                    allow_sending_without_reply=True,
                )
            elif not is_bot_added:
                await message.answer(
                    "Чат вже верифікований!",
                    allow_sending_without_reply=True,
                )

            if chat_type == ChatType.INTERNAL:
                await set_bot_commands_for_internal_chat(
                    message.bot,
                    message.chat.id,
                    is_forum=bool(message.chat.is_forum),
                )
            elif chat_type == ChatType.EXTERNAL:
                await set_bot_commands_for_external_chat(message.bot, message.chat.id)

            return

        if organization.admin_chat_id:
            organization_admins = await message.bot.get_chat_administrators(
                organization.admin_chat_id
            )
            is_chat_admin = False
            for admin in organization_admins:
                if admin.user.id == user.id:
                    is_chat_admin = True
                    break

            if is_chat_admin:
                db.add(
                    Chat(
                        id=message.chat.id,
                        organization_id=organization.id,
                        title=message.chat.title,
                        type=ChatType.INTERNAL,
                        visibility_level=VisibilityLevel.INTERNAL,
                    )
                )
                await db.commit()
                await message.answer(
                    f"Чат {message.chat.title} верифіковано як для внутрішньої роботи {organization.title}",
                    allow_sending_without_reply=True,
                )
                await message.bot.send_message(
                    organization.admin_chat_id,
                    f"{format_user_info(user)} верифікував чат {message.chat.title} як для внутрішньої роботи",
                    message_thread_id=organization.admin_chat_thread_id,
                )
                await set_bot_commands_for_internal_chat(
                    message.bot,
                    message.chat.id,
                    is_forum=bool(message.chat.is_forum),
                )
                return

            else:
                captain = await get_captain(db, organization.id, user.id, user.username)
                if captain:
                    if captain.connected_chat_id:
                        if not is_bot_added:
                            if captain.connected_chat_id == message.chat.id:
                                if message.chat.is_forum:
                                    await message.answer(
                                        f"Чат групи {captain.chat_title} вже під'єднано. Якщо бажаєте щоб бот надсилав повідомлення в іншу гілку, пропишіть в ній /migrate",
                                        allow_sending_without_reply=True,
                                    )
                                else:
                                    await message.answer(
                                        f"Чат групи {captain.chat_title} вже під'єднано.",
                                        allow_sending_without_reply=True,
                                    )
                            else:
                                await message.answer(
                                    "Ви вже під'єднали чат своєї групи, якщо бажаєте мігрувати чат сюди, то надішліть команду /migrate",
                                    allow_sending_without_reply=True,
                                )

                        return

                    db.add(
                        Chat(
                            id=message.chat.id,
                            organization_id=organization.id,
                            title=captain.chat_title,
                            captain_connected_thread=message.message_thread_id,
                            type=ChatType.EXTERNAL,
                            visibility_level=VisibilityLevel.INTERNAL,
                        )
                    )
                    captain.connected_chat_id = message.chat.id
                    await db.commit()

                    if organization.is_admins_accept_messages:
                        await message.answer(
                            f"Чат {captain.chat_title} верифіковано старостою. Ви можете зв'язуватись з модераторами {organization.title} надіславши команду /send з реплаєм на бажане повідомлення.",
                            allow_sending_without_reply=True,
                        )
                    else:
                        await message.answer(
                            f"Чат {captain.chat_title} верифіковано старостою",
                            allow_sending_without_reply=True,
                        )

                    await message.bot.send_message(
                        organization.admin_chat_id,
                        f"Староста {captain.chat_title} {format_user_info(user)} під'єднав чат {message.chat.title}",
                        message_thread_id=organization.admin_chat_thread_id,
                    )
                    await set_bot_commands_for_external_chat(
                        message.bot, message.chat.id
                    )
                else:
                    if is_bot_added:
                        await message.answer(
                            f"Це бот {organization.title}. Для верифікації староста або адміністратор організації має підтвердити себе надіславши команду /verify"
                        )
                        return

                    await message.answer(
                        "❌ Ви не є старостою чи адміністратором організації. Якщо це не так зверніться до адміністраторів."
                    )


async def verify_captain_private_chat(
    db: AsyncSession, message: Message, organization: Organization
) -> bool:
    user = message.from_user
    if (
        user is None
        or user.username is None
        or organization.admin_chat_id is None
        or message.bot is None
    ):
        return False

    captain = await get_captain(db, organization.id, username=user.username)
    if captain and captain.connected_user_id is None:
        captain.connected_user_id = user.id
        captain.is_bot_blocked = False

        base_text = f"Вітаємо. Вас успішно ідентифіковано як старосту {captain.chat_title}! Це бот для комунікації з {organization.title}."
        if organization.is_admins_accept_messages:
            await message.answer(
                f"{base_text} У разі потреби звернутись до нас просто напишіть ваше повідомлення.",
                allow_sending_without_reply=True,
            )
            return True

        await db.commit()
        await message.answer(base_text, allow_sending_without_reply=True)
        await message.bot.send_message(
            organization.admin_chat_id,
            f"Староста {captain.chat_title} {format_user_info(user)} активував бота.",
            message_thread_id=organization.admin_chat_thread_id,
        )
        return True

    if captain:
        await message.answer(
            f"Вас ідентифіковано як старосту {captain.chat_title}.",
            allow_sending_without_reply=True,
        )

        if captain.is_bot_blocked:
            captain.is_bot_blocked = False
            await db.commit()
            await message.bot.send_message(
                organization.admin_chat_id,
                f"Староста {captain.chat_title} {format_user_info(user)} розблокував бота.",
                message_thread_id=organization.admin_chat_thread_id,
            )

        return True

    return False
