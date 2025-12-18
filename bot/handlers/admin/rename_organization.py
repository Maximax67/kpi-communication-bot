import html
from aiogram.types import Message, CallbackQuery
from aiogram.utils.keyboard import InlineKeyboardBuilder
from sqlalchemy import select
from sqlalchemy.orm import joinedload

from app.core.settings import settings
from app.db.models.organization import Organization
from bot.middlewares.organization import OrganizationCache
from bot.root_bot import ROOT_BOT
from bot.callback import OrganizationCallback
from bot.middlewares.db_session import LazyDbSession
from bot.utils.edit_callback_message import edit_callback_message
from bot.utils.format_user import format_user_info
from bot.utils.notify_organization import notify_organization


async def rename_organization_handler(
    message: Message,
    organization: Organization,
    lazy_db: LazyDbSession,
) -> None:
    if not message.text or not message.from_user:
        return

    if message.chat.id != organization.admin_chat_id:
        await message.answer(
            "❌ Команда доступна для виконання лише з чату адміністраторів організації"
        )
        return

    command_parts = message.text.split(maxsplit=1)

    if len(command_parts) < 2:
        await message.answer("❌ Використання: /rename_organization нова_назва")
        return

    new_title = command_parts[1].strip()

    if len(new_title) == 0:
        await message.answer("❌ Назва організації не може бути порожньою!")
        return

    if len(new_title) > 32:
        await message.answer("❌ Назва організації занадто довга! Максимум 32 символи.")
        return

    if new_title == organization.title:
        await message.answer("❌ Нова назва ідентична з попередньою.")
        return

    if organization.id == 0:
        old_title = organization.title
        organization.title = new_title

        db = await lazy_db.get()
        await db.merge(organization)
        await db.commit()

        await message.answer(
            f"✅ Організацію перейменовано\n"
            f"Минула назва: {html.escape(old_title)}\n"
            f"Нова: {html.escape(new_title)}",
        )
        return

    admin_message = (
        f"<b>Запит на перейменування організації</b>\n\n"
        f"<b>ID організації:</b> {organization.id}\n"
        f"<b>Поточна назва:</b> {html.escape(organization.title)}\n"
        f"<b>Нова назва:</b> {html.escape(new_title)}\n"
        f"<b>Від:</b> {message.from_user.id}"
    )

    if message.from_user.username:
        admin_message += f" (@{message.from_user.username})"

    kb = InlineKeyboardBuilder()
    kb.button(
        text="✅ Підтвердити",
        callback_data=OrganizationCallback(action="approve_rename", id=organization.id),
    )
    kb.button(
        text="❌ Відхилити",
        callback_data=OrganizationCallback(action="reject_rename", id=organization.id),
    )
    kb.adjust(1)

    try:
        await ROOT_BOT.send_message(
            settings.ROOT_ADMIN_CHAT_ID,
            admin_message,
            message_thread_id=settings.ROOT_ADMIN_VERIFICATION_THREAD_ID,
            reply_markup=kb.as_markup(),
            parse_mode="HTML",
        )
        await message.answer("✅ Запит на перейменування відправлено")
    except Exception as e:
        await message.answer(f"❌ Помилка відправки запиту: {e}")


async def approve_rename_organization(
    callback: CallbackQuery,
    callback_data: OrganizationCallback,
    organization_cache: OrganizationCache,
    lazy_db: LazyDbSession,
) -> None:
    if not isinstance(callback.message, Message) or not callback.message.text:
        await callback.answer("❌ Помилка: не вдалося отримати повідомлення")
        return

    message_text = callback.message.text
    try:
        new_title_start = message_text.find("Нова назва:") + len("Нова назва:")
        new_title_end = message_text.find("\n", new_title_start)
        if new_title_end == -1:
            new_title_end = len(message_text)

        new_title = message_text[new_title_start:new_title_end].strip()
    except Exception:
        await callback.answer("❌ Помилка: не вдалося отримати нову назву")
        return

    db = await lazy_db.get()

    result = await db.execute(
        select(Organization)
        .options(joinedload(Organization.bot))
        .where(Organization.id == callback_data.id)
    )
    organization = result.scalar_one_or_none()

    if organization is None:
        await edit_callback_message(callback, "❌ Організація не знайдена")
        return

    organization.title = new_title
    await db.commit()

    organization_cache.update(organization)

    await edit_callback_message(
        callback,
        f"{callback.message.text}\n\n✅ Організацію перейменовано: {format_user_info(callback.from_user)}",
        parse_mode="HTML",
    )
    await callback.answer()
    await notify_organization(
        organization, f"✅ Запит на перейменування схвалено. Нова назва: {new_title}"
    )


async def reject_rename_organization(
    callback: CallbackQuery,
    callback_data: OrganizationCallback,
    lazy_db: LazyDbSession,
) -> None:
    if not isinstance(callback.message, Message):
        return

    db = await lazy_db.get()

    result = await db.execute(
        select(Organization)
        .options(joinedload(Organization.bot))
        .where(Organization.id == callback_data.id)
    )
    organization = result.scalar_one_or_none()

    if organization is None:
        await edit_callback_message(callback, "Організація не знайдена")
        return

    await edit_callback_message(
        callback,
        f"{callback.message.text}\n\n❌ Відхилено: {format_user_info(callback.from_user)}",
        parse_mode="HTML",
    )

    await notify_organization(organization, "❌ Запит на перейменування відхилено")
    await callback.answer()
