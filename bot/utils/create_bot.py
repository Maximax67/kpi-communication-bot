from aiogram import Bot
from app.core.crypto import crypto
from app.core.enums import CryptoInfo
from app.db.models.telegram_bot import TelegramBot


def create_bot_from_db(bot: TelegramBot) -> Bot:
    token_stripped = crypto.decrypt_data(bot.token, CryptoInfo.BOT_TOKEN)
    token = f"{bot.id}:{token_stripped}"
    return Bot(token)
