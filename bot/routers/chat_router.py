from aiogram import F, Router
from aiogram.filters import Command

from bot.callback import ChatCallback, SpamCallback, ThreadCallback
from bot.handlers.chat.admin_commands import (
    confirm_chat_delete_handler,
    delete_chat_handler,
    delete_chat_tags_handler,
    delete_thread_tags_handler,
    disable_pin_chat_requests_handler,
    pin_chat_requests_handler,
    pin_thread_requests_handler,
    rename_chat_handler,
    chat_visibility_handler,
    change_chat_visibility_handler,
    set_chat_tags_handler,
    set_thread_handler,
    delete_thread_handler,
    rename_thread_handler,
    set_thread_tags_handler,
    thread_visibility_handler,
    change_thread_visibility_handler,
)
from bot.handlers.chat.captains_management import (
    captains_list_handler,
    confirm_spam_handler,
    spam_all_captains_handler,
    spam_all_groups_handler,
    spam_captains_handler,
    spam_groups_handler,
    update_captains_handler,
)
from bot.handlers.chat.user_commands import (
    chat_handler,
    members_handler,
    groups_handler,
    group_members_handler,
    threads_handler,
)


chat_router = Router()

# Member listing commands (available to all in internal chats)
chat_router.message.register(members_handler, Command("members"))
chat_router.message.register(groups_handler, Command("groups"))
chat_router.message.register(group_members_handler, Command("group_members"))
chat_router.message.register(chat_handler, Command("chat"))
chat_router.message.register(threads_handler, Command("threads"))

# Admin commands (requires chat admin)
chat_router.message.register(rename_chat_handler, Command("rename_chat"))
chat_router.message.register(chat_visibility_handler, Command("chat_visibility"))
chat_router.message.register(set_thread_handler, Command("set_thread"))
chat_router.message.register(delete_thread_handler, Command("delete_thread"))
chat_router.message.register(rename_thread_handler, Command("rename_thread"))
chat_router.message.register(thread_visibility_handler, Command("thread_visibility"))
chat_router.message.register(delete_chat_handler, Command("delete_chat"))

chat_router.message.register(pin_chat_requests_handler, Command("pin_chat_requests"))
chat_router.message.register(
    disable_pin_chat_requests_handler, Command("disable_pin_chat_requests")
)
chat_router.message.register(
    pin_thread_requests_handler, Command("pin_thread_requests")
)
chat_router.message.register(
    disable_pin_chat_requests_handler, Command("disable_pin_thread_requests")
)

chat_router.message.register(set_chat_tags_handler, Command("set_chat_tags"))
chat_router.message.register(delete_chat_tags_handler, Command("delete_chat_tags"))
chat_router.message.register(set_thread_tags_handler, Command("set_thread_tags"))
chat_router.message.register(delete_thread_tags_handler, Command("delete_thread_tags"))

chat_router.callback_query.register(
    change_chat_visibility_handler,
    ChatCallback.filter(F.action.startswith("visibility_")),
)
chat_router.callback_query.register(
    change_thread_visibility_handler,
    ThreadCallback.filter(F.action.startswith("visibility_")),
)
chat_router.callback_query.register(
    confirm_chat_delete_handler,
    ChatCallback.filter(F.action == "confirm_delete_chat"),
)

chat_router.message.register(captains_list_handler, Command("captains_list"))
chat_router.message.register(update_captains_handler, Command("update_captains"))

chat_router.message.register(spam_groups_handler, Command("spam_groups"))
chat_router.message.register(spam_captains_handler, Command("spam_captains"))
chat_router.message.register(spam_all_groups_handler, Command("spam_all_groups"))
chat_router.message.register(spam_all_captains_handler, Command("spam_all_captains"))

chat_router.callback_query.register(
    confirm_spam_handler,
    SpamCallback.filter(F.action == "spam"),
)
