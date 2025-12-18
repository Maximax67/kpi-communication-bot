from aiogram import F, Router
from aiogram.enums import ChatMemberStatus
from aiogram.filters import CommandStart, Command, StateFilter

from bot.handlers.root.create_organization import (
    create_organization_handler,
    process_organization_description,
    process_organization_name,
)
from bot.handlers.user.bot_added import bot_added_handler
from bot.handlers.user.bot_removed import bot_removed_handler
from bot.handlers.user.migrate import migrate_handler
from bot.handlers.user.start import start_handler
from bot.handlers.user.verify import verify_handler
from bot.states import CreateOrganizationStates


user_router = Router()
user_router.message.register(start_handler, CommandStart())
user_router.message.register(verify_handler, Command("verify"))
user_router.message.register(migrate_handler, Command("migrate"))

user_router.message.register(
    create_organization_handler, Command("create_organization")
)
user_router.message.register(
    process_organization_name, StateFilter(CreateOrganizationStates.waiting_for_name)
)
user_router.message.register(
    process_organization_description,
    StateFilter(CreateOrganizationStates.waiting_for_description),
)

user_router.my_chat_member.register(
    bot_added_handler,
    (F.old_chat_member.status.in_({ChatMemberStatus.LEFT, ChatMemberStatus.KICKED}))
    & (
        F.new_chat_member.status.in_(
            {
                ChatMemberStatus.MEMBER,
                ChatMemberStatus.ADMINISTRATOR,
                ChatMemberStatus.RESTRICTED,
            }
        )
    ),
)

user_router.my_chat_member.register(
    bot_removed_handler,
    (
        F.old_chat_member.status.in_(
            {
                ChatMemberStatus.MEMBER,
                ChatMemberStatus.ADMINISTRATOR,
                ChatMemberStatus.RESTRICTED,
            }
        )
    )
    & (F.new_chat_member.status.in_({ChatMemberStatus.LEFT, ChatMemberStatus.KICKED})),
)
