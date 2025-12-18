import html
import traceback

from aiogram import Bot
from aiogram.types import LinkPreviewOptions
from fastapi import Request, Response

from app.core.settings import settings
from app.core.logger import logger
from bot.root_bot import ROOT_BOT
from bot.utils.message_splitter import TelegramHTMLSplitter


async def exception_handler(request: Request, exc: Exception, bot: Bot) -> Response:
    logger.error(exc)

    tb_lines = traceback.format_exception(type(exc), exc, exc.__traceback__)
    filtered_lines = [line for line in tb_lines if "app" in line or "bot" in line]
    formatted_tb = "".join(filtered_lines) or tb_lines[-1]

    chat_id_str: str | None = None

    try:
        message_info: dict[str, str] = request.state.message_info
        chat_id_str = message_info.get("chat_id")
        user_id_str = message_info.get("user_id")
        full_name = message_info.get("full_name")
        username = message_info.get("username")
        message_thread_id_str = message_info.get("message_thread_id")

        footer = f"<code>{chat_id_str}</code>"
        if user_id_str:
            footer += f" | <code>{user_id_str}</code> | "

            if username:
                footer += f"<a href='https://t.me/{username}'>{full_name}</a>"
            else:
                footer += (
                    f"<code>{html.escape(full_name) if full_name else "None"}</code>"
                )
    except AttributeError:
        footer = ""

    try:
        splitter = TelegramHTMLSplitter(
            lambda x, parse_mode: ROOT_BOT.send_message(
                text=x,
                chat_id=settings.ROOT_ADMIN_CHAT_ID,
                message_thread_id=settings.ROOT_ADMIN_ERRORS_THREAD_ID,
                parse_mode=parse_mode,
                link_preview_options=LinkPreviewOptions(is_disabled=True),
            )
        )

        await splitter.add("🚨 <b>Error Alert</b> 🚨\n\n")
        await splitter.add(html.escape(str(exc)))
        await splitter.add(
            f"\n\n<pre>Short Traceback:\n{html.escape(formatted_tb)}</pre>"
        )
        await splitter.add(footer)
        await splitter.flush()

        if chat_id_str:
            chat_id = int(chat_id_str)
            if chat_id != settings.ROOT_ADMIN_CHAT_ID:
                await bot.send_message(
                    chat_id=chat_id,
                    text="Упс. Сталася помилка 🫠. Розробник отримав сповіщення про неї та постарається виправити баг",
                    message_thread_id=(
                        int(message_thread_id_str) if message_thread_id_str else None
                    ),
                )
    except Exception as e:
        logger.error(e)

    return Response(status_code=500)
