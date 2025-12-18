import html
from aiogram.types import Message, CallbackQuery
from aiogram.utils.keyboard import InlineKeyboardBuilder
from sqlalchemy import select

from app.db.models.chat import Chat
from app.db.models.organization import Organization
from bot.callback import ChatCallback, MainCallback
from bot.middlewares.db_session import LazyDbSession
from bot.utils.chat_permissions import check_org_admin_chat
from bot.utils.confirm_action import confirm_action
from bot.utils.edit_callback_message import edit_callback_message


async def delete_seleted_chat_handler(
    message: Message,
    organization: Organization,
    lazy_db: LazyDbSession,
) -> None:
    if not await check_org_admin_chat(message, organization):
        return

    db = await lazy_db.get()
    result = await db.execute(
        select(Chat).where(Chat.organization_id == organization.id)
    )
    chats = result.scalars().all()

    if not chats:
        await message.answer("❌ У організації немає чатів")
        return

    kb = InlineKeyboardBuilder()
    for chat in chats:
        type_emoji = "🏢" if chat.type.value == "internal" else "🌐"
        kb.button(
            text=f"{type_emoji} {chat.title}",
            callback_data=ChatCallback(action="select_delete", chat_id=chat.id),
        )

    kb.button(text="❌ Скасувати", callback_data=MainCallback(action="cancel"))
    kb.adjust(1)

    await message.answer(
        "🗑 <b>Оберіть чат для видалення:</b>",
        reply_markup=kb.as_markup(),
        parse_mode="HTML",
    )


async def select_chat_delete_handler(
    callback: CallbackQuery,
    callback_data: ChatCallback,
    organization: Organization,
    lazy_db: LazyDbSession,
) -> None:
    db = await lazy_db.get()
    result = await db.execute(
        select(Chat).where(
            Chat.id == callback_data.chat_id, Chat.organization_id == organization.id
        )
    )
    chat = result.scalar_one_or_none()

    if chat is None:
        await callback.answer("❌ Чат не знайдено!")
        return

    confirm_callback = ChatCallback(action="confirm_delete_admin", chat_id=chat.id)

    await confirm_action(
        callback,
        confirm_callback,
        f"⚠️ Підтвердити видалення чату {html.escape(chat.title)}?\n\nЦя дія незворотна!",
    )
    await callback.answer()


async def confirm_selected_chat_delete_handler(
    callback: CallbackQuery,
    callback_data: ChatCallback,
    organization: Organization,
    lazy_db: LazyDbSession,
) -> None:
    if not callback.message:
        return

    db = await lazy_db.get()
    result = await db.execute(
        select(Chat).where(
            Chat.id == callback_data.chat_id, Chat.organization_id == organization.id
        )
    )
    chat = result.scalar_one_or_none()

    if chat is None:
        await edit_callback_message(callback, "❌ Чат не знайдено або вже видалено")
        return

    chat_title = chat.title
    await db.delete(chat)
    await db.commit()

    await edit_callback_message(
        callback,
        f"✅ Чат {html.escape(chat_title)} успішно видалено з бази даних",
        parse_mode="HTML",
    )
    await callback.answer()

    if callback.message.bot:
        await callback.message.bot.send_message(
            chat.id, "Чат видалено адміністраторами організації!"
        )
