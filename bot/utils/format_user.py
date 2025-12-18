import html
from aiogram.types import User

from app.db.models.user import User as UserDb


def format_user_info(user: User | UserDb) -> str:
    if user.username:
        return f"{user.full_name} @{user.username}"

    return user.full_name


def format_user_info_html(user: User | UserDb, is_code_username: bool = True) -> str:
    name = html.escape(user.full_name)

    if user.username:
        if is_code_username:
            return f"{name} <code>@{user.username}</code>"

        return f"{name} @{user.username}"

    return name
