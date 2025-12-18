import html
import re
from aiogram.types import Message, CallbackQuery
from aiogram.utils.keyboard import InlineKeyboardBuilder
from sqlalchemy import delete, select

from app.core.constants import COLUMN_REGEX, RANGE_REGEX, SPREADSHEET_URL_REGEX
from app.core.enums import ChatType, MessageType, SpamType
from app.core.logger import logger
from app.core.utils import update_captains
from app.db.models.captain_spreadsheet import CaptainSpreadsheet
from app.db.models.chat import Chat
from app.db.models.chat_captain import ChatCaptain
from app.db.models.organization import Organization
from bot.callback import MainCallback, SpamCallback
from bot.handlers.request.message_handler import send_message
from bot.middlewares.db_session import LazyDbSession
from bot.utils.edit_callback_message import edit_callback_message
from bot.utils.message_splitter import TelegramHTMLSplitter


async def set_captains_spreadsheet_handler(
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

    parts = message.text.split(maxsplit=4)

    if len(parts) < 4:
        await message.answer(
            "❌ <b>Використання:</b>\n"
            "<code>/set_captains_spreadsheet {url} {chat_column} {username_column} [sheet_name] [rows_min-rows_max]</code>\n\n"
            "<b>Приклад:</b>\n"
            "<code>/set_captains_spreadsheet https://docs.google.com/spreadsheets/d/ABC123 A B Sheet1 2-50</code>\n\n"
            "Параметри в квадратних дужках є опціональними.",
            parse_mode="HTML",
        )
        return

    url = parts[1]
    chat_column = parts[2].upper()
    username_column = parts[3].upper()

    url_match = SPREADSHEET_URL_REGEX.search(url)
    if not url_match:
        await message.answer(
            "❌ Невірний URL таблиці Google Sheets. Використовуйте формат:\n"
            "<code>https://docs.google.com/spreadsheets/d/YOUR_SPREADSHEET_ID</code>",
            parse_mode="HTML",
        )
        return

    spreadsheet_id = url_match.group(1)

    if not COLUMN_REGEX.match(chat_column):
        await message.answer(
            f"❌ Невірний формат колонки для назви чату: {html.escape(chat_column)}\n"
            "Використовуйте формат A, B, C, ..., Z, AA, AB, ..., ZZZ",
            parse_mode="HTML",
        )
        return

    if not COLUMN_REGEX.match(username_column):
        await message.answer(
            f"❌ Невірний формат колонки для username: {html.escape(username_column)}\n"
            "Використовуйте формат A, B, C, ..., Z, AA, AB, ..., ZZZ",
            parse_mode="HTML",
        )
        return

    if len(chat_column) > 3 or len(username_column) > 3:
        await message.answer("❌ Назва колонки не може бути довшою за 3 символи")
        return

    sheet_name: str | None = None
    rows_range_min: int | None = None
    rows_range_max: int | None = None

    if len(parts) >= 5:
        remaining = parts[4].strip()
        range_match = RANGE_REGEX.search(remaining)
        if range_match:
            rows_range_min = int(range_match.group(1))
            rows_range_max = int(range_match.group(2))

            if rows_range_min >= rows_range_max:
                await message.answer(
                    "❌ Мінімальне значення діапазону рядків має бути меншим за максимальне"
                )
                return

            if rows_range_min < 0 or rows_range_max < 0:
                await message.answer(
                    "❌ Значення діапазону рядків не можуть бути від'ємними"
                )
                return

            remaining = remaining[: range_match.start()].strip()

        if remaining:
            sheet_name = remaining

    db = await lazy_db.get()

    existing_stmt = select(CaptainSpreadsheet).where(
        CaptainSpreadsheet.organization_id == organization.id
    )
    existing_result = await db.execute(existing_stmt)
    existing = existing_result.scalar_one_or_none()

    if existing:
        existing.spreadsheet_id = spreadsheet_id
        existing.chat_title_column = chat_column
        existing.username_column = username_column
        existing.sheet_name = sheet_name
        existing.rows_range_min = rows_range_min
        existing.rows_range_max = rows_range_max
        action = "оновлено"
    else:
        new_spreadsheet = CaptainSpreadsheet(
            organization_id=organization.id,
            spreadsheet_id=spreadsheet_id,
            chat_title_column=chat_column,
            username_column=username_column,
            sheet_name=sheet_name,
            rows_range_min=rows_range_min,
            rows_range_max=rows_range_max,
        )
        db.add(new_spreadsheet)
        action = "встановлено"

    await db.commit()

    try:
        await update_captains(db)

        await message.answer(
            f"✅ Таблицю старост успішно {action} та синхронізовано!\n\n"
            f"<b>ID таблиці:</b> <code>{html.escape(spreadsheet_id)}</code>\n"
            f"<b>Колонка назви чату:</b> {html.escape(chat_column)}\n"
            f"<b>Колонка username:</b> {html.escape(username_column)}\n"
            + (
                f"<b>Назва аркуша:</b> {html.escape(sheet_name)}\n"
                if sheet_name
                else ""
            )
            + (
                f"<b>Діапазон рядків:</b> {rows_range_min}-{rows_range_max}\n"
                if rows_range_min and rows_range_max
                else ""
            ),
            parse_mode="HTML",
        )
    except Exception as e:
        logger.error(e)
        await message.answer(
            f"⚠️ Таблицю {action}, але виникла помилка при синхронізації:\n"
            f"<code>{html.escape(str(e))}</code>\n\n",
            parse_mode="HTML",
        )


async def delete_captains_spreadsheet_handler(
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

    spreadsheet_stmt = select(CaptainSpreadsheet).where(
        CaptainSpreadsheet.organization_id == organization.id
    )
    spreadsheet_result = await db.execute(spreadsheet_stmt)
    spreadsheet = spreadsheet_result.scalar_one_or_none()

    if not spreadsheet:
        await message.answer("❌ Таблиця старост не налаштована для цієї організації")
        return

    external_chats_stmt = select(Chat).where(
        Chat.organization_id == organization.id, Chat.type == ChatType.EXTERNAL
    )
    external_chats_result = await db.execute(external_chats_stmt)
    external_chats = external_chats_result.scalars().all()
    external_chats_count = len(external_chats)

    await db.execute(
        delete(Chat).where(
            Chat.organization_id == organization.id, Chat.type == ChatType.EXTERNAL
        )
    )

    captains_stmt = select(ChatCaptain).where(
        ChatCaptain.organization_id == organization.id
    )
    captains_result = await db.execute(captains_stmt)
    captains = captains_result.scalars().all()
    captains_count = len(captains)

    await db.execute(
        delete(ChatCaptain).where(ChatCaptain.organization_id == organization.id)
    )

    await db.delete(spreadsheet)
    await db.commit()

    await message.answer(
        f"✅ Таблицю старост успішно видалено!\n\n"
        f"<b>Видалено зовнішніх чатів:</b> {external_chats_count}\n"
        f"<b>Видалено старост:</b> {captains_count}",
        parse_mode="HTML",
    )


async def spam_groups_handler(
    message: Message,
    organization: Organization,
    lazy_db: LazyDbSession,
) -> None:
    await handle_spam_command(message, organization, lazy_db, SpamType.GROUPS)


async def spam_captains_handler(
    message: Message,
    organization: Organization,
    lazy_db: LazyDbSession,
) -> None:
    await handle_spam_command(message, organization, lazy_db, SpamType.CAPTAINS)


async def spam_all_groups_handler(
    message: Message,
    organization: Organization,
    lazy_db: LazyDbSession,
) -> None:
    await handle_spam_command(message, organization, lazy_db, SpamType.ALL_GROUPS)


async def spam_all_captains_handler(
    message: Message,
    organization: Organization,
    lazy_db: LazyDbSession,
) -> None:
    await handle_spam_command(message, organization, lazy_db, SpamType.ALL_CAPTAINS)


async def handle_spam_command(
    message: Message,
    organization: Organization,
    lazy_db: LazyDbSession,
    spam_type: SpamType,
) -> None:
    if not message.text or not message.from_user:
        return

    if message.chat.id != organization.admin_chat_id:
        await message.answer(
            "❌ Команда доступна для виконання лише з чату адміністраторів організації"
        )
        return

    if not message.reply_to_message:
        await message.answer("❌ Команда має бути реплаєм на повідомлення для розсилки")
        return

    db = await lazy_db.get()

    group_names: list[str] = []
    if spam_type in (SpamType.GROUPS, SpamType.CAPTAINS):
        parts = message.text.split(maxsplit=1)
        if len(parts) < 2:
            cmd_name = (
                "spam_groups" if spam_type == SpamType.GROUPS else "spam_captains"
            )
            await message.answer(
                f"❌ <b>Використання:</b>\n"
                f"<code>/{cmd_name} Група 1, Група 2, Група 3</code>",
                parse_mode="HTML",
            )
            return

        group_names = [name.strip() for name in parts[1].split(",") if name.strip()]

        if not group_names:
            await message.answer("❌ Не вказано жодної групи")
            return

    found_targets: list[tuple[str, int]] = []
    not_found: list[str] = []

    if spam_type == SpamType.GROUPS:
        stmt_groups = (
            select(Chat.title, Chat.id)
            .where(
                Chat.organization_id == organization.id,
                Chat.type == ChatType.EXTERNAL,
                Chat.title.in_(group_names),
            )
            .order_by(Chat.title)
        )

        result_groups = await db.execute(stmt_groups)
        rows_groups = result_groups.tuples().all()
        found_map_groups = {title: chat_id for title, chat_id in rows_groups}

        for group_name in group_names:
            found = found_map_groups.get(group_name)
            if found:
                found_targets.append((group_name, found))
            else:
                not_found.append(group_name)

    elif spam_type == SpamType.CAPTAINS:
        stmt_captains = (
            select(ChatCaptain.chat_title, ChatCaptain.connected_user_id)
            .where(
                ChatCaptain.organization_id == organization.id,
                ChatCaptain.chat_title.in_(group_names),
                ChatCaptain.connected_user_id.is_not(None),
                ChatCaptain.is_bot_blocked.is_(False),
            )
            .order_by(ChatCaptain.chat_title)
        )

        result_captains = await db.execute(stmt_captains)
        rows_captains = result_captains.tuples().all()
        found_map_captains = {title: user_id for title, user_id in rows_captains}

        for group_name in group_names:
            found = found_map_captains.get(group_name)
            if found and found is not None:
                found_targets.append((group_name, found))
            else:
                not_found.append(group_name)

    elif spam_type == SpamType.ALL_GROUPS:
        chats_stmt = (
            select(Chat)
            .where(
                Chat.organization_id == organization.id, Chat.type == ChatType.EXTERNAL
            )
            .order_by(Chat.title)
        )
        chats_result = await db.execute(chats_stmt)
        chats = chats_result.scalars().all()

        for chat in chats:
            found_targets.append((chat.title, chat.id))

    elif spam_type == SpamType.ALL_CAPTAINS:
        captains_stmt = (
            select(ChatCaptain)
            .where(
                ChatCaptain.organization_id == organization.id,
                ChatCaptain.connected_user_id.is_not(None),
                ChatCaptain.is_bot_blocked.is_(False),
            )
            .order_by(ChatCaptain.chat_title)
        )
        captains_result = await db.execute(captains_stmt)
        captains = captains_result.scalars().all()

        for captain in captains:
            if captain.connected_user_id:
                found_targets.append((captain.chat_title, captain.connected_user_id))

    if not found_targets:
        await message.answer("❌ Не знайдено жодного отримувача для розсилки")
        return

    target_type = (
        "групи" if spam_type in (SpamType.GROUPS, SpamType.ALL_GROUPS) else "староста"
    )
    confirmation_text = (
        f"<b>Підтвердження розсилки до {len(found_targets)} {target_type}</b>\n\n"
    )

    if found_targets:
        confirmation_text += f"<b>Знайдено ({len(found_targets)}):</b>\n"
        for name, _ in found_targets:
            confirmation_text += f"• {html.escape(name)}\n"

    if not_found:
        confirmation_text += f"\n<b>Не знайдено ({len(not_found)}):</b>\n"
        for name in not_found:
            confirmation_text += f"• {html.escape(name)}\n"

    confirmation_text += "\n⚠️ Ви впевнені, що хочете розіслати повідомлення?"

    kb = InlineKeyboardBuilder()
    kb.button(
        text="✅ Так, розіслати",
        callback_data=SpamCallback(type=spam_type),
    )
    kb.button(text="❌ Скасувати", callback_data=MainCallback(action="cancel"))
    kb.adjust(1)

    await message.answer(
        confirmation_text,
        reply_markup=kb.as_markup(),
        reply_to_message_id=message.reply_to_message.message_id,
        parse_mode="HTML",
    )


async def confirm_spam_handler(
    callback: CallbackQuery,
    callback_data: SpamCallback,
    organization: Organization,
    lazy_db: LazyDbSession,
) -> None:
    if (
        not isinstance(callback.message, Message)
        or not callback.message.reply_to_message
        or not callback.message.text
    ):
        await callback.answer("❌ Повідомлення для розсилки не знайдено")
        return

    if not callback.message.text:
        await callback.answer("❌ Текст з переліком груп не знайдено")
        return

    spam_type = callback_data.type
    if spam_type not in (
        SpamType.GROUPS,
        SpamType.CAPTAINS,
        SpamType.ALL_GROUPS,
        SpamType.ALL_CAPTAINS,
    ):
        await callback.answer("❌ Невідомий тип розсилки")
        return

    message_to_send = callback.message.reply_to_message

    group_names: list[str] = []
    lines = [ln.strip() for ln in callback.message.text.splitlines() if ln.strip()]

    group_names = []
    start_idx = None
    for i, ln in enumerate(lines):
        if re.match(r"^Знайдено\b", ln, re.IGNORECASE):
            start_idx = i + 1
            break

    bullet_re = re.compile(r"^[\u2022•\-\*]\s*(.+)")

    if start_idx is not None:
        for ln in lines[start_idx:]:
            if re.match(r"^(Не\s+знайдено\b|⚠️|❌)", ln, re.IGNORECASE):
                break

            m = bullet_re.match(ln)
            if m:
                group_names.append(m.group(1).strip())
            else:
                if re.match(r"^[A-ZА-ЯІЇЄ].*", ln):
                    break
    else:
        for ln in lines:
            m = bullet_re.match(ln)
            if m:
                group_names.append(m.group(1).strip())

    seen: set[str] = set()
    deduped: list[str] = []
    for g in group_names:
        if g and g not in seen:
            seen.add(g)
            deduped.append(g)

    group_names = deduped

    if not group_names:
        await edit_callback_message(callback, "❌ Не вдалося розпарсити групи")
        return

    await edit_callback_message(
        callback, "⏳ Розсилка розпочата... Це може зайняти деякий час."
    )

    try:
        db = await lazy_db.get()
        targets: list[tuple[str, int, int | None]] = []

        if spam_type in (SpamType.GROUPS, SpamType.ALL_GROUPS):
            for group_name in group_names:
                chat_stmt = select(Chat).where(
                    Chat.organization_id == organization.id,
                    Chat.type == ChatType.EXTERNAL,
                    Chat.title == group_name,
                )
                chat_result = await db.execute(chat_stmt)
                chat = chat_result.scalar_one_or_none()
                if chat:
                    targets.append((chat.title, chat.id, chat.captain_connected_thread))
        else:
            for group_name in group_names:
                captain_stmt = select(ChatCaptain).where(
                    ChatCaptain.organization_id == organization.id,
                    ChatCaptain.chat_title == group_name,
                    ChatCaptain.connected_user_id.is_not(None),
                    ChatCaptain.is_bot_blocked.is_(False),
                )
                captain_result = await db.execute(captain_stmt)
                captain = captain_result.scalar_one_or_none()
                if captain and captain.connected_user_id:
                    targets.append(
                        (captain.chat_title, captain.connected_user_id, None)
                    )

        success: list[str] = []
        failed: list[tuple[str, str]] = []

        for name, chat_id, thread_id in targets:
            try:
                await send_message(
                    db,
                    message_to_send,
                    chat_id,
                    thread_id,
                    None,
                    MessageType.INFO,
                )
                success.append(name)
            except Exception as e:
                failed.append((name, str(e)))

        splitter = TelegramHTMLSplitter(send_func=callback.message.answer)

        await splitter.add("<b>📊 Звіт про розсилку</b>\n\n")
        await splitter.add(
            f"<b>Всього отримувачів:</b> {len(targets)}\n"
            f"<b>Успішно:</b> {len(success)}\n"
            f"<b>Помилки:</b> {len(failed)}\n\n"
        )

        if success:
            await splitter.add(f"<b>✅ Успішно надіслано ({len(success)}):</b>\n")
            for name in success:
                await splitter.add(f"• {html.escape(name)}\n")
            await splitter.add("\n")

        if failed:
            await splitter.add(f"<b>❌ Помилки ({len(failed)}):</b>\n")
            for name, error in failed:
                await splitter.add(
                    f"• {html.escape(name)}: <code>{html.escape(error)}</code>\n"
                )

        await splitter.flush()
        await edit_callback_message(callback, "✅ Розсилка завершена", answer=False)
    except Exception as e:
        logger.error(e)
        await edit_callback_message(
            callback,
            f"❌ Критична помилка під час розсилки:\n<code>{html.escape(str(e))}</code>",
            parse_mode="HTML",
        )
