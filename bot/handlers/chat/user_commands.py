import html
from aiogram.enums import ChatType as TelegramChatType
from aiogram.types import Message
from sqlalchemy import select
from sqlalchemy.orm import joinedload, selectinload

from app.core.enums import ChatType
from app.db.models.chat import Chat
from app.db.models.chat_thread import ChatThread
from app.db.models.chat_user import ChatUser
from app.db.models.organization import Organization
from bot.middlewares.db_session import LazyDbSession
from bot.utils.chat_permissions import check_internal_chat
from bot.utils.get_visibility import get_visibility_emoji
from bot.utils.message_splitter import TelegramHTMLSplitter


async def members_handler(
    message: Message,
    organization: Organization,
    lazy_db: LazyDbSession,
) -> None:
    if message.chat.type == TelegramChatType.PRIVATE:
        await message.answer("❌ Ця команда доступна лише в групових чатах")
        return

    db = await lazy_db.get()
    result = await db.execute(
        select(Chat).where(
            Chat.id == message.chat.id, Chat.organization_id == organization.id
        )
    )
    chat = result.scalar_one_or_none()

    if chat is None or not await check_internal_chat(message, chat):
        return

    result_users = await db.execute(
        select(ChatUser)
        .options(joinedload(ChatUser.user))
        .where(ChatUser.chat_id == message.chat.id)
        .order_by(ChatUser.created_at)
    )
    chat_users = result_users.scalars().all()

    if not chat_users:
        await message.answer("❌ У цьому чаті немає учасників")
        return

    splitter = TelegramHTMLSplitter(send_func=message.answer)
    await splitter.add("<b>👥 Учасники чату</b>\n\n")
    await splitter.add("<code>")

    for chat_user in chat_users:
        user = chat_user.user
        full_name = user.first_name
        if user.last_name:
            full_name += f" {user.last_name}"
        username = f", @{user.username}" if user.username else ""
        line = f"{html.escape(full_name)}{username}\n"
        await splitter.add(line)

    await splitter.add("</code>")
    await splitter.flush()


async def groups_handler(
    message: Message,
    organization: Organization,
    lazy_db: LazyDbSession,
) -> None:
    db = await lazy_db.get()

    result = await db.execute(
        select(Chat)
        .where(Chat.organization_id == organization.id, Chat.type == ChatType.INTERNAL)
        .order_by(Chat.title)
    )
    chats = result.scalars().all()

    if not chats:
        await message.answer("❌ У організації немає внутрішніх чатів")
        return

    splitter = TelegramHTMLSplitter(send_func=message.answer)
    await splitter.add("<b>📋 Внутрішні чати</b>\n\n")

    for chat in chats:
        visibility_emoji = get_visibility_emoji(chat.visibility_level)
        line = f"{visibility_emoji} {html.escape(chat.title)}\n"
        await splitter.add(line)

    await splitter.flush()


async def group_members_handler(
    message: Message,
    organization: Organization,
    lazy_db: LazyDbSession,
) -> None:
    db = await lazy_db.get()

    result = await db.execute(
        select(Chat)
        .where(Chat.organization_id == organization.id, Chat.type == ChatType.INTERNAL)
        .options(selectinload(Chat.users).selectinload(ChatUser.user))
        .order_by(Chat.title)
    )
    chats = result.scalars().all()

    if not chats:
        await message.answer("❌ У організації немає внутрішніх чатів")
        return

    splitter = TelegramHTMLSplitter(send_func=message.answer)
    await splitter.add("<b>👥 Чати та їх учасники</b>\n\n")

    for chat in chats:
        visibility_emoji = get_visibility_emoji(chat.visibility_level)
        chat_line = f"{visibility_emoji} <b>{html.escape(chat.title)}</b>\n"
        await splitter.add(chat_line)

        if chat.users:
            users = sorted(
                chat.users,
                key=lambda cu: cu.user.first_name.lower(),
            )

            await splitter.add("<code>")
            for chat_user in users:
                user = chat_user.user
                full_name = user.first_name
                if user.last_name:
                    full_name += f" {user.last_name}"

                username = f", @{user.username}" if user.username else ""
                await splitter.add(f"{html.escape(full_name)}{username}\n")
            await splitter.add("</code>\n")
        else:
            await splitter.add("<i>Немає учасників</i>\n\n")

    await splitter.flush()


async def chat_handler(
    message: Message, organization: Organization, lazy_db: LazyDbSession
) -> None:
    db = await lazy_db.get()

    result = await db.execute(
        select(Chat).where(
            Chat.id == message.chat.id, Chat.organization_id == organization.id
        )
    )
    chat = result.scalar_one_or_none()

    if chat is None or not await check_internal_chat(message, chat):
        return

    text = "<b>💬 Інформація про чат</b>\n\n"
    visibility_emoji = get_visibility_emoji(chat.visibility_level)
    pin_emoji = "📌" if chat.pin_requests else "❌"
    text += f"{visibility_emoji} {pin_emoji} <b>{html.escape(chat.title)}</b>\n"

    if chat.tag_on_requests:
        tags = " ".join([f"@{tag}" for tag in chat.tag_on_requests.split()])
        text += f"<code>{tags}</code>"
    else:
        text += "<i>Без тегів</i>"

    await message.answer(text, parse_mode="HTML")


async def threads_handler(message: Message, lazy_db: LazyDbSession) -> None:
    db = await lazy_db.get()

    result = await db.execute(
        select(ChatThread)
        .where(ChatThread.chat_id == message.chat.id)
        .order_by(ChatThread.title)
    )
    threads = result.scalars().all()

    if not threads:
        await message.answer(
            "❌ У чаті не створені гілки, додати можна командою /set_thread [назва]"
        )
        return

    splitter = TelegramHTMLSplitter(send_func=message.answer)
    await splitter.add("<b>💬 Гілки чату</b>\n\n")

    for thread in threads:
        visibility_emoji = get_visibility_emoji(thread.visibility_level)
        pin_emoji = "📌" if thread.pin_requests else "❌"
        thread_line = (
            f"{visibility_emoji} {pin_emoji} <b>{html.escape(thread.title)}</b>\n"
        )
        await splitter.add(thread_line)

        if thread.tag_on_requests:
            tags = " ".join([f"@{tag}" for tag in thread.tag_on_requests.split()])
            await splitter.add(f"<code>{tags}</code>\n\n")
        else:
            await splitter.add("<i>Без тегів</i>\n\n")

    await splitter.flush()
