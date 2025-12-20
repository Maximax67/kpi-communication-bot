from aiogram.types import Message

from app.db.models.organization import Organization
from bot.middlewares.organization import OrganizationCache
from bot.middlewares.db_session import LazyDbSession


async def set_greeting_handler(
    message: Message,
    organization: Organization,
    organization_cache: OrganizationCache,
    lazy_db: LazyDbSession,
) -> None:
    if not message.text or not message.from_user:
        return

    if message.chat.id != organization.admin_chat_id:
        await message.answer(
            "❌ Команда доступна для виконання лише з чату адміністраторів організації"
        )
        return

    command_parts = message.text.split(maxsplit=1)

    if len(command_parts) < 2:
        await message.answer("❌ Використання: /set_greeting Вітальне повідомлення")
        return

    new_greeting = command_parts[1].strip()

    if len(new_greeting) == 0:
        await message.answer("❌ Вітальне повідомлення не може бути порожнім!")
        return

    if len(new_greeting) > 1024:
        await message.answer(
            "❌ Вітальне повідомлення занадто довге! Максимум 1024 символи."
        )
        return

    if new_greeting == organization.greeting_message:
        await message.answer("❌ Нове вітальне повідомлення ідентичне з попереднім.")
        return

    old_greeintg = organization.greeting_message
    organization.greeting_message = new_greeting

    db = await lazy_db.get()
    await db.merge(organization)
    await db.commit()

    organization_cache.update(organization)

    if old_greeintg:
        await message.answer(
            f"✅ Вітальне повідомлення змінено\n\n{new_greeting}",
        )
        return

    await message.answer(
        f"✅ Вітальне повідомлення встановлено\n\n{new_greeting}",
    )


async def delete_greeting_handler(
    message: Message,
    organization: Organization,
    organization_cache: OrganizationCache,
    lazy_db: LazyDbSession,
) -> None:
    if not message.text or not message.from_user:
        return

    if message.chat.id != organization.admin_chat_id:
        await message.answer(
            "❌ Команда доступна для виконання лише з чату адміністраторів організації"
        )
        return

    if not organization.greeting_message:
        await message.answer("❌ Організація не має власного вітального повідомлення")
        return

    organization.greeting_message = None

    db = await lazy_db.get()
    await db.merge(organization)
    await db.commit()

    organization_cache.update(organization)

    await message.answer("✅ Власне вітальне повідомлення видалено")
