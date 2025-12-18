from aiogram import Bot
from app.core.settings import settings

ROOT_BOT = Bot(token=settings.ROOT_BOT_TOKEN.get_secret_value())
