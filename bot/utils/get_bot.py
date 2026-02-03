from aiogram import Bot

from app.core.crypto import crypto
from app.core.enums import CryptoInfo
from app.db.models.organization import Organization
from app.db.models.telegram_bot import TelegramBot


def get_bot(bot: TelegramBot) -> Bot:
    token_stripped = crypto.decrypt_data(bot.token, CryptoInfo.BOT_TOKEN)
    token = f"{bot.id}:{token_stripped}"

    return Bot(token)


def get_organization_bot(organization: Organization) -> Bot:
    if not organization.bot:
        raise ValueError("Organization without bot")

    return get_bot(organization.bot)
