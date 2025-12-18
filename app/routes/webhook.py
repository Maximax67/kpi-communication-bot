from typing import Dict

from aiogram import Bot
from aiogram.types import Update
from fastapi import (
    APIRouter,
    Depends,
    HTTPException,
    Header,
    Request,
    Response,
)
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.bot_cache import get_telegram_bot
from app.core.crypto import crypto
from app.core.enums import CryptoInfo
from app.core.exceptions import exception_handler
from app.core.limiter import limiter
from app.db.session import get_db

from bot.dispatcher import dp
from bot.root_bot import ROOT_BOT

router = APIRouter(prefix="/webhook", tags=["telegram"])


@router.post(
    "/{bot_id}",
    responses={
        400: {
            "description": "Invalid update content",
            "content": {
                "application/json": {"example": {"detail": "Invalid update content"}}
            },
        },
        401: {
            "description": "Invalid Telegram token",
            "content": {
                "application/json": {"example": {"detail": "Invalid Telegram token"}}
            },
        },
    },
)
@limiter.limit("60/minute")
async def handle_update(
    bot_id: int,
    request: Request,
    response: Response,
    x_telegram_token: str = Header(..., alias="X-Telegram-Bot-Api-Secret-Token"),
    db: AsyncSession = Depends(get_db),
) -> Response:
    bot = await get_telegram_bot(bot_id, db)
    if bot is None:
        raise HTTPException(status_code=401, detail="Invalid token")

    secret = crypto.decrypt_data(bot.secret, CryptoInfo.WEBHOOK_SECRET)
    if x_telegram_token != secret:
        raise HTTPException(status_code=401, detail="Invalid token")

    try:
        raw_update = await request.json()
        update = Update.model_validate(raw_update)
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

    token_stripped = crypto.decrypt_data(bot.token, CryptoInfo.BOT_TOKEN)
    token = f"{bot_id}:{token_stripped}"
    telegram_bot = Bot(token)

    try:
        message = update.message
        if message:
            message_info: Dict[str, str] = {
                "chat_id": str(message.chat.id),
                "message_thread_id": (
                    str(message.message_thread_id)
                    if message.message_thread_id
                    and message.chat.is_forum
                    and (
                        not message.reply_to_message
                        or not message.reply_to_message.forum_topic_created
                    )
                    else ""
                ),
            }

            user = message.from_user
            if user:
                message_info["user_id"] = str(user.id)
                message_info["full_name"] = user.full_name

                if user.username:
                    message_info["username"] = user.username

            request.state.message_info = message_info

        if bot_id == ROOT_BOT.id:
            await dp.feed_update(ROOT_BOT, update)
        else:
            await dp.feed_update(telegram_bot, update)
    except Exception as exc:
        await exception_handler(request, exc, telegram_bot)
    finally:
        await telegram_bot.session.close()

    return Response(status_code=200)
