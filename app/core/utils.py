import asyncio
from collections import defaultdict
import html
from io import BytesIO
import secrets

from aiogram import Bot
import pandas as pd
from sqlalchemy import delete, exists, select
from sqlalchemy.orm import joinedload
from sqlalchemy.ext.asyncio import AsyncSession
from openpyxl.utils import column_index_from_string

from app.core.constants import USERNAME_REGEX
from app.core.google_drive import download_file
from app.core.settings import settings
from app.core.crypto import crypto
from app.core.enums import CryptoInfo
from app.core.logger import logger
from app.db.models.captain_spreadsheet import CaptainSpreadsheet
from app.db.models.chat_captain import ChatCaptain
from app.db.models.organization import Organization
from app.db.session import async_session
from app.db.models.telegram_bot import TelegramBot
from bot.utils.set_bot_commands import (
    set_bot_commands_for_admin_chat,
    set_bot_commands_for_private_chats,
)
from bot.utils.set_webhook import get_webhook_url, init_webhook
from bot.root_bot import ROOT_BOT


async def setup_root_bot(db: AsyncSession, bot_token: str) -> None:
    try:
        bot = Bot(bot_token)
        me = await bot.get_me()
    except Exception as e:
        logger.error(e)
        raise ValueError("Invalid bot token")

    bot_id = me.id

    q = await db.execute(select(TelegramBot).where(TelegramBot.id == bot_id))
    existing_bot: TelegramBot | None = q.scalar_one_or_none()

    token_stripped = bot_token.split(":", 1)[1]
    token_encrypted = crypto.encrypt_data(token_stripped, CryptoInfo.BOT_TOKEN)

    if existing_bot is None:
        secret_token = secrets.token_urlsafe(32)
        secret_token_encrypted = crypto.encrypt_data(
            secret_token, CryptoInfo.WEBHOOK_SECRET
        )

        new_bot = TelegramBot(
            id=bot_id,
            token=token_encrypted,
            username=me.username,
            secret=secret_token_encrypted,
            owner=0,
            organization_id=0,
        )
        db.add(new_bot)

    await init_webhook(bot, secret_token)
    await bot.session.close()

    await db.commit()


async def update_webhooks(db: AsyncSession) -> None:
    q = await db.execute(select(TelegramBot))
    bots = q.scalars().all()

    for bot in bots:
        tg_bot: Bot | None = None

        try:
            token_decrypted = crypto.decrypt_data(bot.token, CryptoInfo.BOT_TOKEN)
            secret_token = crypto.decrypt_data(bot.secret, CryptoInfo.WEBHOOK_SECRET)
            token = f"{bot.id}:{token_decrypted}"
            tg_bot = Bot(token)
            await init_webhook(tg_bot, secret_token)
            await set_bot_commands_for_private_chats(tg_bot)
        except Exception as e:
            logger.error(e)
        finally:
            if tg_bot:
                await tg_bot.session.close()


async def startup_bots_setup() -> None:
    async with async_session() as db:
        async with db.begin():
            await update_webhooks(db)

            bot_id = ROOT_BOT.id
            root_webhook = await ROOT_BOT.get_webhook_info()
            if root_webhook.url != get_webhook_url(bot_id):
                await setup_root_bot(db, settings.ROOT_BOT_TOKEN.get_secret_value())
                return

            await set_bot_commands_for_admin_chat(
                ROOT_BOT, settings.ROOT_ADMIN_CHAT_ID, True
            )

            root_bot_exists = await db.execute(
                select(exists().where(TelegramBot.id == bot_id))
            )

            if not root_bot_exists.scalar():
                await setup_root_bot(db, settings.ROOT_BOT_TOKEN.get_secret_value())


async def setup_root_organization() -> None:
    async with async_session() as db:
        async with db.begin():
            root_org_exists = await db.execute(
                select(exists().where(Organization.id == 0))
            )

            if not root_org_exists.scalar():
                db.add(
                    Organization(
                        id=0,
                        title=settings.ROOT_ORGANIZATION_TITLE,
                        admin_chat_id=settings.ROOT_ADMIN_CHAT_ID,
                        admin_chat_thread_id=settings.ROOT_ADMIN_MESSAGES_THREAD_ID,
                        is_admins_accept_messages=settings.ROOT_ORGANIZATION_ACCEPT_MESSAGES,
                        is_verified=True,
                        is_private=settings.ROOT_ORGANIZATION_PRIVATE,
                        owner=0,
                    )
                )
                await db.commit()


def excel_cols_to_positions(cols: list[str]) -> list[int]:
    return [column_index_from_string(c) - 1 for c in cols]


async def update_captains_spreadsheet_info(db: AsyncSession) -> None:
    q = await db.execute(
        select(CaptainSpreadsheet).options(
            joinedload(CaptainSpreadsheet.organization, Organization.bot)
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

            current_captains = organization_captains.get(
                spreadsheet.organization_id, {}
            )

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
                    if conn_user and conn_user.username != username:
                        if existing_captain.validated_username == username:
                            remind_changed_username.append(existing_captain)
                            continue

                        existing_captain.connected_user_id = None
                        existing_captain.validated_username = username
                        changed_captains.append(existing_captain)

                    continue

                new_captain = ChatCaptain(
                    organization_id=spreadsheet.organization_id,
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
                    db.add_all(new_captains)

                bot_token_encrypted = bot.token
                bot_token_stripped = crypto.decrypt_data(
                    bot_token_encrypted, CryptoInfo.BOT_TOKEN
                )
                bot_token = f"{bot.id}:{bot_token_stripped}"
                telegram_bot = Bot(bot_token)

                admin_text = "<b>Інформація про старост оновлена</b>"

                if remind_changed_username:
                    admin_text += "\n\n<b>Самостійна зміна тегу</b>"
                    for captain in remind_changed_username:
                        tag = (
                            f"@{html.escape(captain.connected_user.username)}"
                            if captain.connected_user
                            and captain.connected_user.username
                            else "без юзернейму"
                        )
                        admin_text += f"\n{html.escape(captain.chat_title)} - {tag}"

                if new_captains:
                    admin_text += "\n\n<b>Нові старости</b>"
                    for captain in new_captains:
                        tag = f"@{html.escape(captain.validated_username)}"
                        admin_text += f"\n{html.escape(captain.chat_title)} - {tag}"

                if changed_captains:
                    admin_text += "\n\n<b>Змінено старост</b>"
                    for captain in changed_captains:
                        tag = (
                            f"@{html.escape(captain.validated_username)}"
                            if captain.validated_username
                            else "без юзернейму"
                        )
                        admin_text += f"\n{html.escape(captain.chat_title)} - {tag}"

                if removed_captains:
                    admin_text += "\n\n<b>Видалено старост</b>"
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
                        admin_chat_id,
                        admin_text,
                        message_thread_id=spreadsheet.organization.admin_chat_thread_id,
                        parse_mode="HTML",
                    )
                except Exception as e:
                    logger.error(e)
                    await ROOT_BOT.send_message(
                        settings.ROOT_ADMIN_CHAT_ID,
                        f"Не вдалось надіслати оновлену інформацію про старост для {spreadsheet.organization.title}: {e}",
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
        except Exception as e:
            logger.error(e)
            await db.rollback()
            await ROOT_BOT.send_message(
                settings.ROOT_ADMIN_CHAT_ID,
                f"Не вдалось оновити старост для {spreadsheet.organization.title}: {e}",
                message_thread_id=settings.ROOT_ADMIN_ERRORS_THREAD_ID,
            )


async def update_captains(db: AsyncSession) -> None:
    logger.info("Updating captains")
    await update_captains_spreadsheet_info(db)
    logger.info("Captains updated")


async def periodic_data_update(interval_seconds: int = 43200) -> None:
    while True:
        try:
            async with async_session() as db:
                async with db.begin():
                    await update_captains(db)
        except Exception:
            pass

        await asyncio.sleep(interval_seconds)
