from aiogram import F, Dispatcher

from app.db.session import async_session
from bot.handlers.cancel import cancel_handler
from bot.handlers.close import close_handler
from bot.callback import MainCallback
from bot.middlewares.ban_middleware import BanMiddleware
from bot.middlewares.db_session import DbSessionMiddleware
from bot.middlewares.organization import OrganizationMiddleware
from bot.middlewares.user_middleware import UserMiddleware
from bot.routers.root_router import root_router
from bot.routers.admin_router import admin_router
from bot.routers.chat_router import chat_router
from bot.routers.user_router import user_router
from bot.routers.request_router import request_router
from bot.utils.migrate_chat import auto_migrate


dp = Dispatcher()

dp.update.middleware(DbSessionMiddleware(async_session))
dp.update.middleware(OrganizationMiddleware())
dp.update.middleware(UserMiddleware())
dp.update.middleware(BanMiddleware())

dp.message.register(auto_migrate, F.migrate_to_chat_id)
dp.callback_query.register(close_handler, MainCallback.filter(F.action == "close"))
dp.callback_query.register(cancel_handler, MainCallback.filter(F.action == "cancel"))

dp.include_router(root_router)
dp.include_router(admin_router)
dp.include_router(chat_router)
dp.include_router(user_router)
dp.include_router(request_router)
