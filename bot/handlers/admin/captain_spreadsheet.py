import html
from aiogram.types import Message
from sqlalchemy import delete, select
from sqlalchemy.orm import joinedload

from app.core.constants import COLUMN_REGEX, RANGE_REGEX, SPREADSHEET_URL_REGEX
from app.core.enums import ChatType
from app.core.logger import logger
from app.db.models.captain_spreadsheet import CaptainSpreadsheet
from app.db.models.chat import Chat
from app.db.models.chat_captain import ChatCaptain
from app.db.models.organization import Organization
from bot.middlewares.db_session import LazyDbSession
from bot.utils.captains import update_captains_single_spreadhseet


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
        last_space_idx = remaining.rfind(" ")
        if last_space_idx != -1:
            potential_range = remaining[last_space_idx + 1 :].strip()
            range_match = RANGE_REGEX.match(potential_range)
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

                sheet_name = remaining[:last_space_idx].strip() or None
            else:
                sheet_name = remaining
        else:
            range_match = RANGE_REGEX.match(remaining)
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
            else:
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

    await message.answer(
        f"✅ Таблицю старост успішно {action}!\n\n"
        f"<b>ID таблиці:</b> <code>{html.escape(spreadsheet_id)}</code>\n"
        f"<b>Колонка назви чату:</b> {html.escape(chat_column)}\n"
        f"<b>Колонка username:</b> {html.escape(username_column)}\n"
        + (f"<b>Назва аркуша:</b> {html.escape(sheet_name)}\n" if sheet_name else "")
        + (
            f"<b>Діапазон рядків:</b> {rows_range_min}-{rows_range_max}\n"
            if rows_range_min and rows_range_max
            else ""
        ),
        parse_mode="HTML",
    )

    try:
        captains_stmt = (
            select(ChatCaptain)
            .options(joinedload(ChatCaptain.connected_user))
            .where(ChatCaptain.organization_id == organization.id)
        )
        captains_result = await db.execute(captains_stmt)
        captains = captains_result.scalars().all()

        organization_captains: dict[str, ChatCaptain] = {}
        for captain in captains:
            organization_captains[captain.chat_title] = captain

        await update_captains_single_spreadhseet(
            db,
            new_spreadsheet,
            organization_captains,
            organization,
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
