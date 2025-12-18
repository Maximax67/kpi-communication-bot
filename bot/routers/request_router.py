from aiogram import Router, F
from aiogram.filters import Command

from bot.handlers.request.message_handler import message_handler
from bot.handlers.request.send_handler import (
    select_admin_chat_handler,
    select_chat_handler,
    select_organization_handler,
    select_thread_handler,
    send_handler,
    send_task_handler,
)
from bot.handlers.request.status_handler import request_status_handler
from bot.handlers.request.pending_handler import pending_handler, pending_chat_handler
from bot.callback import MessageCallback


request_router = Router()

request_router.message.register(send_handler, Command("send"))
request_router.message.register(send_task_handler, Command("send_task"))

request_router.callback_query.register(
    select_organization_handler, MessageCallback.filter(F.action == "select_org")
)
request_router.callback_query.register(
    select_admin_chat_handler, MessageCallback.filter(F.action == "select_admin_chat")
)
request_router.callback_query.register(
    select_chat_handler, MessageCallback.filter(F.action == "select_chat")
)
request_router.callback_query.register(
    select_thread_handler, MessageCallback.filter(F.action == "select_thread")
)

request_router.callback_query.register(
    request_status_handler,
    MessageCallback.filter(F.action == "set_status"),
)

request_router.message.register(pending_handler, Command("pending"))
request_router.message.register(pending_chat_handler, Command("pending_chat"))

request_router.message.register(message_handler)
