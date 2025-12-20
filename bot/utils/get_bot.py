from aiogram import Bot

from app.core.crypto import crypto
from app.core.enums import CryptoInfo
from app.db.models.organization import Organization


def get_organization_bot(organization: Organization) -> Bot:
    if not organization.bot:
        raise ValueError("Organization without bot")

    token_stripped = crypto.decrypt_data(organization.bot.token, CryptoInfo.BOT_TOKEN)
    token = f"{organization.bot.id}:{token_stripped}"

    return Bot(token)
