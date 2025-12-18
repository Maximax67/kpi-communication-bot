import html
from aiogram.types import Message, CallbackQuery
from aiogram.fsm.context import FSMContext
from aiogram.utils.keyboard import InlineKeyboardBuilder
from sqlalchemy import select

from app.core.settings import settings
from app.core.logger import logger
from app.db.models.organization import Organization
from bot.callback import MainCallback, OrganizationCallback
from bot.middlewares.db_session import LazyDbSession
from bot.root_bot import ROOT_BOT
from bot.states import CreateOrganizationStates
from bot.utils.delete_last_message import delete_last_message
from bot.utils.edit_callback_message import edit_callback_message
from bot.utils.format_user import format_user_info


async def create_organization_handler(
    message: Message,
    state: FSMContext,
    lazy_db: LazyDbSession,
) -> None:
    if not message.from_user:
        return

    await state.clear()

    db = await lazy_db.get()
    result = await db.execute(
        select(Organization.title).where(Organization.owner == message.from_user.id)
    )
    owned_org_title = result.scalar_one_or_none()
    if owned_org_title:
        await message.answer(f"❌ Ви вже маєте створену організацію: {owned_org_title}")
        return

    kb = InlineKeyboardBuilder()
    kb.button(
        text="❌ Скасувати",
        callback_data=MainCallback(action="cancel"),
    )

    sent_message = await message.answer(
        "Введіть назву організації (не більше 32 символів):",
        reply_markup=kb.as_markup(),
    )

    await state.set_state(CreateOrganizationStates.waiting_for_name)
    await state.update_data(last_message_id=sent_message.message_id)


async def process_organization_name(
    message: Message,
    state: FSMContext,
) -> None:
    if not message.text:
        await message.answer("Будь ласка, введіть текст назви організації")
        return

    org_name = message.text.strip()

    if len(org_name) > 32:
        await message.answer("❌ Назва організації занадто довга! Максимум 32 символи.")
        return

    if len(org_name) == 0:
        await message.answer("❌ Назва організації не може бути порожньою!")
        return

    await delete_last_message(message, state)
    await state.update_data(organization_name=org_name)

    kb = InlineKeyboardBuilder()
    kb.button(
        text="❌ Скасувати",
        callback_data=MainCallback(action="cancel"),
    )

    sent_message = await message.answer(
        "Тепер опишіть, хто ви і навіщо вам потрібна організація:",
        reply_markup=kb.as_markup(),
    )

    await state.set_state(CreateOrganizationStates.waiting_for_description)
    await state.update_data(last_message_id=sent_message.message_id)


async def process_organization_description(
    message: Message,
    state: FSMContext,
    lazy_db: LazyDbSession,
) -> None:
    if not message.text or not message.from_user:
        await message.answer("❌ Будь ласка, введіть текстовий опис")
        return

    description = message.text.strip()

    if len(description) == 0:
        await message.answer("❌ Опис не може бути порожнім!")
        return

    if len(description) > 2048:
        await message.answer(
            "❌ Опис занадто довгий, цінуйте час модераторів. Напишіть більш короткий!"
        )
        return

    data = await state.get_data()
    org_name = data.get("organization_name")

    await delete_last_message(message, state)

    if not org_name:
        await message.answer(
            "❌ Помилка: назва організації не знайдена. Почніть спочатку."
        )
        await state.clear()
        return

    db = await lazy_db.get()
    new_org = Organization(
        title=org_name,
        is_verified=False,
        owner=message.from_user.id,
    )

    db.add(new_org)
    await db.commit()
    await db.refresh(new_org)

    user_info = f"User ID: <code>{message.from_user.id}</code>\n{html.escape(format_user_info(message.from_user))}"

    admin_message = (
        f"<b>Нова заявка на створення організації</b>\n\n"
        f"<b>Назва:</b> {html.escape(org_name)}\n"
        f"<b>ID організації:</b> {new_org.id}\n\n"
        f"<b>Відомості про користувача:</b>\n{user_info}\n\n"
        f"<b>Опис:</b>\n{html.escape(description)}"
    )

    kb = InlineKeyboardBuilder()
    kb.button(
        text="✅ Підтвердити",
        callback_data=OrganizationCallback(action="verify", id=new_org.id),
    )
    kb.button(
        text="❌ Відхилити",
        callback_data=OrganizationCallback(action="reject", id=new_org.id),
    )
    kb.adjust(1)

    await ROOT_BOT.send_message(
        settings.ROOT_ADMIN_CHAT_ID,
        admin_message,
        message_thread_id=settings.ROOT_ADMIN_VERIFICATION_THREAD_ID,
        reply_markup=kb.as_markup(),
        parse_mode="HTML",
    )
    await message.answer(
        "✅ Заявку на створення організації відправлено! "
        "Очікуйте на підтвердження адміністратора."
    )
    await state.clear()


async def verify_organization(
    callback: CallbackQuery,
    callback_data: OrganizationCallback,
    lazy_db: LazyDbSession,
) -> None:
    if not callback.from_user or not isinstance(callback.message, Message):
        return

    db = await lazy_db.get()

    result = await db.execute(
        select(Organization).where(Organization.id == callback_data.id)
    )
    organization = result.scalar_one_or_none()

    if organization is None:
        await edit_callback_message(
            callback, "Організація не знайдена, можливо вона вже видалена"
        )
        return

    if organization.is_verified:
        await callback.message.edit_reply_markup()
        return

    organization.is_verified = True

    await db.commit()

    await edit_callback_message(
        callback,
        f"{callback.message.text}\n\n✅ Підтверджено: {format_user_info(callback.from_user)}",
        parse_mode="HTML",
    )

    await callback.answer()

    try:
        await ROOT_BOT.send_message(
            organization.owner,
            f"Організація підтверджена: {html.escape(organization.title)}. Тепер створіть свого бота командою: /set_bot [token]",
        )
    except Exception as e:
        logger.error(e)


async def reject_organization(
    callback: CallbackQuery,
    callback_data: OrganizationCallback,
    lazy_db: LazyDbSession,
) -> None:
    if not callback.from_user or not isinstance(callback.message, Message):
        return

    db = await lazy_db.get()

    result = await db.execute(
        select(Organization).where(Organization.id == callback_data.id)
    )
    organization = result.scalar_one_or_none()

    if organization is None:
        await edit_callback_message(
            callback, "Організація не знайдена, можливо вона вже видалена"
        )
        return

    await db.delete(organization)
    await db.commit()

    text = f"{callback.message.text}\n\n❌ Відхилено: {format_user_info(callback.from_user)}"
    await edit_callback_message(callback, text, parse_mode="HTML")

    try:
        await ROOT_BOT.send_message(
            organization.owner, f"Створення організації відхилено: {organization.title}"
        )
    except Exception as e:
        logger.error(e)
