import html
from aiogram import Bot
from aiogram.enums import ChatType as TelegramChatType
from aiogram.types import Message, CallbackQuery
from aiogram.utils.keyboard import InlineKeyboardBuilder
from sqlalchemy import select
from sqlalchemy.orm import joinedload

from app.core.enums import VisibilityLevel
from app.db.models.chat import Chat
from app.db.models.chat_thread import ChatThread
from app.db.models.organization import Organization
from bot.callback import ChatCallback, ThreadCallback, MainCallback
from bot.middlewares.db_session import LazyDbSession
from bot.utils.chat_permissions import get_chat_if_admin
from bot.utils.edit_callback_message import edit_callback_message
from bot.utils.format_user import format_user_info
from bot.utils.get_visibility import get_visibility_label
from bot.utils.notify_organization import notify_organization
from bot.utils.set_bot_commands import set_bot_commands_for_internal_chat
from bot.utils.usernames import extract_usernames, validate_usernames


async def rename_chat_handler(
    message: Message,
    organization: Organization,
    lazy_db: LazyDbSession,
    bot: Bot,
) -> None:
    if not message.text or not message.from_user:
        return

    if message.chat.type == TelegramChatType.PRIVATE:
        await message.answer("❌ Ця команда доступна лише в групових чатах")
        return

    db = await lazy_db.get()
    chat = await get_chat_if_admin(db, message, bot, organization.id)
    if chat is None:
        return

    command_parts = message.text.split(maxsplit=1)
    if len(command_parts) < 2:
        await message.answer("❌ Використання: /rename_chat Нова назва")
        return

    new_title = command_parts[1].strip()

    if len(new_title) == 0:
        await message.answer("❌ Назва чату не може бути порожньою!")
        return

    if len(new_title) > 32:
        await message.answer("❌ Назва чату занадто довга! Максимум 32 символи.")
        return

    if new_title == chat.title:
        await message.answer("❌ Назва чату ідентична з поточною.")
        return

    old_title = chat.title
    chat.title = new_title
    await db.commit()

    await message.answer(
        f"✅ Чат перейменовано\n"
        f"Минула назва: {html.escape(old_title)}\n"
        f"Нова назва: {html.escape(new_title)}",
        parse_mode="HTML",
    )

    notification = (
        f"<b>🔄 Чат перейменовано</b>\n\n"
        f"<b>Чат ID:</b> <code>{chat.id}</code>\n"
        f"<b>Стара назва:</b> {html.escape(old_title)}\n"
        f"<b>Нова назва:</b> {html.escape(new_title)}\n"
        f"<b>Хто:</b> {html.escape(format_user_info(message.from_user))}"
    )
    await notify_organization(organization, notification, parse_mode="HTML")


async def chat_visibility_handler(
    message: Message,
    organization: Organization,
    lazy_db: LazyDbSession,
    bot: Bot,
) -> None:
    if message.chat.type == TelegramChatType.PRIVATE:
        await message.answer("❌ Ця команда доступна лише в групових чатах")
        return

    db = await lazy_db.get()
    chat = await get_chat_if_admin(db, message, bot, organization.id)
    if chat is None:
        return

    await show_visibility_settings(message, chat)


async def show_visibility_settings(
    msg_or_callback: Message | CallbackQuery,
    chat: Chat,
) -> None:
    text = (
        f"<b>👁 Видимість чату</b>\n\n"
        f"<b>Поточний рівень:</b> {get_visibility_label(chat.visibility_level)}"
    )

    kb = InlineKeyboardBuilder()
    for level in VisibilityLevel:
        if level != chat.visibility_level:
            kb.button(
                text=get_visibility_label(level),
                callback_data=ChatCallback(
                    action=f"visibility_{level.value}", chat_id=chat.id
                ),
            )

    kb.button(text="❌ Закрити", callback_data=MainCallback(action="close"))
    kb.adjust(1)

    if isinstance(msg_or_callback, Message):
        await msg_or_callback.answer(
            text, reply_markup=kb.as_markup(), parse_mode="HTML"
        )
    else:
        await edit_callback_message(
            msg_or_callback, text, kb.as_markup(), parse_mode="HTML"
        )


async def change_chat_visibility_handler(
    callback: CallbackQuery,
    callback_data: ChatCallback,
    organization: Organization,
    lazy_db: LazyDbSession,
    bot: Bot,
) -> None:
    if not callback.from_user or not isinstance(callback.message, Message):
        return

    db = await lazy_db.get()
    chat = await get_chat_if_admin(
        db, callback.message, bot, organization.id, callback.from_user.id
    )
    if chat is None:
        return

    visibility_str = callback_data.action.replace("visibility_", "")
    new_visibility = VisibilityLevel(visibility_str)

    old_visibility = chat.visibility_level
    chat.visibility_level = new_visibility
    await db.commit()

    await show_visibility_settings(callback, chat)
    await callback.answer("✅ Видимість змінено")

    notification = (
        f"<b>👁 Змінено видимість чату</b>\n\n"
        f"<b>Чат:</b> {html.escape(chat.title)}\n"
        f"<b>Було:</b> {get_visibility_label(old_visibility)}\n"
        f"<b>Стало:</b> {get_visibility_label(new_visibility)}\n"
        f"<b>Хто:</b> {html.escape(format_user_info(callback.from_user))}"
    )
    await notify_organization(organization, notification, parse_mode="HTML")


async def set_thread_handler(
    message: Message,
    organization: Organization,
    lazy_db: LazyDbSession,
    bot: Bot,
) -> None:
    if not message.text or not message.from_user:
        return

    if message.chat.type == TelegramChatType.PRIVATE:
        await message.answer("❌ Ця команда доступна лише в групових чатах")
        return

    db = await lazy_db.get()
    chat = await get_chat_if_admin(db, message, bot, organization.id)
    if chat is None:
        return

    chat_info = await bot.get_chat(message.chat.id)
    if not chat_info.is_forum:
        await message.answer("❌ Команда доступна лише в чатах з гілками")
        return

    command_parts = message.text.split(maxsplit=1)
    if len(command_parts) < 2:
        await message.answer("❌ Використання: /set_thread Назва гілки")
        return

    thread_title = command_parts[1].strip()

    if len(thread_title) == 0:
        await message.answer("❌ Назва гілки не може бути порожньою!")
        return

    if len(thread_title) > 32:
        await message.answer("❌ Назва гілки занадто довга! Максимум 32 символи.")
        return

    thread_id = message.message_thread_id or 1
    result = await db.execute(
        select(ChatThread).where(
            ChatThread.chat_id == chat.id, ChatThread.id == thread_id
        )
    )
    existing_thread = result.scalar_one_or_none()

    if existing_thread:
        await message.answer("❌ Ця гілка вже додана до бази даних!")
        return

    thread = ChatThread(
        id=thread_id,
        chat_id=chat.id,
        title=thread_title,
        visibility_level=VisibilityLevel.INTERNAL,
    )
    db.add(thread)
    await db.commit()

    await message.answer(
        f"✅ Гілку '{html.escape(thread_title)}' додано", parse_mode="HTML"
    )

    notification = (
        f"<b>➕ Додано нову гілку</b>\n\n"
        f"<b>Чат:</b> {html.escape(chat.title)}\n"
        f"<b>Гілка:</b> {html.escape(thread_title)}\n"
        f"<b>Thread ID:</b> <code>{thread_id}</code>\n"
        f"<b>Хто:</b> {html.escape(format_user_info(message.from_user))}"
    )
    await notify_organization(organization, notification, parse_mode="HTML")
    await set_bot_commands_for_internal_chat(bot, message.chat.id, is_forum=True)


async def delete_thread_handler(
    message: Message,
    organization: Organization,
    lazy_db: LazyDbSession,
    bot: Bot,
) -> None:
    if not message.from_user:
        return

    if message.chat.type == TelegramChatType.PRIVATE:
        await message.answer("❌ Ця команда доступна лише в групових чатах")
        return

    db = await lazy_db.get()
    chat = await get_chat_if_admin(db, message, bot, organization.id)
    if chat is None:
        return

    thread_id = message.message_thread_id or 1
    result = await db.execute(
        select(ChatThread).where(
            ChatThread.chat_id == chat.id, ChatThread.id == thread_id
        )
    )
    thread = result.scalar_one_or_none()

    if not thread:
        await message.answer("❌ Гілка не знайдена в базі даних!")
        return

    thread_title = thread.title
    await db.delete(thread)
    await db.commit()

    await message.answer(
        f"✅ Гілку '{html.escape(thread_title)}' видалено з бази даних",
        parse_mode="HTML",
    )

    notification = (
        f"<b>➖ Видалено гілку</b>\n\n"
        f"<b>Чат:</b> {html.escape(chat.title)}\n"
        f"<b>Гілка:</b> {html.escape(thread_title)}\n"
        f"<b>Хто:</b> {html.escape(format_user_info(message.from_user))}"
    )
    await notify_organization(organization, notification, parse_mode="HTML")


async def rename_thread_handler(
    message: Message,
    organization: Organization,
    lazy_db: LazyDbSession,
    bot: Bot,
) -> None:
    if not message.text or not message.from_user:
        return

    if message.chat.type == TelegramChatType.PRIVATE:
        await message.answer("❌ Ця команда доступна лише в групових чатах")
        return

    db = await lazy_db.get()
    chat = await get_chat_if_admin(db, message, bot, organization.id)
    if chat is None:
        return

    command_parts = message.text.split(maxsplit=1)
    if len(command_parts) < 2:
        await message.answer("❌ Використання: /rename_thread Нова назва")
        return

    new_title = command_parts[1].strip()

    if len(new_title) == 0:
        await message.answer("❌ Назва гілки не може бути порожньою!")
        return

    if len(new_title) > 32:
        await message.answer("❌ Назва гілки занадто довга! Максимум 32 символи.")
        return

    thread_id = message.message_thread_id or 1
    result = await db.execute(
        select(ChatThread).where(
            ChatThread.chat_id == chat.id, ChatThread.id == thread_id
        )
    )
    thread = result.scalar_one_or_none()

    if not thread:
        await message.answer("❌ Гілка не знайдена в базі даних!")
        return

    if new_title == thread.title:
        await message.answer("❌ Гілка вже має таку назву.")
        return

    old_title = thread.title
    thread.title = new_title
    await db.commit()

    await message.answer(
        f"✅ Гілку перейменовано\n"
        f"Було: {html.escape(old_title)}\n"
        f"Стало: {html.escape(new_title)}",
        parse_mode="HTML",
    )

    notification = (
        f"<b>🔄 Перейменовано гілку</b>\n\n"
        f"<b>Чат:</b> {html.escape(chat.title)}\n"
        f"<b>Було:</b> {html.escape(old_title)}\n"
        f"<b>Стало:</b> {html.escape(new_title)}\n"
        f"<b>Хто:</b> {html.escape(format_user_info(message.from_user))}"
    )
    await notify_organization(organization, notification, parse_mode="HTML")


async def thread_visibility_handler(
    message: Message,
    organization: Organization,
    lazy_db: LazyDbSession,
    bot: Bot,
) -> None:
    if not message.from_user:
        return

    if message.chat.type == TelegramChatType.PRIVATE:
        await message.answer("❌ Ця команда доступна лише в групових чатах")
        return

    db = await lazy_db.get()
    chat = await get_chat_if_admin(db, message, bot, organization.id)
    if chat is None:
        return

    thread_id = message.message_thread_id or 1
    thread_result = await db.execute(
        select(ChatThread).where(
            ChatThread.chat_id == chat.id, ChatThread.id == thread_id
        )
    )
    thread = thread_result.scalar_one_or_none()

    if not thread:
        await message.answer("❌ Гілка не знайдена в базі даних!")
        return

    await show_thread_visibility_settings(message, thread)


async def show_thread_visibility_settings(
    msg_or_callback: Message | CallbackQuery,
    thread: ChatThread,
) -> None:
    text = (
        f"<b>👁 Видимість гілки</b>\n\n"
        f"<b>Поточний рівень:</b> {get_visibility_label(thread.visibility_level)}"
    )

    kb = InlineKeyboardBuilder()
    for level in VisibilityLevel:
        if level != thread.visibility_level:
            kb.button(
                text=get_visibility_label(level),
                callback_data=ThreadCallback(
                    action=f"visibility_{level.value}",
                    chat_id=thread.chat_id,
                    thread_id=thread.id,
                ),
            )

    kb.button(text="❌ Закрити", callback_data=MainCallback(action="close"))
    kb.adjust(1)

    if isinstance(msg_or_callback, Message):
        await msg_or_callback.answer(
            text, reply_markup=kb.as_markup(), parse_mode="HTML"
        )
    else:
        await edit_callback_message(
            msg_or_callback, text, kb.as_markup(), parse_mode="HTML"
        )


async def change_thread_visibility_handler(
    callback: CallbackQuery,
    callback_data: ThreadCallback,
    organization: Organization,
    lazy_db: LazyDbSession,
) -> None:
    if (
        not callback.from_user
        or not callback.bot
        or not isinstance(callback.message, Message)
    ):
        return

    db = await lazy_db.get()

    chat = await get_chat_if_admin(
        db, callback.message, callback.bot, organization.id, callback.from_user.id
    )
    if chat is None:
        return

    result = await db.execute(
        select(ChatThread)
        .options(joinedload(ChatThread.chat))
        .where(
            ChatThread.chat_id == callback_data.chat_id,
            ChatThread.id == callback_data.thread_id,
        )
    )
    thread = result.scalar_one_or_none()

    if not thread:
        await callback.answer("❌ Гілка не знайдена!")
        return

    visibility_str = callback_data.action.replace("visibility_", "")
    new_visibility = VisibilityLevel(visibility_str)

    old_visibility = thread.visibility_level
    thread.visibility_level = new_visibility
    await db.commit()

    await show_thread_visibility_settings(callback, thread)
    await callback.answer("✅ Видимість змінено")

    notification = (
        f"<b>👁 Змінено видимість гілки</b>\n\n"
        f"<b>Чат:</b> {html.escape(thread.chat.title)}\n"
        f"<b>Гілка:</b> {html.escape(thread.title)}\n"
        f"<b>Було:</b> {get_visibility_label(old_visibility)}\n"
        f"<b>Стало:</b> {get_visibility_label(new_visibility)}\n"
        f"<b>Хто:</b> {html.escape(format_user_info(callback.from_user))}"
    )
    await notify_organization(organization, notification, parse_mode="HTML")


async def delete_chat_handler(
    message: Message,
    organization: Organization,
    lazy_db: LazyDbSession,
    bot: Bot,
) -> None:
    if not message.from_user:
        return

    if message.chat.type == TelegramChatType.PRIVATE:
        await message.answer("❌ Ця команда доступна лише в групових чатах")
        return

    db = await lazy_db.get()
    chat = await get_chat_if_admin(db, message, bot, organization.id)
    if chat is None:
        return

    kb = InlineKeyboardBuilder()
    kb.button(
        text="✅ Підтвердити видалення",
        callback_data=ChatCallback(action="confirm_delete_chat", chat_id=chat.id),
    )
    kb.button(text="❌ Скасувати", callback_data=MainCallback(action="close"))
    kb.adjust(1)

    await message.answer(
        f"⚠️ Ви впевнені, що хочете видалити чат {html.escape(chat.title)}?",
        reply_markup=kb.as_markup(),
        parse_mode="HTML",
    )


async def confirm_chat_delete_handler(
    callback: CallbackQuery,
    callback_data: ChatCallback,
    organization: Organization,
    lazy_db: LazyDbSession,
) -> None:
    if (
        not callback.from_user
        or not callback.bot
        or not isinstance(callback.message, Message)
    ):
        return

    if callback.message.chat.id != callback_data.chat_id:
        await callback.answer("❌ Кнопка призначена для іншого чату!")
        return

    db = await lazy_db.get()
    chat = await get_chat_if_admin(
        db, callback.message, callback.bot, organization.id, callback.from_user.id
    )
    if chat is None:
        return

    notification = (
        f"<b>🗑 Чат видалено</b>\n\n"
        f"<b>Чат ID:</b> <code>{chat.id}</code>\n"
        f"<b>Назва:</b> {html.escape(chat.title)}\n"
        f"<b>Хто:</b> {html.escape(format_user_info(callback.from_user))}"
    )

    await notify_organization(organization, notification, parse_mode="HTML")
    await edit_callback_message(callback, "✅ Чат видалено")
    await callback.answer()


async def pin_chat_requests_handler(
    message: Message,
    lazy_db: LazyDbSession,
    organization: Organization,
    bot: Bot,
) -> None:
    if message.chat.type == TelegramChatType.PRIVATE:
        await message.answer("❌ Ця команда доступна лише в групових чатах")
        return

    db = await lazy_db.get()
    chat = await get_chat_if_admin(db, message, bot, organization.id)
    if chat is None:
        return

    if chat.pin_requests:
        await message.answer("❌ Закріплення запитів вже увімкнено для цього чату")
        return

    chat.pin_requests = True
    await db.commit()

    await message.answer("✅ Закріплення запитів увімкнено для чату")


async def disable_pin_chat_requests_handler(
    message: Message,
    lazy_db: LazyDbSession,
    organization: Organization,
    bot: Bot,
) -> None:
    if message.chat.type == TelegramChatType.PRIVATE:
        await message.answer("❌ Ця команда доступна лише в групових чатах")
        return

    db = await lazy_db.get()
    chat = await get_chat_if_admin(db, message, bot, organization.id)
    if chat is None:
        return

    if not chat.pin_requests:
        await message.answer("❌ Закріплення запитів вже вимкнено для цього чату")
        return

    chat.pin_requests = False
    await db.commit()

    await message.answer("✅ Закріплення запитів вимкнено для чату")


async def pin_thread_requests_handler(
    message: Message,
    lazy_db: LazyDbSession,
    organization: Organization,
    bot: Bot,
) -> None:
    if message.chat.type == TelegramChatType.PRIVATE:
        await message.answer("❌ Ця команда доступна лише в групових чатах")
        return

    db = await lazy_db.get()
    chat = await get_chat_if_admin(db, message, bot, organization.id)
    if chat is None:
        return

    chat_info = await bot.get_chat(message.chat.id)
    if not chat_info.is_forum:
        await message.answer("❌ Команда доступна лише в чатах з гілками")
        return

    thread_id = message.message_thread_id or 1
    result = await db.execute(
        select(ChatThread).where(
            ChatThread.chat_id == chat.id, ChatThread.id == thread_id
        )
    )
    thread = result.scalar_one_or_none()

    if not thread:
        await message.answer("❌ Гілка не знайдена в базі даних!")
        return

    if thread.pin_requests:
        await message.answer("❌ Закріплення запитів вже увімкнено для цієї гілки")
        return

    thread.pin_requests = True
    await db.commit()

    await message.answer("✅ Закріплення запитів увімкнено для гілки")


async def disable_pin_thread_requests_handler(
    message: Message,
    lazy_db: LazyDbSession,
    organization: Organization,
    bot: Bot,
) -> None:
    if message.chat.type == TelegramChatType.PRIVATE:
        await message.answer("❌ Ця команда доступна лише в групових чатах")
        return

    db = await lazy_db.get()
    chat = await get_chat_if_admin(db, message, bot, organization.id)
    if chat is None:
        return

    chat_info = await bot.get_chat(message.chat.id)
    if not chat_info.is_forum:
        await message.answer("❌ Команда доступна лише в чатах з гілками")
        return

    thread_id = message.message_thread_id or 1
    result = await db.execute(
        select(ChatThread).where(
            ChatThread.chat_id == chat.id, ChatThread.id == thread_id
        )
    )
    thread = result.scalar_one_or_none()

    if not thread:
        await message.answer("❌ Гілка не знайдена в базі даних!")
        return

    if not thread.pin_requests:
        await message.answer("❌ Закріплення запитів вже вимкнено для цієї гілки")
        return

    thread.pin_requests = False
    await db.commit()

    await message.answer("✅ Закріплення запитів вимкнено для гілки")


async def set_chat_tags_handler(
    message: Message,
    lazy_db: LazyDbSession,
    organization: Organization,
    bot: Bot,
) -> None:
    if not message.text:
        return

    if message.chat.type == TelegramChatType.PRIVATE:
        await message.answer("❌ Ця команда доступна лише в групових чатах")
        return

    db = await lazy_db.get()
    chat = await get_chat_if_admin(db, message, bot, organization.id)
    if chat is None:
        return

    command_parts = message.text.split(maxsplit=1)
    if len(command_parts) < 2:
        await message.answer(
            "❌ Використання: /set_chat_tags @username1 @username2 ...\n"
        )
        return

    tags_text = command_parts[1].strip()

    usernames = extract_usernames(tags_text)
    is_valid, error_msg = validate_usernames(usernames)
    if not is_valid:
        if error_msg:
            await message.answer(error_msg)

        return

    tags_string = " ".join(usernames)
    if chat.tag_on_requests == tags_string:
        await message.answer("❌ Ці теги вже встановлені для чату")
        return

    old_tags = chat.tag_on_requests
    chat.tag_on_requests = tags_string
    await db.commit()

    display_tags = " ".join(f"@{tag}" for tag in usernames)
    response = (
        f"✅ Теги для чату встановлено\n\n<b>Теги:</b> {html.escape(display_tags)}"
    )

    if old_tags:
        old_display = " ".join(f"@{tag}" for tag in old_tags.split())
        response = (
            f"✅ Теги для чату оновлено\n\n"
            f"<b>Було:</b> {html.escape(old_display)}\n"
            f"<b>Стало:</b> {html.escape(display_tags)}"
        )

    await message.answer(response, parse_mode="HTML")


async def delete_chat_tags_handler(
    message: Message,
    lazy_db: LazyDbSession,
    organization: Organization,
    bot: Bot,
) -> None:
    if message.chat.type == TelegramChatType.PRIVATE:
        await message.answer("❌ Ця команда доступна лише в групових чатах")
        return

    db = await lazy_db.get()
    chat = await get_chat_if_admin(db, message, bot, organization.id)
    if chat is None:
        return

    if not chat.tag_on_requests:
        await message.answer("❌ Для цього чату не встановлено тегів")
        return

    old_tags = chat.tag_on_requests
    old_display = " ".join(f"@{tag}" for tag in old_tags.split())

    chat.tag_on_requests = None
    await db.commit()

    await message.answer(
        f"✅ Теги видалено з чату\n\n<b>Видалені теги:</b> {html.escape(old_display)}",
        parse_mode="HTML",
    )


async def set_thread_tags_handler(
    message: Message,
    lazy_db: LazyDbSession,
    organization: Organization,
    bot: Bot,
) -> None:
    if not message.text:
        return

    if message.chat.type == TelegramChatType.PRIVATE:
        await message.answer("❌ Ця команда доступна лише в групових чатах")
        return

    db = await lazy_db.get()
    chat = await get_chat_if_admin(db, message, bot, organization.id)
    if chat is None:
        return

    chat_info = await bot.get_chat(message.chat.id)
    if not chat_info.is_forum:
        await message.answer("❌ Команда доступна лише в чатах з гілками")
        return

    thread_id = message.message_thread_id or 1
    result = await db.execute(
        select(ChatThread).where(
            ChatThread.chat_id == chat.id, ChatThread.id == thread_id
        )
    )
    thread = result.scalar_one_or_none()

    if not thread:
        await message.answer("❌ Гілка не знайдена в базі даних!")
        return

    command_parts = message.text.split(maxsplit=1)
    if len(command_parts) < 2:
        await message.answer(
            "❌ Використання: /set_thread_tags @username1 @username2 ...\n"
        )
        return

    tags_text = command_parts[1].strip()
    usernames = extract_usernames(tags_text)
    is_valid, error_msg = validate_usernames(usernames)
    if not is_valid:
        if error_msg:
            await message.answer(error_msg)

        return

    tags_string = " ".join(usernames)

    if thread.tag_on_requests == tags_string:
        await message.answer("❌ Ці теги вже встановлені для гілки")
        return

    old_tags = thread.tag_on_requests
    thread.tag_on_requests = tags_string
    await db.commit()

    display_tags = " ".join(f"@{tag}" for tag in usernames)
    response = (
        f"✅ Теги для гілки встановлено\n\n<b>Теги:</b> {html.escape(display_tags)}"
    )

    if old_tags:
        old_display = " ".join(f"@{tag}" for tag in old_tags.split())
        response = (
            f"✅ Теги для гілки оновлено\n\n"
            f"<b>Було:</b> {html.escape(old_display)}\n"
            f"<b>Стало:</b> {html.escape(display_tags)}"
        )

    await message.answer(response, parse_mode="HTML")


async def delete_thread_tags_handler(
    message: Message,
    lazy_db: LazyDbSession,
    organization: Organization,
    bot: Bot,
) -> None:
    if message.chat.type == TelegramChatType.PRIVATE:
        await message.answer("❌ Ця команда доступна лише в групових чатах")
        return

    db = await lazy_db.get()
    chat = await get_chat_if_admin(db, message, bot, organization.id)
    if chat is None:
        return

    chat_info = await bot.get_chat(message.chat.id)
    if not chat_info.is_forum:
        await message.answer("❌ Команда доступна лише в чатах з гілками")
        return

    thread_id = message.message_thread_id or 1
    result = await db.execute(
        select(ChatThread).where(
            ChatThread.chat_id == chat.id, ChatThread.id == thread_id
        )
    )
    thread = result.scalar_one_or_none()

    if not thread:
        await message.answer("❌ Гілка не знайдена в базі даних!")
        return

    if not thread.tag_on_requests:
        await message.answer("❌ Для цієї гілки не встановлено тегів")
        return

    old_tags = thread.tag_on_requests
    old_display = " ".join(f"@{tag}" for tag in old_tags.split())

    thread.tag_on_requests = None
    await db.commit()

    await message.answer(
        f"✅ Теги видалено з гілки\n\n<b>Видалені теги:</b> {html.escape(old_display)}",
        parse_mode="HTML",
    )
