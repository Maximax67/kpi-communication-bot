import html
from aiogram.types import Message, CallbackQuery
from aiogram.utils.keyboard import InlineKeyboardBuilder

from app.core.settings import settings
from app.db.models.organization import Organization
from bot.callback import MainCallback, OrganizationCallback
from bot.middlewares.db_session import LazyDbSession
from bot.middlewares.organization import OrganizationCache
from bot.root_bot import ROOT_BOT
from bot.utils.confirm_action import confirm_action
from bot.utils.edit_callback_message import edit_callback_message
from bot.utils.format_user import format_user_info


async def settings_handler(
    message: Message,
    organization: Organization,
) -> None:
    if not message.from_user:
        return

    if message.chat.id != organization.admin_chat_id:
        await message.answer(
            "❌ Команда доступна для виконання лише з чату адміністраторів організації"
        )
        return

    await show_settings(message, organization)


async def show_settings(
    msg_or_callback: Message | CallbackQuery,
    organization: Organization,
) -> None:
    privacy_status = "🔒 Приватна" if organization.is_private else "🌐 Публічна"
    messages_status = (
        "✅ Увімкнено" if organization.is_admins_accept_messages else "❌ Вимкнено"
    )
    daily_notifications_status = (
        "✅ Увімкнено" if organization.daily_pending_notifications else "❌ Вимкнено"
    )

    text = (
        f"<b>⚙️ Налаштування організації</b>\n\n"
        f"<b>Назва:</b> {html.escape(organization.title)}\n"
        f"<b>Приватність:</b> {privacy_status}\n"
        f"<b>Прийом повідомлень:</b> {messages_status}\n"
        f"<b>Щоденні нагадування про запити:</b> {daily_notifications_status}\n"
    )

    kb = InlineKeyboardBuilder()

    if organization.is_private:
        kb.button(
            text="🌐 Зробити публічною",
            callback_data=OrganizationCallback(
                action="toggle_privacy", id=organization.id
            ),
        )
    else:
        kb.button(
            text="🔒 Зробити приватною",
            callback_data=OrganizationCallback(
                action="toggle_privacy", id=organization.id
            ),
        )

    if organization.is_admins_accept_messages:
        kb.button(
            text="❌ Вимкнути прийом повідомлень",
            callback_data=OrganizationCallback(
                action="toggle_messages", id=organization.id
            ),
        )
    else:
        kb.button(
            text="✅ Увімкнути прийом повідомлень",
            callback_data=OrganizationCallback(
                action="toggle_messages", id=organization.id
            ),
        )

    if organization.daily_pending_notifications:
        kb.button(
            text="❌ Вимкнути щоденні нагадування",
            callback_data=OrganizationCallback(
                action="toggle_daily_notifications", id=organization.id
            ),
        )
    else:
        kb.button(
            text="✅ Увімкнути щоденні нагадування",
            callback_data=OrganizationCallback(
                action="toggle_daily_notifications", id=organization.id
            ),
        )

    if organization.id != 0:
        kb.button(
            text="🗑 Видалити організацію",
            callback_data=OrganizationCallback(
                action="request_delete", id=organization.id
            ),
        )

    kb.button(
        text="❌ Закрити",
        callback_data=MainCallback(action="close"),
    )
    kb.adjust(1)
    reply_markup = kb.as_markup()

    if isinstance(msg_or_callback, Message):
        await msg_or_callback.answer(text, reply_markup=reply_markup, parse_mode="HTML")
    else:
        await edit_callback_message(
            msg_or_callback, text, reply_markup, parse_mode="HTML"
        )


async def toggle_privacy_handler(
    callback: CallbackQuery,
    callback_data: OrganizationCallback,
    organization: Organization,
    organization_cache: OrganizationCache,
    lazy_db: LazyDbSession,
) -> None:
    if callback_data.id != organization.id:
        await callback.answer("❌ Кнопка призначена для іншої організації!")
        return

    db = await lazy_db.get()
    organization.is_private = not organization.is_private
    await db.merge(organization)
    await db.commit()

    organization_cache.update(organization)

    await show_settings(callback, organization)
    await callback.answer()


async def toggle_messages_handler(
    callback: CallbackQuery,
    callback_data: OrganizationCallback,
    organization: Organization,
    organization_cache: OrganizationCache,
    lazy_db: LazyDbSession,
) -> None:
    if callback_data.id != organization.id:
        await callback.answer("❌ Кнопка призначена для іншої організації!")
        return

    db = await lazy_db.get()
    organization.is_admins_accept_messages = not organization.is_admins_accept_messages
    await db.merge(organization)
    await db.commit()

    organization_cache.update(organization)

    await show_settings(callback, organization)
    await callback.answer()


async def toggle_daily_notifications_handler(
    callback: CallbackQuery,
    callback_data: OrganizationCallback,
    organization: Organization,
    organization_cache: OrganizationCache,
    lazy_db: LazyDbSession,
) -> None:
    if callback_data.id != organization.id:
        await callback.answer("❌ Кнопка призначена для іншої організації!")
        return

    db = await lazy_db.get()
    organization.daily_pending_notifications = (
        not organization.daily_pending_notifications
    )
    await db.merge(organization)
    await db.commit()

    organization_cache.update(organization)

    await show_settings(callback, organization)
    await callback.answer()


async def request_delete_handler(
    callback: CallbackQuery,
    callback_data: OrganizationCallback,
    organization: Organization,
) -> None:
    if callback_data.id != organization.id:
        await callback.answer("❌ Кнопка призначена для іншої організації!")
        return

    if organization.id == 0:
        await callback.answer("❌ Не можливо видалити root організацію")
        return

    await confirm_action(
        callback,
        callback=OrganizationCallback(action="confirm_delete", id=organization.id),
        text="⚠️ Ви впевнені, що хочете видалити організацію? Ця дія незворотна!",
    )
    await callback.answer()


async def confirm_delete_handler(
    callback: CallbackQuery,
    callback_data: OrganizationCallback,
    organization: Organization,
) -> None:
    if callback_data.id != organization.id:
        await callback.answer("❌ Кнопка призначена для іншої організації!")
        return

    if not callback.message or not callback.from_user:
        return

    admin_message = (
        f"<b>Запит на видалення організації</b>\n\n"
        f"<b>ID організації:</b> {organization.id}\n"
        f"<b>Назва:</b> {html.escape(organization.title)}\n"
        f"<b>Від:</b> {html.escape(format_user_info(callback.from_user))}"
    )

    kb = InlineKeyboardBuilder()
    kb.button(
        text="✅ Підтвердити видалення",
        callback_data=OrganizationCallback(action="approve_delete", id=organization.id),
    )
    kb.button(
        text="❌ Відхилити",
        callback_data=OrganizationCallback(action="reject_delete", id=organization.id),
    )
    kb.adjust(1)

    await ROOT_BOT.send_message(
        settings.ROOT_ADMIN_CHAT_ID,
        admin_message,
        message_thread_id=settings.ROOT_ADMIN_VERIFICATION_THREAD_ID,
        reply_markup=kb.as_markup(),
        parse_mode="HTML",
    )

    await edit_callback_message(callback, "✅ Запит на видалення відправлено")
    await callback.answer()
