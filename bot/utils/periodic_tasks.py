import asyncio
from datetime import datetime, timezone
from app.db.session import async_session
from app.core.logger import logger
from app.core.settings import settings

from bot.handlers.request.pending_handler import send_all_daily_pending_notifications
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


async def daily_pending_notifications_task() -> None:
    while True:
        try:
            now = datetime.now(timezone.utc)
            target_hour = settings.DAILY_PENDING_NOTIFICATION_HOUR

            next_run = now.replace(hour=target_hour, minute=0, second=0, microsecond=0)

            if now >= next_run:
                next_run = next_run.replace(day=next_run.day + 1)

            seconds_until_run = (next_run - now).total_seconds()

            logger.info(
                f"Next daily pending notification scheduled at {next_run} UTC ({seconds_until_run:.0f} seconds)"
            )

            await asyncio.sleep(seconds_until_run)

            logger.info("Sending daily pending notifications")
            async with async_session() as db:
                async with db.begin():
                    await send_all_daily_pending_notifications(db)
            logger.info("Daily pending notifications sent successfully")

        except Exception as e:
            logger.error(f"Error in daily pending notifications task: {e}")
            await asyncio.sleep(3600)
