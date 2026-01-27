from aiogram import F, Router
from aiogram.filters import Command

from bot.handlers.admin.ban import (
    ban_list_handler,
    ban_user_handler,
    unban_user_handler,
)
from bot.handlers.admin.chat_delete import (
    confirm_selected_chat_delete_handler,
    delete_seleted_chat_handler,
    select_chat_delete_handler,
)
from bot.handlers.admin.greeting_message import (
    delete_greeting_handler,
    set_greeting_handler,
)
from bot.handlers.admin.organization_settings import (
    confirm_delete_handler,
    request_delete_handler,
    settings_handler,
    toggle_daily_notifications_handler,
    toggle_messages_handler,
    toggle_privacy_handler,
)
from bot.handlers.admin.rename_organization import rename_organization_handler
from bot.handlers.admin.set_admin_chat import set_admin_chat_handler
from bot.handlers.admin.bot_management import (
    set_bot_handler,
    delete_bot_handler,
)
from bot.callback import ChatCallback, OrganizationCallback
from bot.handlers.admin.captain_spreadsheet import (
    delete_captains_spreadsheet_handler,
    set_captains_spreadsheet_handler,
)


admin_router = Router()

admin_router.message.register(settings_handler, Command("settings"))

admin_router.callback_query.register(
    toggle_privacy_handler,
    OrganizationCallback.filter(F.action == "toggle_privacy"),
)
admin_router.callback_query.register(
    toggle_messages_handler,
    OrganizationCallback.filter(F.action == "toggle_messages"),
)
admin_router.callback_query.register(
    toggle_daily_notifications_handler,
    OrganizationCallback.filter(F.action == "toggle_daily_notifications"),
)
admin_router.callback_query.register(
    request_delete_handler,
    OrganizationCallback.filter(F.action == "request_delete"),
)
admin_router.callback_query.register(
    confirm_delete_handler,
    OrganizationCallback.filter(F.action == "confirm_delete"),
)

admin_router.message.register(set_greeting_handler, Command("set_greeting"))
admin_router.message.register(delete_greeting_handler, Command("delete_greeting"))

admin_router.message.register(
    rename_organization_handler, Command("rename_organization")
)
admin_router.message.register(set_admin_chat_handler, Command("set_admin_chat"))
admin_router.message.register(set_bot_handler, Command("set_bot"))
admin_router.message.register(delete_bot_handler, Command("delete_bot"))

admin_router.message.register(
    delete_seleted_chat_handler, Command("delete_selected_chat")
)
admin_router.callback_query.register(
    select_chat_delete_handler, ChatCallback.filter(F.action == "select_delete")
)
admin_router.callback_query.register(
    confirm_selected_chat_delete_handler,
    ChatCallback.filter(F.action == "confirm_delete_admin"),
)

admin_router.message.register(ban_user_handler, Command("ban"))
admin_router.message.register(unban_user_handler, Command("unban"))
admin_router.message.register(ban_list_handler, Command("ban_list"))

admin_router.message.register(
    set_captains_spreadsheet_handler, Command("set_captains_spreadsheet")
)
admin_router.message.register(
    delete_captains_spreadsheet_handler, Command("delete_captains_spreadsheet")
)
