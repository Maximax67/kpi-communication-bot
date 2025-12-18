from urllib.parse import urljoin
from aiogram import Bot

from app.core.settings import settings


def get_webhook_url(bot_id: int) -> str:
    return urljoin(str(settings.API_URL), f"{settings.API_PREFIX}/webhook/{bot_id}")


async def init_webhook(bot: Bot, secret_token: str) -> None:
    webhook_url = get_webhook_url(bot.id)

    await bot.set_webhook(
        webhook_url,
        secret_token=secret_token,
        allowed_updates=[
            "message",
            "edited_message",
            "callback_query",
            "chat_member",
            "my_chat_member",
        ],
    )
