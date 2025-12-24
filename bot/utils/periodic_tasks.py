import asyncio
from app.db.session import async_session
from app.core.logger import logger
from bot.utils.captains import update_captains


async def periodic_data_update(interval_seconds: int = 43200) -> None:
    while True:
        try:
            async with async_session() as db:
                async with db.begin():
                    await update_captains(db)
        except Exception as e:
            logger.error(e)

        await asyncio.sleep(interval_seconds)
