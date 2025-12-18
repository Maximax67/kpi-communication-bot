from aiogram.types import User as TelegramUser
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import delete, literal_column, select

from app.db.models.chat import Chat
from app.db.models.chat_user import ChatUser
from app.db.models.user import User


async def get_user_chat_info(
    db: AsyncSession, user_id: int, chat_id: int
) -> tuple[User | None, Chat | None, ChatUser | None]:
    base = select(literal_column("1")).subquery()
    stmt = (
        select(User, Chat, ChatUser)
        .select_from(base)
        .join(User, User.id == user_id, isouter=True)
        .join(
            ChatUser,
            (ChatUser.user_id == user_id) & (ChatUser.chat_id == chat_id),
            isouter=True,
        )
        .join(Chat, Chat.id == chat_id, isouter=True)
    )

    result = await db.execute(stmt)
    (user, chat, chat_user) = result.one()

    return user, chat, chat_user


async def register_user(db: AsyncSession, tg_user: TelegramUser) -> None:
    stmt = select(User).where(User.id == tg_user.id)
    result = await db.execute(stmt)
    user = result.scalar_one_or_none()

    if user:
        user.username = tg_user.username
        user.first_name = tg_user.first_name
        user.last_name = tg_user.last_name
    else:
        user = User(
            id=tg_user.id,
            username=tg_user.username,
            first_name=tg_user.first_name,
            last_name=tg_user.last_name,
        )
        db.add(user)

    await db.commit()


async def register_chat_user(
    db: AsyncSession, tg_user: TelegramUser, chat_id: int
) -> None:
    user, chat, chat_user = await get_user_chat_info(db, tg_user.id, chat_id)

    if user is None:
        user = User(
            id=tg_user.id,
            username=tg_user.username,
            first_name=tg_user.first_name,
            last_name=tg_user.last_name,
        )
        db.add(user)
    else:
        user.username = tg_user.username
        user.first_name = tg_user.first_name
        user.last_name = tg_user.last_name

    if chat and chat_user is None:
        db.add(ChatUser(user_id=tg_user.id, chat_id=chat_id))

    await db.commit()


async def delete_user_from_chat(db: AsyncSession, user_id: int, chat_id: int) -> None:
    await db.execute(
        delete(ChatUser).where(
            ChatUser.user_id == user_id,
            ChatUser.chat_id == chat_id,
        )
    )
