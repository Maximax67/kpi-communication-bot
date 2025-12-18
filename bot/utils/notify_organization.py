from aiogram import Bot
from app.core.crypto import crypto
from app.core.enums import CryptoInfo
from app.db.models.organization import Organization
from bot.root_bot import ROOT_BOT


async def notify_organization(
    organization: Organization,
    text: str,
    delete_webhook: bool = False,
    parse_mode: str | None = None,
) -> None:
    org_bot = organization.bot
    if org_bot:
        token_decrypted = crypto.decrypt_data(org_bot.token, CryptoInfo.BOT_TOKEN)
        token = f"{org_bot.id}:{token_decrypted}"
        tg_bot = Bot(token)

        try:
            if organization.admin_chat_id:
                await tg_bot.send_message(
                    organization.admin_chat_id,
                    text,
                    message_thread_id=organization.admin_chat_thread_id,
                    parse_mode=parse_mode,
                )
            else:
                await tg_bot.send_message(
                    organization.owner, text, parse_mode=parse_mode
                )
        except Exception:
            pass

        if delete_webhook:
            try:
                await tg_bot.delete_webhook(drop_pending_updates=True)
            except Exception:
                pass

        try:
            await tg_bot.session.close()
        except Exception:
            pass

        return

    try:
        if organization.admin_chat_id:
            await ROOT_BOT.send_message(
                organization.admin_chat_id,
                text,
                message_thread_id=organization.admin_chat_thread_id,
                parse_mode=parse_mode,
            )
        else:
            await ROOT_BOT.send_message(organization.owner, text)
    except Exception:
        pass
