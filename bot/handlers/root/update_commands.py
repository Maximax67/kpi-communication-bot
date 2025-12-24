import asyncio
from aiogram import Bot
from aiogram.types import Message
from sqlalchemy import select
from sqlalchemy.orm import selectinload, joinedload

from app.core.enums import ChatType
from app.core.logger import logger
from app.db.models.organization import Organization
from bot.middlewares.db_session import LazyDbSession
from bot.utils.get_bot import get_organization_bot
from bot.utils.set_bot_commands import (
    set_bot_commands_for_admin_chat,
    set_bot_commands_for_external_chat,
    set_bot_commands_for_internal_chat,
    set_bot_commands_for_private_chats,
)


async def update_commands_handler(message: Message, lazy_db: LazyDbSession) -> None:
    db = await lazy_db.get()
    stmt = (
        select(Organization)
        .options(joinedload(Organization.bot), selectinload(Organization.chats))
        .where(Organization.bot.has())
    )
    results_db = await db.execute(stmt)
    results = results_db.scalars().all()

    errors: list[dict[str, str]] = []
    success_count = 0
    total_orgs = len(results)

    waiting_message = await message.answer(
        f"⏳ Встановлення команд для {total_orgs} організацій... Це може зайняти деякий час."
    )

    for organization in results:
        bot: Bot | None = None
        org_errors: list[str] = []

        try:
            bot = get_organization_bot(organization)

            if organization.admin_chat_id:
                try:
                    await set_bot_commands_for_admin_chat(
                        bot,
                        organization.admin_chat_id,
                        organization.id == 0,
                    )
                except Exception as e:
                    error_msg = (
                        f"Admin chat (ID: {organization.admin_chat_id}): {str(e)}"
                    )
                    org_errors.append(error_msg)
                    logger.error(
                        f"Failed to set admin chat commands for {organization.title}: {e}"
                    )

            for chat in organization.chats:
                try:
                    if chat.type == ChatType.INTERNAL:
                        try:
                            chat_info = await bot.get_chat(chat.id)
                            await set_bot_commands_for_internal_chat(
                                bot, chat.id, bool(chat_info.is_forum)
                            )
                        except Exception as e:
                            error_msg = f"Internal chat (ID: {chat.id}): {str(e)}"
                            org_errors.append(error_msg)
                            logger.error(
                                f"Failed to set internal chat commands for {organization.title}, chat {chat.id}: {e}"
                            )
                    else:
                        try:
                            await set_bot_commands_for_external_chat(bot, chat.id)
                        except Exception as e:
                            error_msg = f"External chat (ID: {chat.id}): {str(e)}"
                            org_errors.append(error_msg)
                            logger.error(
                                f"Failed to set external chat commands for {organization.title}, chat {chat.id}: {e}"
                            )

                    await asyncio.sleep(0.1)
                except Exception as e:
                    error_msg = f"Chat (ID: {chat.id}): {str(e)}"
                    org_errors.append(error_msg)
                    logger.error(
                        f"Unexpected error processing chat {chat.id} for {organization.title}: {e}"
                    )

            try:
                await set_bot_commands_for_private_chats(bot)
            except Exception as e:
                error_msg = f"Private chats: {str(e)}"
                org_errors.append(error_msg)
                logger.error(
                    f"Failed to set private chat commands for {organization.title}: {e}"
                )

            if org_errors:
                errors.append(
                    {
                        "organization": organization.title,
                        "errors": "\n  • ".join(org_errors),
                    }
                )
            else:
                success_count += 1

        except Exception as e:
            error_msg = f"Critical error: {str(e)}"
            errors.append({"organization": organization.title, "errors": error_msg})
            logger.error(
                f"Critical error processing organization {organization.title}: {e}"
            )
        finally:
            if bot:
                try:
                    await bot.session.close()
                except Exception as e:
                    logger.error(
                        f"Error closing bot session for {organization.title}: {e}"
                    )

    result_message = (
        f"✅ Команди встановлено для {success_count}/{total_orgs} організацій"
    )

    if errors:
        result_message += "\n\n❌ Помилки:\n\n"
        for error in errors:
            result_message += f"🏢 {error['organization']}:\n  • {error['errors']}\n\n"

    if len(result_message) > 4000:
        await waiting_message.edit_text(
            f"✅ Команди встановлено для {success_count}/{total_orgs} організацій\n\n⚠️ Повний список помилок надіслано окремими повідомленнями."
        )

        error_text = "❌ Помилки:\n\n"
        for error in errors:
            error_chunk = f"🏢 {error['organization']}:\n  • {error['errors']}\n\n"
            if len(error_text + error_chunk) > 4000:
                await message.answer(error_text)
                error_text = "❌ Помилки (продовження):\n\n" + error_chunk
            else:
                error_text += error_chunk

        if error_text:
            await message.answer(error_text)
    else:
        await waiting_message.edit_text(result_message)
