import secrets
from aiogram import Bot
from sqlalchemy import exists, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.settings import settings
from app.core.crypto import crypto
from app.core.enums import CryptoInfo
from app.core.logger import logger
from app.db.session import async_session
from app.db.models.organization import Organization
from app.db.models.telegram_bot import TelegramBot

from bot.root_bot import ROOT_BOT
from bot.utils.set_bot_commands import (
    set_bot_commands_for_admin_chat,
    set_bot_commands_for_private_chats,
)
from bot.utils.set_webhook import get_webhook_url, init_webhook


async def setup_webhook(bot: Bot, secret: str) -> None:
    try:
        await init_webhook(bot, secret)
    except Exception as e:
        logger.error(e)
        raise


async def setup_root_bot(db: AsyncSession, bot_token: str) -> None:
    try:
        bot = Bot(bot_token)
        me = await bot.get_me()
    except Exception as e:
        logger.error(e)
        raise ValueError("Invalid bot token")

    bot_id = me.id

    existing = await db.scalar(select(TelegramBot).where(TelegramBot.id == bot_id))

    token_encrypted = crypto.encrypt_data(
        bot_token.split(":", 1)[1],
        CryptoInfo.BOT_TOKEN,
    )

    if existing is None:
        secret = secrets.token_urlsafe(32)
        db.add(
            TelegramBot(
                id=bot_id,
                token=token_encrypted,
                username=me.username,
                secret=crypto.encrypt_data(secret, CryptoInfo.WEBHOOK_SECRET),
                owner=0,
                organization_id=0,
            )
        )

    await setup_webhook(bot, secret)
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
