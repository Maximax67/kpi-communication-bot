from collections import defaultdict
from datetime import timezone
from aiogram.enums import ChatType
from aiogram.types import Message
from sqlalchemy import or_, select
from sqlalchemy.orm import joinedload
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logger import logger
from app.core.enums import MessageType, MessageStatus
from app.db.models.message import Message as MessageDB
from app.db.models.organization import Organization
from bot.middlewares.db_session import LazyDbSession
from bot.utils.format_message_url import format_message_url
from bot.utils.get_bot import get_organization_bot
from bot.utils.message_splitter import TelegramHTMLSplitter


INCOMING_SECTIONS = [
    (
        (MessageStatus.IN_PROCESS, False),
        "🟡 <b>В обробці:</b>",
    ),
    (
        (MessageStatus.NEW, False),
        "🔴 <b>Не оброблені:</b>",
    ),
]

OUTGOING_SECTIONS = [
    (
        (MessageStatus.IN_PROCESS, True),
        "🟨 <b>В обробці:</b>",
    ),
    (
        (MessageStatus.NEW, True),
        "🟥 <b>Не оброблені:</b>",
    ),
]


async def render_section(
    splitter: TelegramHTMLSplitter,
    header: str,
    messages: list[MessageDB],
    *,
    newline_before: bool = False,
) -> None:
    if not messages:
        return

    if newline_before:
        await splitter.add("\n")

    await splitter.add(f"{header}\n")

    for idx, msg in enumerate(messages, 1):
        url = format_message_url(
            msg.destination_chat_id,
            msg.destination_thread_id,
            msg.destination_message_id,
        )
        date_utc = msg.created_at.astimezone(timezone.utc).strftime("%d.%m")

        await splitter.add(f"{idx}) {url} {date_utc}\n")


async def show_pending(
    db: AsyncSession,
    message: Message,
    message_thread_id: int | None,
    title: str,
) -> None:
    conditions = [
        MessageDB.destination_chat_id == message.chat.id,
        MessageDB.type == MessageType.SERVICE,
        MessageDB.status.in_([MessageStatus.IN_PROCESS, MessageStatus.NEW]),
    ]

    if message_thread_id:
        if message_thread_id == 1:
            conditions.append(
                or_(
                    MessageDB.destination_thread_id == 1,
                    MessageDB.destination_thread_id.is_(None),
                ),
            )
        else:
            conditions.append(
                MessageDB.destination_thread_id == message_thread_id,
            )

    stmt = select(MessageDB).where(*conditions).order_by(MessageDB.id)

    result = await db.execute(stmt)
    msgs = result.scalars().all()

    groups: dict[tuple[MessageStatus | None, bool | None], list[MessageDB]] = (
        defaultdict(list)
    )

    for msg in msgs:
        groups[(msg.status, msg.is_status_reference)].append(msg)

    splitter = TelegramHTMLSplitter(send_func=message.answer)

    await splitter.add(f"{title}\n\n")

    incoming_has_messages = False
    for i, (key, header) in enumerate(INCOMING_SECTIONS):
        msgs_list = groups.get(key)
        if not msgs_list:
            continue

        await render_section(
            splitter,
            header,
            msgs_list,
            newline_before=incoming_has_messages and i != 0,
        )
        incoming_has_messages = True

    if incoming_has_messages:
        await splitter.add("\n")
    else:
        await splitter.add("✅ Вхідні запити оброблено!\n")

    outgoing_has_messages = False
    for key, header in OUTGOING_SECTIONS:
        msgs_list = groups.get(key)
        if not msgs_list:
            continue

        if not outgoing_has_messages:
            if not incoming_has_messages:
                await splitter.add("\n")

            await splitter.add("<b>--- Вихідні запити ---</b>\n")

        await render_section(
            splitter,
            header,
            msgs_list,
            newline_before=True,
        )
        outgoing_has_messages = True

    if not outgoing_has_messages:
        await splitter.add("✅ Вихідні запити оброблено!")

    await splitter.flush()


async def pending_handler(
    message: Message,
    lazy_db: LazyDbSession,
) -> None:
    if message.chat.type == ChatType.PRIVATE:
        await message.answer("❌ Ця команда доступна лише в групових чатах")
        return

    if message.chat.type == ChatType.GROUP:
        await message.answer(
            "❌ Ця команда доступна лише суперчатах. Прості групи не дозволяють створювати посилання на повідомлення. Аби мігрувати до суперчату просто увімкніть історію чату."
        )
        return

    db = await lazy_db.get()

    thread_id = message.message_thread_id
    if message.chat.is_forum and thread_id is None:
        thread_id = 1

    title = "<b>Запити гілки</b>" if thread_id else "<b>Запити чату</b>"

    await show_pending(db, message, thread_id, title)


async def pending_chat_handler(
    message: Message,
    lazy_db: LazyDbSession,
) -> None:
    if message.chat.type == ChatType.PRIVATE:
        await message.answer("❌ Ця команда доступна лише в групових чатах")
        return

    if message.chat.type == ChatType.GROUP:
        await message.answer(
            "❌ Ця команда доступна лише суперчатах. Прості групи не дозволяють створювати посилання на повідомлення. Аби мігрувати до суперчату просто увімкніть історію чату."
        )
        return

    db = await lazy_db.get()

    await show_pending(db, message, None, "<b>Запити чату</b>")


async def send_daily_pending_notification(
    db: AsyncSession, organization: Organization
) -> None:
    if not organization.admin_chat_id or not organization.bot:
        return

    conditions = [
        MessageDB.destination_chat_id == organization.admin_chat_id,
        MessageDB.type == MessageType.SERVICE,
        MessageDB.status.in_([MessageStatus.IN_PROCESS, MessageStatus.NEW]),
    ]

    if organization.admin_chat_thread_id:
        conditions.append(
            or_(
                MessageDB.destination_thread_id == organization.admin_chat_thread_id,
                MessageDB.destination_thread_id.is_(None),
            )
        )

    stmt = select(MessageDB).where(*conditions).order_by(MessageDB.id)

    result = await db.execute(stmt)
    msgs = result.scalars().all()

    if not msgs:
        return

    groups: dict[tuple[MessageStatus | None, bool | None], list[MessageDB]] = (
        defaultdict(list)
    )

    for msg in msgs:
        groups[(msg.status, msg.is_status_reference)].append(msg)

    bot = get_organization_bot(organization)

    async def send_func(text: str, parse_mode: str | None = None) -> None:
        if organization.admin_chat_id:
            await bot.send_message(
                organization.admin_chat_id,
                text,
                message_thread_id=organization.admin_chat_thread_id,
                parse_mode=parse_mode,
            )

    try:
        splitter = TelegramHTMLSplitter(send_func=send_func)

        await splitter.add("📅 <b>Щоденне нагадування про необроблені запити</b>\n\n")

        incoming_has_messages = False
        for i, (key, header) in enumerate(INCOMING_SECTIONS):
            msgs_list = groups.get(key)
            if not msgs_list:
                continue

            await render_section(
                splitter,
                header,
                msgs_list,
                newline_before=incoming_has_messages and i != 0,
            )
            incoming_has_messages = True

        if incoming_has_messages:
            await splitter.add("\n")

        outgoing_has_messages = False
        for key, header in OUTGOING_SECTIONS:
            msgs_list = groups.get(key)
            if not msgs_list:
                continue

            if not outgoing_has_messages:
                if not incoming_has_messages:
                    await splitter.add("\n")

                await splitter.add("<b>--- Вихідні запити ---</b>\n")

            await render_section(
                splitter,
                header,
                msgs_list,
                newline_before=True,
            )
            outgoing_has_messages = True

        await splitter.flush()
    except Exception as e:
        logger.error(
            f"Failed to send daily pending notification for org {organization.id}: {e}"
        )
    finally:
        await bot.session.close()


async def send_all_daily_pending_notifications(db: AsyncSession) -> None:
    stmt = (
        select(Organization)
        .options(joinedload(Organization.bot))
        .where(
            Organization.daily_pending_notifications.is_(True),
            Organization.admin_chat_id.is_not(None),
            Organization.bot.has(),
        )
    )

    result = await db.execute(stmt)
    organizations = result.scalars().all()

    logger.info(
        f"Sending daily pending notifications to {len(organizations)} organizations"
    )

    for organization in organizations:
        try:
            await send_daily_pending_notification(db, organization)
        except Exception as e:
            logger.error(
                f"Error sending daily notification for org {organization.id}: {e}"
            )
