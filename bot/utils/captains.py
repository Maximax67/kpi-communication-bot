from collections import defaultdict
import html
from io import BytesIO
from aiogram import Bot
import pandas as pd
from sqlalchemy import delete, insert, or_, select
from sqlalchemy.orm import joinedload
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.crypto import crypto
from app.core.settings import settings
from app.core.logger import logger
from app.core.constants import USERNAME_REGEX
from app.core.enums import CryptoInfo
from app.core.google_drive import download_file
from app.db.models.captain_spreadsheet import CaptainSpreadsheet
from app.db.models.chat_captain import ChatCaptain
from app.db.models.organization import Organization
from bot.root_bot import ROOT_BOT
from bot.utils.spreadsheet import excel_cols_to_positions


async def get_captain(
    db: AsyncSession,
    organization_id: int,
    user_id: int | None = None,
    username: str | None = None,
    load_chat: bool = False,
) -> ChatCaptain | None:
    if user_id is None and username is None:
        raise ValueError("At least one param should be provided: user_id, username")

    conditions = [ChatCaptain.organization_id == organization_id]
    or_conditions = []

    if user_id is not None:
        or_conditions.append(ChatCaptain.connected_user_id == user_id)

    if username is not None:
        or_conditions.append(ChatCaptain.validated_username == username)

    if or_conditions:
        if len(or_conditions) == 1:
            conditions.append(or_conditions[0])
        else:
            conditions.append(or_(*or_conditions))

    q = select(ChatCaptain).where(*conditions).limit(1)

    if load_chat:
        q = q.options(joinedload(ChatCaptain.chat))

    result = await db.execute(q)

    return result.scalar_one_or_none()


async def update_captains_single_spreadhseet(
    db: AsyncSession,
    spreadsheet: CaptainSpreadsheet,
    current_captains: dict[str, ChatCaptain],
    organization: Organization,
) -> None:
    if organization.bot is None:
        raise ValueError("Organization without bot")

    if organization.admin_chat_id is None:
        raise ValueError("Organization without admin_chat_id")

    config_content = BytesIO()
    download_file(
        spreadsheet.spreadsheet_id,
        config_content,
        export_mime_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )

    config_content.seek(0)
    file = pd.ExcelFile(config_content)
    df = pd.read_excel(file, spreadsheet.sheet_name, engine="openpyxl")
    file.close()

    if isinstance(df, dict):
        df = next(iter(df.values()))

    rows_min = spreadsheet.rows_range_min
    rows_max = spreadsheet.rows_range_max

    row_slice = slice(
        rows_min if rows_min is not None else None,
        rows_max + 1 if rows_max is not None else None,
    )

    col_positions = excel_cols_to_positions(
        [spreadsheet.chat_title_column, spreadsheet.username_column]
    )
    two_cols = df.iloc[row_slice, col_positions].dropna()

    new_captains: list[ChatCaptain] = []
    removed_captains: list[ChatCaptain] = []
    changed_captains: list[ChatCaptain] = []
    remind_changed_username: list[ChatCaptain] = []
    processed_chats: set[str] = set()
    duplicated_chats: list[str] = []

    for title, username in two_cols.itertuples(index=False, name=None):
        title = title.strip()
        if len(title) > 32:
            continue

        if title in processed_chats:
            duplicated_chats.append(title)
            continue

        username = username.strip()
        match = USERNAME_REGEX.fullmatch(username)
        if not match:
            continue

        username = match.group("username")
        processed_chats.add(title)
        existing_captain = current_captains.get(title)
        if existing_captain:
            del current_captains[title]
            conn_user = existing_captain.connected_user
            if conn_user:
                if conn_user.username != username:
                    if existing_captain.validated_username == username:
                        remind_changed_username.append(existing_captain)
                        continue

                    existing_captain.connected_user_id = None
                    existing_captain.validated_username = username
                    existing_captain.is_bot_blocked = True

                    changed_captains.append(existing_captain)
            elif existing_captain.validated_username != username:
                existing_captain.validated_username = username
                changed_captains.append(existing_captain)

            continue

        new_captain = ChatCaptain(
            organization_id=organization.id,
            validated_username=username,
            chat_title=title,
        )
        new_captains.append(new_captain)

    for captain in current_captains.values():
        removed_captains.append(captain)

    if (
        new_captains
        or removed_captains
        or changed_captains
        or remind_changed_username
        or duplicated_chats
    ):
        if removed_captains:
            await db.execute(
                delete(ChatCaptain).where(
                    ChatCaptain.id.in_([c.id for c in removed_captains])
                )
            )

        if new_captains:
            await db.execute(
                insert(ChatCaptain),
                [
                    {
                        "organization_id": c.organization_id,
                        "validated_username": c.validated_username,
                        "chat_title": c.chat_title,
                    }
                    for c in new_captains
                ],
            )

        bot_token_encrypted = organization.bot.token
        bot_token_stripped = crypto.decrypt_data(
            bot_token_encrypted, CryptoInfo.BOT_TOKEN
        )
        bot_token = f"{organization.bot.id}:{bot_token_stripped}"
        telegram_bot = Bot(bot_token)

        admin_text = "<b>Інформація про старост оновлена</b>"

        if remind_changed_username:
            admin_text += "\n\n<b>Самостійна зміна тегу</b>"
            for captain in remind_changed_username:
                tag = (
                    f"@{html.escape(captain.connected_user.username)}"
                    if captain.connected_user and captain.connected_user.username
                    else "без юзернейму"
                )
                admin_text += f"\n{html.escape(captain.chat_title)} - {tag}"

        if new_captains:
            admin_text += f"\n\n<b>Нові старости ({len(new_captains)}):</b>"
            for captain in new_captains:
                tag = f"@{html.escape(captain.validated_username)}"
                admin_text += f"\n{html.escape(captain.chat_title)} - {tag}"

        if changed_captains:
            admin_text += f"\n\n<b>Змінено старост ({len(changed_captains)}):</b>"
            for captain in changed_captains:
                tag = (
                    f"@{html.escape(captain.validated_username)}"
                    if captain.validated_username
                    else "без юзернейму"
                )
                admin_text += f"\n{html.escape(captain.chat_title)} - {tag}"

        if removed_captains:
            admin_text += f"\n\n<b>Видалено старост ({len(removed_captains)}):</b>"
            for captain in removed_captains:
                tag = (
                    f"@{html.escape(captain.validated_username)}"
                    if captain.validated_username
                    else "без юзернейму"
                )
                admin_text += f"\n{html.escape(captain.chat_title)} - {tag}"

        if duplicated_chats:
            admin_text += (
                f"\n\nЗнайдено дублікати наступних чатів: {', '.join(duplicated_chats)}. "
                "Для них старостою вважається лише перше знайдене значення в таблиці."
            )

        try:
            await telegram_bot.send_message(
                organization.admin_chat_id,
                admin_text,
                message_thread_id=organization.admin_chat_thread_id,
                parse_mode="HTML",
            )
        except Exception as e:
            logger.error(e)
            await ROOT_BOT.send_message(
                settings.ROOT_ADMIN_CHAT_ID,
                f"Не вдалось надіслати оновлену інформацію про старост для {organization.title}: {e}",
                message_thread_id=settings.ROOT_ADMIN_ERRORS_THREAD_ID,
            )
            await ROOT_BOT.send_message(
                settings.ROOT_ADMIN_CHAT_ID,
                admin_text,
                message_thread_id=settings.ROOT_ADMIN_ERRORS_THREAD_ID,
                parse_mode="HTML",
            )
        finally:
            try:
                await telegram_bot.session.close()
            except Exception:
                pass

        await db.commit()


async def update_captains_spreadsheet_info(db: AsyncSession) -> None:
    q = await db.execute(
        select(CaptainSpreadsheet).options(
            joinedload(CaptainSpreadsheet.organization).joinedload(Organization.bot),
        )
    )
    spreadsheets = q.scalars().all()

    q2 = await db.execute(
        select(ChatCaptain).options(joinedload(ChatCaptain.connected_user))
    )
    captains = q2.scalars().all()

    organization_captains: dict[int, dict[str, ChatCaptain]] = defaultdict(dict)
    for captain in captains:
        organization_captains[captain.organization_id][captain.chat_title] = captain

    for spreadsheet in spreadsheets:
        bot = spreadsheet.organization.bot
        admin_chat_id = spreadsheet.organization.admin_chat_id
        if not bot or not admin_chat_id:
            continue

        try:
            current_captains = organization_captains.get(
                spreadsheet.organization_id, {}
            )
            await update_captains_single_spreadhseet(
                db, spreadsheet, current_captains, spreadsheet.organization
            )
        except Exception as e:
            logger.error(e)
            org_title = spreadsheet.organization.title
            await db.rollback()
            await ROOT_BOT.send_message(
                settings.ROOT_ADMIN_CHAT_ID,
                f"Не вдалось оновити старост для <b>{html.escape(org_title)}</b>!\n\n<code>{html.escape(str(e))}</code>",
                message_thread_id=settings.ROOT_ADMIN_ERRORS_THREAD_ID,
                parse_mode="HTML",
            )


async def update_captains(db: AsyncSession) -> None:
    logger.info("Updating captains")
    await update_captains_spreadsheet_info(db)
    logger.info("Captains updated")
