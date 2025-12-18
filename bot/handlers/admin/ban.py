import html
from aiogram.types import Message
from sqlalchemy import select

from app.db.models.organization import Organization
from app.db.models.user import User
from app.db.models.banned_user import BannedUser
from bot.middlewares.ban_middleware import BanController
from bot.middlewares.db_session import LazyDbSession
from bot.utils.format_user import format_user_info_html
from bot.utils.message_splitter import TelegramHTMLSplitter


async def ban_user_handler(
    message: Message,
    organization: Organization,
    ban_controller: BanController,
    lazy_db: LazyDbSession,
) -> None:
    if not message.from_user or not message.text:
        return

    if message.chat.id != organization.admin_chat_id:
        await message.answer(
            "❌ Команда доступна для виконання лише з чату адміністраторів організації"
        )
        return

    parts = message.text.split(maxsplit=2)

    if len(parts) < 3:
        await message.answer(
            "❌ <b>Неправильний формат команди</b>\n\n"
            "<b>Використання:</b>\n"
            "<code>/ban {user_id} причина</code>\n"
            "<code>/ban @username причина</code>\n\n"
            "<b>Приклад:</b>\n"
            "<code>/ban 123456789 Порушення правил</code>\n"
            "<code>/ban @username Спам</code>",
            parse_mode="HTML",
        )
        return

    user_identifier = parts[1]
    reason = parts[2]

    db = await lazy_db.get()
    target_user = None

    if user_identifier.startswith("@"):
        username = user_identifier[1:]
        query = select(User).where(User.username == username)
        result = await db.execute(query)
        target_user = result.scalar_one_or_none()

        if not target_user:
            await message.answer(
                f"❌ Користувача з username <code>@{html.escape(username)}</code> не знайдено в базі даних",
                parse_mode="HTML",
            )
            return
    else:
        try:
            user_id = int(user_identifier)
        except ValueError:
            await message.answer(
                "❌ Неправильний формат ID користувача. Використовуйте числовий ID або @username",
                parse_mode="HTML",
            )
            return

        query = select(User).where(User.id == user_id)
        result = await db.execute(query)
        target_user = result.scalar_one_or_none()

        if not target_user:
            await message.answer(
                f"❌ Користувача з ID <code>{user_id}</code> не знайдено в базі даних",
                parse_mode="HTML",
            )
            return

    if not await ban_controller.ban_user(
        db, target_user.id, organization.id, message.from_user.id, reason
    ):
        await message.answer(
            f"❌ Користувач {format_user_info_html(target_user)} вже заблокований",
            parse_mode="HTML",
        )
        return

    await message.answer(
        f"✅ <b>Користувача заблоковано</b>\n\n"
        f"<b>Користувач:</b> {format_user_info_html(target_user)}\n"
        f"<b>ID:</b> <code>{target_user.id}</code>\n"
        f"<b>Причина:</b> {html.escape(reason)}\n"
        f"<b>Заблокував:</b> {format_user_info_html(message.from_user)}",
        parse_mode="HTML",
    )

    try:
        if message.bot:
            await message.bot.send_message(target_user.id, "❌ Вас заблоковано!")
    except Exception:
        pass


async def unban_user_handler(
    message: Message,
    organization: Organization,
    ban_controller: BanController,
    lazy_db: LazyDbSession,
) -> None:
    if not message.from_user or not message.text:
        return

    if message.chat.id != organization.admin_chat_id:
        await message.answer(
            "❌ Команда доступна для виконання лише з чату адміністраторів організації"
        )
        return

    parts = message.text.split(maxsplit=2)

    if len(parts) < 2:
        await message.answer(
            "❌ <b>Неправильний формат команди</b>\n\n"
            "<b>Використання:</b>\n"
            "<code>/unban {user_id} [причина]</code>\n"
            "<code>/unban @username [причина]</code>\n\n"
            "<b>Приклад:</b>\n"
            "<code>/unban 123456789</code>\n"
            "<code>/unban @username Помилка</code>",
            parse_mode="HTML",
        )
        return

    user_identifier = parts[1]
    unban_reason = parts[2] if len(parts) > 2 else None

    db = await lazy_db.get()
    target_user_id: int | None = None

    if user_identifier.startswith("@"):
        username = user_identifier[1:]
        query = select(User).where(User.username == username)
        result = await db.execute(query)
        target_user = result.scalar_one_or_none()

        if not target_user:
            await message.answer(
                f"❌ Користувача з username <code>@{html.escape(username)}</code> не знайдено в базі даних",
                parse_mode="HTML",
            )
            return
        target_user_id = target_user.id
    else:
        try:
            target_user_id = int(user_identifier)
        except ValueError:
            await message.answer(
                "❌ Неправильний формат ID користувача. Використовуйте числовий ID або @username",
                parse_mode="HTML",
            )
            return

        query = select(User).where(User.id == target_user_id)
        result = await db.execute(query)
        target_user = result.scalar_one_or_none()

        if not target_user:
            await message.answer(
                f"❌ Користувача з ID <code>{target_user_id}</code> не знайдено в базі даних",
                parse_mode="HTML",
            )
            return

    if not await ban_controller.unban_user(db, target_user_id, organization.id):
        await message.answer(
            f"❌ Користувач {format_user_info_html(target_user)} не заблокований",
            parse_mode="HTML",
        )
        return

    response_text = (
        f"✅ <b>Користувача розблоковано</b>\n\n"
        f"<b>Користувач:</b> {format_user_info_html(target_user)}\n"
        f"<b>ID:</b> <code>{target_user.id}</code>\n"
        f"<b>Розблокував:</b> {format_user_info_html(message.from_user)}"
    )

    if unban_reason:
        response_text += f"\n<b>Причина розблокування:</b> {html.escape(unban_reason)}"

    await message.answer(response_text, parse_mode="HTML")

    try:
        if message.bot:
            await message.bot.send_message(target_user_id, "✅ Вас розблоковано!")
    except Exception:
        pass


async def ban_list_handler(
    message: Message,
    organization: Organization,
    lazy_db: LazyDbSession,
) -> None:
    if not message.from_user:
        return

    if message.chat.id != organization.admin_chat_id:
        await message.answer(
            "❌ Команда доступна для виконання лише з чату адміністраторів організації"
        )
        return

    db = await lazy_db.get()
    query = (
        select(BannedUser)
        .where(BannedUser.organization_id == organization.id)
        .order_by(BannedUser.created_at)
    )
    result = await db.execute(query)
    banned_users = result.scalars().all()

    if not banned_users:
        await message.answer(
            "Список заблокованих користувачів порожній",
            parse_mode="HTML",
        )
        return

    user_ids = [banned.user_id for banned in banned_users]
    users_query = select(User).where(User.id.in_(user_ids))
    users_result = await db.execute(users_query)
    users = {user.id: user for user in users_result.scalars().all()}

    admin_ids = list(set([banned.banned_by for banned in banned_users]))
    admins_query = select(User).where(User.id.in_(admin_ids))
    admins_result = await db.execute(admins_query)
    admins = {user.id: user for user in admins_result.scalars().all()}

    splitter = TelegramHTMLSplitter(send_func=message.answer)
    await splitter.add("🚫 <b>Список заблокованих користувачів</b>\n\n")
    await splitter.add(f"<b>Організація:</b> {html.escape(organization.title)}\n")
    await splitter.add(f"<b>Всього заблоковано:</b> {len(banned_users)}\n\n")

    for idx, banned in enumerate(banned_users, 1):
        user = users.get(banned.user_id)
        admin = admins.get(banned.banned_by)

        if user:
            user_info = format_user_info_html(user)
        else:
            user_info = f"ID: <code>{banned.user_id}</code>"

        if admin:
            admin_info = format_user_info_html(admin)
        else:
            admin_info = f"ID: <code>{banned.banned_by}</code>"

        await splitter.add(f"<b>{idx}.</b> {user_info}\n")

        if user:
            await splitter.add(f"<b>ID:</b> <code>{banned.user_id}</code>\n")

        if banned.reason:
            await splitter.add(f"<b>Причина:</b> {html.escape(banned.reason)}\n")

        await splitter.add(f"<b>Заблокував:</b> {admin_info}\n")
        await splitter.add(
            f"<b>Дата:</b> {banned.created_at.strftime('%Y-%m-%d %H:%M:%S')}\n\n"
        )

    await splitter.flush()
