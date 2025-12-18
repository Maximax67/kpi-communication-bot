from typing import TYPE_CHECKING
from sqlalchemy import BigInteger, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.db.base import Base
from app.db.timestamps import CreatedTimestamp


if TYPE_CHECKING:
    from app.db.models.chat import Chat
    from app.db.models.user import User


class ChatUser(Base, CreatedTimestamp):
    __tablename__ = "chat_users"

    chat_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("chats.id", onupdate="CASCADE", ondelete="CASCADE"),
        primary_key=True,
        index=True,
    )
    user_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("users.id", ondelete="CASCADE"),
        primary_key=True,
        index=True,
    )

    chat: Mapped["Chat"] = relationship(back_populates="users", uselist=False)
    user: Mapped["User"] = relationship(back_populates="chats", uselist=False)
