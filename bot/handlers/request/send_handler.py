import html
from aiogram import Bot
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup
from aiogram.enums import ChatType as TelegramChatType
from aiogram.utils.keyboard import InlineKeyboardBuilder
from sqlalchemy import exists, select
from sqlalchemy.orm import joinedload, selectinload
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logger import logger
from app.core.enums import ChatType, MessageType, VisibilityLevel
from app.db.models.chat import Chat
from app.db.models.chat_thread import ChatThread
from app.db.models.organization import Organization
from bot.callback import MainCallback, MessageCallback
from bot.handlers.request.message_handler import put_reaction, send_message
from bot.middlewares.ban_middleware import BanController
from bot.middlewares.db_session import LazyDbSession
from bot.utils.edit_callback_message import edit_callback_message
from bot.utils.get_bot import get_organization_bot


async def change_callback_or_message(
    tg_object: Message | CallbackQuery,
    text: str,
    reply_markup: InlineKeyboardMarkup | None = None,
) -> None:
    if isinstance(tg_object, CallbackQuery):
        await edit_callback_message(tg_object, text, reply_markup)
        return

    await tg_object.answer(
        text,
        reply_markup=reply_markup,
        reply_to_message_id=(
            tg_object.reply_to_message.message_id
            if tg_object.reply_to_message
            else None
        ),
    )


async def show_available_root_admin_org_chats(
    db: AsyncSession, tg_object: Message | CallbackQuery, type: MessageType
) -> None:
    orgs_admin_stmt = select(Organization).where(
        Organization.id != 0,
        Organization.is_verified.is_(True),
    )
    orgs_admin_stmt_result = await db.execute(orgs_admin_stmt)
    orgs_admin = orgs_admin_stmt_result.scalars().all()

    if not orgs_admin:
        await change_callback_or_message(
            tg_object, "❌ Верифіковані організації відсутні"
        )
        return

    kb = InlineKeyboardBuilder()
    for org in orgs_admin:
        kb.button(
            text=org.title,
            callback_data=MessageCallback(
                action="select_org",
                data=str(org.id),
                type=type,
            ),
        )

    kb.button(text="❌ Скасувати", callback_data=MainCallback(action="cancel"))
    kb.adjust(1)

    await change_callback_or_message(
        tg_object, "Оберіть організацію:", reply_markup=kb.as_markup()
    )


async def show_available_org_chats(
    db: AsyncSession,
    tg_object: Message | CallbackQuery,
    organization_id: int,
    organization: Organization,
    default_type: MessageType | None = None,
) -> None:
    current_type = default_type

    if isinstance(tg_object, CallbackQuery):
        if not isinstance(tg_object.message, Message):
            return

        if tg_object.data:
            callback_data = MessageCallback.unpack(tg_object.data)
            current_type = callback_data.type

        message = tg_object.message
    else:
        message = tg_object

    if current_type is None:
        raise ValueError("Current message type not set")

    available_chats: list[Chat] = []

    if organization.id == 0:
        if organization.admin_chat_id != message.chat.id:
            await change_callback_or_message(
                tg_object, "❌ Не вдалось ідентифікувати ваш чат"
            )
            return

        if organization_id == 0:
            await show_available_root_admin_org_chats(db, tg_object, current_type)
            return
    else:
        chats_stmt = select(Chat).where(Chat.organization_id == organization_id)
        chats_result = await db.execute(chats_stmt)
        chats = chats_result.scalars().all()

        if (
            organization.id == organization_id
            and organization.admin_chat_id == message.chat.id
        ):
            available_chats = list(chats)
        else:
            current_chat: Chat | None = None
            for chat in chats:
                if chat.id == message.chat.id:
                    current_chat = chat
                elif (chat.visibility_level == VisibilityLevel.PUBLIC) or (
                    organization.id == organization_id
                    and chat.visibility_level == VisibilityLevel.INTERNAL
                ):
                    available_chats.append(chat)

            if (
                organization.id == organization_id
                and not current_chat
                and not organization.admin_chat_id == message.chat.id
            ):
                await change_callback_or_message(
                    tg_object, "❌ Не вдалось ідентифікувати ваш чат"
                )
                return

    if organization.id == 0:
        admin_chat_stmt = select(Organization.title, Organization.admin_chat_id).where(
            Organization.id == organization_id
        )
        admin_chat_result = await db.execute(admin_chat_stmt)
        admin_chat = admin_chat_result.tuples().one_or_none()

        if admin_chat is None:
            await change_callback_or_message(tg_object, "❌ Організація не існує")
            return

        kb = InlineKeyboardBuilder()

        if admin_chat[1] is not None:
            kb.button(
                text=f"Адміністратори {admin_chat[0]}",
                callback_data=MessageCallback(
                    action="select_admin_chat",
                    data=str(organization_id),
                    type=current_type,
                ),
            )

        org_chats_stmt = select(Chat.id, Chat.title).where(
            Chat.organization_id == organization_id
        )
        org_chats_result = await db.execute(org_chats_stmt)
        org_chats = org_chats_result.tuples().all()

        for chat_id, chat_title in org_chats:
            kb.button(
                text=chat_title,
                callback_data=MessageCallback(
                    action="select_chat",
                    data=str(chat_id),
                    type=current_type,
                ),
            )

        kb.button(
            text="⬅️ Назад",
            callback_data=MessageCallback(
                action="select_org",
                type=current_type,
            ),
        )
        kb.button(text="❌ Скасувати", callback_data=MainCallback(action="cancel"))
        kb.adjust(1)

        await change_callback_or_message(
            tg_object, "Оберіть чат:", reply_markup=kb.as_markup()
        )

        return

    public_chat_exists_stmt = (
        select(Chat.id)
        .where(
            Chat.organization_id == Organization.id,
            Chat.type == ChatType.INTERNAL,
            Chat.visibility_level == VisibilityLevel.PUBLIC,
        )
        .exists()
    )

    orgs_stmt = select(
        Organization, public_chat_exists_stmt.label("public_chat_exists")
    ).where(
        Organization.id != organization.id,
        Organization.is_verified.is_(True),
        Organization.is_private.is_(False),
    )
    orgs_result = await db.execute(orgs_stmt)
    organizations = orgs_result.tuples().all()

    is_organizations_available = False
    for org, chat_exists in organizations:
        if (org.is_admins_accept_messages and org.admin_chat_id) or chat_exists:
            is_organizations_available = True
            break

    kb = InlineKeyboardBuilder()
    is_admin_button = False

    if (
        organization.id != organization_id
        or organization.admin_chat_id != message.chat.id
    ):
        current_org: Organization | None = None

        if organization.id == organization_id:
            current_org = organization
        else:
            for org, _ in organizations:
                if org.id == organization_id:
                    current_org = org
                    break

        if (
            current_org
            and current_org.is_admins_accept_messages
            and current_org.admin_chat_id
        ):
            is_admin_button = True
            kb.button(
                text=f"Адміністратори {current_org.title}",
                callback_data=MessageCallback(
                    action="select_admin_chat",
                    data=str(organization_id),
                    type=current_type,
                ),
            )

    if not available_chats and not is_organizations_available and not is_admin_button:
        await change_callback_or_message(tg_object, "❌ Доступні чати відсутні")
        return

    for chat in available_chats:
        kb.button(
            text=chat.title,
            callback_data=MessageCallback(
                action="select_chat",
                data=str(chat.id),
                type=current_type,
            ),
        )

    if is_organizations_available:
        if available_chats or is_admin_button:
            kb.button(
                text=(
                    "📤 Зовнішнє листування"
                    if organization.id == organization_id
                    else "⬅️ Назад"
                ),
                callback_data=MessageCallback(
                    action="select_org",
                    type=current_type,
                ),
            )
        else:
            for org, chat_exists in organizations:
                if (org.is_admins_accept_messages and org.admin_chat_id) or chat_exists:
                    kb.button(
                        text=org.title,
                        callback_data=MessageCallback(
                            action="select_org",
                            data=str(org.id),
                            type=current_type,
                        ),
                    )

    kb.button(text="❌ Скасувати", callback_data=MainCallback(action="cancel"))
    kb.adjust(1)

    if available_chats or is_admin_button:
        await change_callback_or_message(
            tg_object, "Оберіть чат:", reply_markup=kb.as_markup()
        )
        return

    await change_callback_or_message(
        tg_object, "Оберіть організацію:", reply_markup=kb.as_markup()
    )


async def show_available_organizations(
    db: AsyncSession,
    callback: CallbackQuery,
    organization: Organization,
    type: MessageType,
) -> None:
    if not isinstance(callback.message, Message):
        return

    if organization.id == 0:
        if callback.message.chat.id == organization.admin_chat_id:
            await show_available_root_admin_org_chats(db, callback, type)
            return

        await edit_callback_message(callback, "❌ Не вдалось ідентифікувати ваш чат")
        return

    public_chat_exists_stmt = (
        select(Chat.id)
        .where(
            Chat.organization_id == Organization.id,
            Chat.type == ChatType.INTERNAL,
            Chat.visibility_level == VisibilityLevel.PUBLIC,
        )
        .exists()
    )

    orgs_stmt = (
        select(Organization, public_chat_exists_stmt.label("public_chat_exists"))
        .where(
            Organization.id != organization.id,
            Organization.is_verified.is_(True),
            Organization.is_private.is_(False),
        )
        .order_by(Organization.title)
    )
    orgs_result = await db.execute(orgs_stmt)
    organizations = orgs_result.tuples().all()

    available_orgs: list[Organization] = []
    for org, chat_exists in organizations:
        if (org.is_admins_accept_messages and org.admin_chat_id) or chat_exists:
            available_orgs.append(org)

    if not available_orgs:
        await edit_callback_message(callback, "❌ Доступні організації відсутні")
        return

    kb = InlineKeyboardBuilder()

    for org in available_orgs:
        kb.button(
            text=org.title,
            callback_data=MessageCallback(
                action="select_org", data=str(org.id), type=type
            ),
        )

    is_admin_chat_id = callback.message.chat.id == organization.admin_chat_id
    if (
        organization.is_admins_accept_messages
        and organization.admin_chat_id
        and not is_admin_chat_id
    ):
        is_internal_available = True
    else:
        conditions = [
            Chat.organization_id == organization.id,
            Chat.type == ChatType.INTERNAL,
        ]

        if not is_admin_chat_id:
            conditions.append(Chat.visibility_level == VisibilityLevel.INTERNAL)

        chats_stmt = select(exists().where(*conditions))
        chats_exist_result = await db.execute(chats_stmt)
        is_internal_available = bool(chats_exist_result.scalar())

    if is_internal_available:
        kb.button(
            text=("📥 Внутрішнє листування"),
            callback_data=MessageCallback(
                action="select_org", data=str(organization.id), type=type
            ),
        )

    kb.button(text="❌ Скасувати", callback_data=MainCallback(action="cancel"))
    kb.adjust(1)

    await edit_callback_message(
        callback, "Оберіть організацію:", reply_markup=kb.as_markup()
    )


async def send_handler(
    message: Message, lazy_db: LazyDbSession, organization: Organization
) -> None:
    if not message.from_user:
        return

    if message.chat.type == TelegramChatType.PRIVATE:
        await message.answer("❌ Ця команда доступна лише в групових чатах")
        return

    if not message.reply_to_message or message.reply_to_message.forum_topic_created:
        await message.answer("❌ Ця команда має бути реплаєм на повідомлення")
        return

    db = await lazy_db.get()

    if message.chat.id == organization.admin_chat_id:
        await show_available_org_chats(
            db, message, organization.id, organization, MessageType.INFO
        )
        return

    if organization.admin_chat_id == message.chat.id:
        service_text = f"Адміністратори {html.escape(organization.title)}"
    else:
        stmt = select(Chat.type, Chat.title).where(
            Chat.id == message.chat.id, Chat.organization_id == organization.id
        )
        result_db = await db.execute(stmt)
        type_and_title = result_db.tuples().one_or_none()

        if type_and_title is None:
            await message.answer("❌ Не вдалось ідентифікувати ваш чат")
            return

        chat_type, title = type_and_title
        if chat_type == ChatType.INTERNAL:
            await show_available_org_chats(
                db,
                message,
                organization.id,
                organization,
                MessageType.INFO,
            )
            return

        service_text = f"Чат групи {html.escape(title)}"

    if not organization.admin_chat_id or (
        not organization.is_admins_accept_messages
        and (organization.id != 0 or organization.admin_chat_id != message.chat.id)
    ):
        await message.answer("❌ Адміністратори не приймають повідомлення.")
        return

    destination_text = f"<b>{html.escape(organization.title)}</b>"

    await send_message(
        db,
        message.reply_to_message,
        organization.admin_chat_id,
        organization.admin_chat_thread_id,
        None,
        MessageType.REQUEST,
        service_text,
        destination_text,
        message.from_user,
    )
    await put_reaction(message.reply_to_message)


async def send_task_handler(
    message: Message, lazy_db: LazyDbSession, organization: Organization
) -> None:
    if not message.from_user:
        return

    if message.chat.type == TelegramChatType.PRIVATE:
        await message.answer("❌ Ця команда доступна лише в групових чатах")
        return

    if not message.reply_to_message or message.reply_to_message.forum_topic_created:
        await message.answer("❌ Ця команда має бути реплаєм на повідомлення")
        return

    db = await lazy_db.get()

    if message.chat.id != organization.admin_chat_id:
        stmt = select(Chat.type).where(
            Chat.id == message.chat.id, Chat.organization_id == organization.id
        )
        result_db = await db.execute(stmt)
        chat_type = result_db.scalar_one_or_none()

        if chat_type is None:
            await message.answer("❌ Не вдалось ідентифікувати ваш чат")
            return

        if chat_type == ChatType.EXTERNAL:
            await message.answer("❌ Команда призначена лише для внутрішніх чатів")
            return

    await show_available_org_chats(
        db, message, organization.id, organization, MessageType.TASK
    )


async def select_organization_handler(
    callback: CallbackQuery,
    callback_data: MessageCallback,
    lazy_db: LazyDbSession,
    organization: Organization,
) -> None:
    if (
        not isinstance(callback.message, Message)
        or not callback.message.reply_to_message
    ):
        await edit_callback_message(callback, "❌ Реплай на повідомлення відсутній")
        return

    if not callback_data.type:
        return

    db = await lazy_db.get()

    if callback_data.data:
        organization_id = int(callback_data.data)
        await show_available_org_chats(
            db, callback, organization_id, organization, callback_data.type
        )
        return

    await show_available_organizations(db, callback, organization, callback_data.type)


async def select_admin_chat_handler(
    callback: CallbackQuery,
    callback_data: MessageCallback,
    lazy_db: LazyDbSession,
    organization: Organization,
    ban_controller: BanController,
) -> None:
    if (
        not isinstance(callback.message, Message)
        or not callback.message.reply_to_message
    ):
        await edit_callback_message(callback, "❌ Реплай на повідомлення відсутній")
        return

    if not callback_data.data or not callback_data.type:
        return

    organization_id = int(callback_data.data)
    send_organization: Organization | None = None

    db = await lazy_db.get()

    bot: Bot | None = None

    if organization_id == organization.id:
        send_organization = organization
    else:
        organization_stmt = (
            select(Organization)
            .options(joinedload(Organization.bot))
            .where(Organization.id == organization_id)
        )
        organization_result = await db.execute(organization_stmt)
        send_organization = organization_result.scalar_one_or_none()

        if send_organization is None:
            await edit_callback_message(callback, "❌ Організація не знайдена")
            return

        if await ban_controller.get(db, callback.from_user.id, send_organization.id):
            await callback.answer("❌ Вас було заблоковано")
            return

        bot = get_organization_bot(send_organization)

    if not send_organization.admin_chat_id or (
        not send_organization.is_admins_accept_messages
        and (
            organization.id != 0
            or organization.admin_chat_id != callback.message.chat.id
        )
    ):
        await edit_callback_message(
            callback, "❌ Організація вже не приймає повідомлень"
        )
        return

    if organization.admin_chat_id == callback.message.chat.id:
        service_text = f"Адміністратори {html.escape(organization.title)}"
    else:
        chat_stmt = select(Chat).where(Chat.id == callback.message.chat.id)
        chat_result = await db.execute(chat_stmt)
        chat = chat_result.scalar_one_or_none()

        if chat is None:
            await edit_callback_message(
                callback, "❌ Не вдалось ідентифікувати ваш чат"
            )
            return

        if chat.organization_id != organization_id:
            service_text = f"{html.escape(organization.title)}, "
        else:
            service_text = ""

        service_text += html.escape(chat.title)

    feedback_destination = f"адміністраторам {html.escape(send_organization.title)}"

    try:
        await send_message(
            db,
            callback.message.reply_to_message,
            send_organization.admin_chat_id,
            send_organization.admin_chat_thread_id,
            None,
            callback_data.type,
            service_text,
            feedback_destination,
            callback.from_user,
            bot,
        )
    finally:
        if bot:
            await bot.session.close()

    await callback.answer()

    try:
        await callback.message.delete()
    except Exception as e:
        logger.error(e)


async def select_chat_handler(
    callback: CallbackQuery,
    callback_data: MessageCallback,
    lazy_db: LazyDbSession,
    organization: Organization,
    ban_controller: BanController,
) -> None:
    if (
        not isinstance(callback.message, Message)
        or not callback.message.reply_to_message
    ):
        await edit_callback_message(callback, "❌ Реплай на повідомлення відсутній")
        return

    if not callback_data.data or not callback_data.type or not callback.bot:
        return

    chat_id = int(callback_data.data)

    db = await lazy_db.get()

    chat_stmt = (
        select(Chat)
        .options(
            selectinload(Chat.threads),
            joinedload(Chat.organization).joinedload(Organization.bot),
        )
        .where(Chat.id == chat_id)
    )
    chat_result = await db.execute(chat_stmt)
    chat = chat_result.scalar_one_or_none()

    if chat is None:
        await edit_callback_message(callback, "❌ Чат не знайдено")
        return

    if await ban_controller.get(db, callback.from_user.id, chat.organization_id):
        await callback.answer("❌ Вас було заблоковано")
        return

    available_threads: list[ChatThread] = []

    is_admin = organization.admin_chat_id == callback.message.chat.id
    if chat.organization_id == organization.id:
        if not is_admin and chat.visibility_level == VisibilityLevel.PRIVATE:
            await edit_callback_message(callback, "❌ Чат приватний")
            return

        for thread in chat.threads:
            if is_admin or thread.visibility_level in (
                VisibilityLevel.PUBLIC,
                VisibilityLevel.INTERNAL,
            ):
                available_threads.append(thread)
    else:
        is_global_admin = is_admin and organization.id == 0

        if not is_global_admin and chat.visibility_level != VisibilityLevel.PUBLIC:
            await edit_callback_message(callback, "❌ Чат приватний")
            return

        for thread in chat.threads:
            if is_global_admin or thread.visibility_level == VisibilityLevel.PUBLIC:
                available_threads.append(thread)

    if len(available_threads) <= 1:
        if is_admin:
            service_text = f"Адміністратори {html.escape(organization.title)}"
        else:
            current_chat_stmt = select(Chat.title).where(
                Chat.id == callback.message.chat.id,
                Chat.organization_id == organization.id,
            )
            current_chat_result = await db.execute(current_chat_stmt)
            current_chat = current_chat_result.scalar_one_or_none()

            if current_chat is None:
                await edit_callback_message(
                    callback, "❌ Не вдалось ідентифікувати ваш чат"
                )
                return

            if chat.organization_id != organization.id:
                service_text = f"{html.escape(organization.title)}, "
            else:
                service_text = ""

            service_text += html.escape(current_chat)

        bot = callback.bot
        is_callback_bot = True

        if organization.id != chat.organization_id:
            service_dest_text = (
                f"{html.escape(chat.organization.title)}, {html.escape(chat.title)}"
            )
            bot = get_organization_bot(chat.organization)
            is_callback_bot = False
        else:
            service_dest_text = html.escape(chat.title)

        if available_threads:
            thread = available_threads[0]
            service_dest_text += f", {html.escape(thread.title)}"
            thread_id = thread.id
        else:
            thread_id = None

        try:
            sent_message_id = await send_message(
                db,
                callback.message.reply_to_message,
                chat_id,
                thread_id,
                None,
                callback_data.type,
                service_text,
                service_dest_text,
                callback.from_user,
                bot,
            )

            await callback.answer()

            try:
                await callback.message.delete()
            except Exception as e:
                logger.error(e)

            tag_on_requests = (
                thread.tag_on_requests if thread_id else chat.tag_on_requests
            )
            pin_requests = thread.pin_requests if thread_id else chat.pin_requests

            if not sent_message_id or callback_data.type != MessageType.TASK:
                return

            if tag_on_requests:
                try:
                    tags = " ".join([f"@{tag}" for tag in tag_on_requests.split()])
                    await bot.send_message(
                        chat.id,
                        tags,
                        message_thread_id=thread_id,
                        reply_to_message_id=sent_message_id,
                    )
                except Exception as e:
                    logger.error(e)

            if pin_requests:
                try:
                    await bot.pin_chat_message(
                        thread.chat.id, sent_message_id, disable_notification=True
                    )
                except Exception as e:
                    logger.error(e)
                    await bot.send_message(
                        chat_id,
                        "❌ Не вдалось запінить повідомлення, перевірте чи у бота достатньо прав на це.",
                        message_thread_id=thread_id,
                        reply_to_message_id=sent_message_id,
                    )
        finally:
            if not is_callback_bot:
                await bot.session.close()

        return

    kb = InlineKeyboardBuilder()

    for thread in available_threads:
        kb.button(
            text=thread.title,
            callback_data=MessageCallback(
                action="select_thread",
                data=f"{chat.id}|{thread.id}",
                type=callback_data.type,
            ),
        )

    kb.button(
        text="⬅️ Назад",
        callback_data=MessageCallback(
            action="select_org", data=str(chat.organization_id), type=callback_data.type
        ),
    )
    kb.button(text="❌ Скасувати", callback_data=MainCallback(action="cancel"))
    kb.adjust(1)

    await edit_callback_message(callback, "Оберіть гілку:", reply_markup=kb.as_markup())


async def select_thread_handler(
    callback: CallbackQuery,
    callback_data: MessageCallback,
    lazy_db: LazyDbSession,
    organization: Organization,
    ban_controller: BanController,
) -> None:
    if (
        not isinstance(callback.message, Message)
        or not callback.message.reply_to_message
    ):
        await edit_callback_message(callback, "❌ Реплай на повідомлення відсутній")
        return

    if not callback_data.data or not callback_data.type or not callback.bot:
        return

    chat_id, thread_id = [int(x) for x in callback_data.data.split("|", 1)]

    db = await lazy_db.get()

    thread_stmt = (
        select(ChatThread)
        .options(
            joinedload(ChatThread.chat)
            .joinedload(Chat.organization)
            .joinedload(Organization.bot)
        )
        .where(ChatThread.id == thread_id, ChatThread.chat_id == chat_id)
    )
    thread_result = await db.execute(thread_stmt)
    thread = thread_result.scalar_one_or_none()

    if thread is None:
        await edit_callback_message(callback, "❌ Гілку не знайдено")
        return

    if await ban_controller.get(db, callback.from_user.id, thread.chat.organization_id):
        await callback.answer("❌ Вас було заблоковано")
        return

    is_admin = organization.admin_chat_id == callback.message.chat.id
    if thread.chat.organization_id == organization.id:
        if not is_admin and thread.chat.visibility_level == VisibilityLevel.PRIVATE:
            await edit_callback_message(callback, "❌ Чат приватний")
            return

        if not is_admin and thread.visibility_level == VisibilityLevel.PRIVATE:
            await edit_callback_message(callback, "❌ Гілка приватна")
            return

        service_text = ""
    else:
        is_global_admin = is_admin and organization.id == 0

        if (
            not is_global_admin
            and thread.chat.visibility_level != VisibilityLevel.PUBLIC
        ):
            await edit_callback_message(callback, "❌ Чат приватний")
            return

        if not is_global_admin and thread.visibility_level != VisibilityLevel.PUBLIC:
            await edit_callback_message(callback, "❌ Гілка приватна")
            return

        service_text = f"{html.escape(organization.title)}, "

    if is_admin:
        service_text = f"Адміністратори {html.escape(organization.title)}"
    else:
        current_chat_stmt = select(Chat.title).where(
            Chat.id == callback.message.chat.id, Chat.organization_id == organization.id
        )
        current_chat_result = await db.execute(current_chat_stmt)
        current_chat = current_chat_result.scalar_one_or_none()

        if current_chat is None:
            await edit_callback_message(
                callback, "❌ Не вдалось ідентифікувати ваш чат"
            )
            return

        service_text += html.escape(current_chat)

    bot = callback.bot
    is_callback_bot = True

    if organization.id != thread.chat.organization_id:
        service_dest_text = f"{html.escape(thread.chat.organization.title)}, {html.escape(thread.chat.title)}, {html.escape(thread.title)}"
        is_callback_bot = False
        bot = get_organization_bot(thread.chat.organization)
    else:
        service_dest_text = (
            f"{html.escape(thread.chat.title)}, {html.escape(thread.title)}"
        )

    try:
        sent_message_id = await send_message(
            db,
            callback.message.reply_to_message,
            chat_id,
            thread_id,
            None,
            callback_data.type,
            service_text,
            service_dest_text,
            callback.from_user,
            bot,
        )

        await callback.answer()

        try:
            await callback.message.delete()
        except Exception as e:
            logger.error(e)

        if not sent_message_id or callback_data.type != MessageType.TASK:
            return

        if thread.tag_on_requests:
            try:
                tags = " ".join([f"@{tag}" for tag in thread.tag_on_requests.split()])
                await bot.send_message(
                    chat_id,
                    tags,
                    message_thread_id=thread_id,
                    reply_to_message_id=sent_message_id,
                )
            except Exception as e:
                logger.error(e)

        if thread.pin_requests:
            try:
                await bot.pin_chat_message(
                    thread.chat.id, sent_message_id, disable_notification=True
                )
            except Exception as e:
                logger.error(e)
                await bot.send_message(
                    chat_id,
                    "❌ Не вдалось запінить повідомлення, перевірте чи у бота достатньо прав на це.",
                    message_thread_id=thread_id,
                    reply_to_message_id=sent_message_id,
                )
    finally:
        if not is_callback_bot:
            await bot.session.close()
