from aiogram import F, Router
from aiogram.filters import Command

from app.core.settings import settings
from bot.handlers.admin.rename_organization import (
    approve_rename_organization,
    reject_rename_organization,
)
from bot.handlers.root.delete_ogranization import (
    approve_delete_organization,
    delete_organization,
    delete_organization_confirmed,
    delete_organization_handler,
    reject_delete_organization,
)
from bot.handlers.root.list_organizations import organizations_handler
from bot.handlers.root.create_organization import (
    verify_organization,
    reject_organization,
)
from bot.callback import OrganizationCallback


root_router = Router()

root_router.message.register(
    organizations_handler,
    Command("organizations"),
    F.chat.id == settings.ROOT_ADMIN_CHAT_ID,
)
root_router.message.register(
    delete_organization_handler,
    Command("delete_organization"),
    F.chat.id == settings.ROOT_ADMIN_CHAT_ID,
)

root_router.callback_query.register(
    delete_organization,
    OrganizationCallback.filter(F.action == "delete"),
    F.message.chat.id == settings.ROOT_ADMIN_CHAT_ID,
)
root_router.callback_query.register(
    delete_organization_confirmed,
    OrganizationCallback.filter(F.action == "confirm_delete"),
    F.message.chat.id == settings.ROOT_ADMIN_CHAT_ID,
)
root_router.callback_query.register(
    verify_organization,
    OrganizationCallback.filter(F.action == "verify"),
    F.message.chat.id == settings.ROOT_ADMIN_CHAT_ID,
)
root_router.callback_query.register(
    reject_organization,
    OrganizationCallback.filter(F.action == "reject"),
    F.message.chat.id == settings.ROOT_ADMIN_CHAT_ID,
)

root_router.callback_query.register(
    approve_rename_organization,
    OrganizationCallback.filter(F.action == "approve_rename"),
    F.message.chat.id == settings.ROOT_ADMIN_CHAT_ID,
)
root_router.callback_query.register(
    reject_rename_organization,
    OrganizationCallback.filter(F.action == "reject_rename"),
    F.message.chat.id == settings.ROOT_ADMIN_CHAT_ID,
)

root_router.callback_query.register(
    approve_delete_organization,
    OrganizationCallback.filter(F.action == "approve_delete"),
    F.message.chat.id == settings.ROOT_ADMIN_CHAT_ID,
)
root_router.callback_query.register(
    reject_delete_organization,
    OrganizationCallback.filter(F.action == "reject_delete"),
    F.message.chat.id == settings.ROOT_ADMIN_CHAT_ID,
)
