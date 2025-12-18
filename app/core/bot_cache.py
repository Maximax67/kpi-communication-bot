from cachetools import TTLCache
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.telegram_bot import TelegramBot

telegram_bot_cache: TTLCache[int, TelegramBot] = TTLCache(maxsize=100, ttl=300)


async def get_telegram_bot(bot_id: int, db: AsyncSession) -> TelegramBot | None:
    bot = telegram_bot_cache.get(bot_id)
    if bot is not None:
        return bot

    q = await db.execute(select(TelegramBot).where(TelegramBot.id == bot_id))
    bot = q.scalar_one_or_none()

    if bot:
        telegram_bot_cache[bot_id] = bot

    return bot


def remove_telegram_bot(bot_id: int) -> None:
    telegram_bot_cache.pop(bot_id)
