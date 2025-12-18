import html
from aiogram.types import Message, CallbackQuery
from aiogram.utils.keyboard import InlineKeyboardBuilder
from aiogram.fsm.context import FSMContext
from sqlalchemy import select
from sqlalchemy.orm import joinedload

from app.core.bot_cache import remove_telegram_bot
from app.db.models.organization import Organization
from bot.callback import MainCallback, OrganizationCallback
from bot.middlewares.db_session import LazyDbSession
from bot.middlewares.organization import OrganizationCache
from bot.utils.confirm_action import confirm_action
from bot.utils.edit_callback_message import edit_callback_message
from bot.utils.notify_organization import notify_organization


async def delete_organization_handler(
    message: Message,
    state: FSMContext,
    lazy_db: LazyDbSession,
) -> None:
    await state.clear()

    db = await lazy_db.get()
    result = await db.execute(select(Organization).where(Organization.id != 0))
    organizations = result.scalars().all()

    if not organizations:
        await message.answer("❌ Жодна організація не створена")
        return

    kb = InlineKeyboardBuilder()
    for org in organizations:
        kb.button(
            text=org.title,
            callback_data=OrganizationCallback(action="delete", id=org.id),
        )

    kb.button(
        text="❌ Скасувати",
        callback_data=MainCallback(action="cancel"),
    )

    kb.adjust(1)

    await message.answer(
        "Оберіть організацію для видалення:", reply_markup=kb.as_markup()
    )


async def delete_organization(
    callback: CallbackQuery,
    callback_data: OrganizationCallback,
    lazy_db: LazyDbSession,
) -> None:
    await callback.answer()

    if not isinstance(callback.message, Message):
        return

    db = await lazy_db.get()
    result = await db.execute(
        select(Organization.title).where(Organization.id == callback_data.id)
    )
    title = result.scalar_one_or_none()

    if title is None:
        await edit_callback_message(
            callback, "Організація не знайдена, можливо вона вже видалена"
        )
        return

    confirm_callback = OrganizationCallback(
        action="confirm_delete", id=callback_data.id
    )

    await confirm_action(callback, confirm_callback, f"Підтвердити видалення: {title}?")


async def delete_organization_confirmed(
    callback: CallbackQuery,
    callback_data: OrganizationCallback,
    lazy_db: LazyDbSession,
    organization_cache: OrganizationCache,
) -> None:
    if not isinstance(callback.message, Message):
        return

    db = await lazy_db.get()
    org_id = callback_data.id

    result = await db.execute(
        select(Organization)
        .options(joinedload(Organization.bot))
        .where(Organization.id == org_id)
    )
    organization = result.scalar_one_or_none()

    if organization is None:
        await edit_callback_message(
            callback, "Організація не знайдена, можливо вона вже видалена"
        )
        return

    await db.delete(organization)
    await db.commit()

    if organization.bot:
        bot_id = organization.bot.id
        remove_telegram_bot(bot_id)
        organization_cache.remove(bot_id)

    await callback.answer()
    await edit_callback_message(
        callback, f"Організація {organization.title} успішно видалена"
    )
    await notify_organization(
        organization, "Ваша організація видалена адміністраторами!"
    )


async def approve_delete_organization(
    callback: CallbackQuery,
    callback_data: OrganizationCallback,
    lazy_db: LazyDbSession,
) -> None:
    db = await lazy_db.get()

    result = await db.execute(
        select(Organization)
        .options(joinedload(Organization.bot))
        .where(Organization.id == callback_data.id)
    )
    organization = result.scalar_one_or_none()

    if organization is None:
        await edit_callback_message(
            callback, "Організація не знайдена, можливо вона вже видалена"
        )
        return

    title = organization.title

    await db.delete(organization)
    await db.commit()

    await edit_callback_message(
        callback, f"✅ Організацію {html.escape(title)} успішно видалено"
    )
    await callback.answer()
    await notify_organization(
        organization,
        "Організацію було видалено!",
        delete_webhook=True,
    )


async def reject_delete_organization(
    callback: CallbackQuery,
    callback_data: OrganizationCallback,
    lazy_db: LazyDbSession,
) -> None:
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
        f"❌ Запит на видалення організації {html.escape(organization.title)} відхилено",
    )
    await callback.answer()
    await notify_organization(organization, "Видалення організації відхилено!")
