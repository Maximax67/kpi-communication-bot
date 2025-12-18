from typing import TYPE_CHECKING
from sqlalchemy import BigInteger, String
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.db.base import Base
from app.db.timestamps import TimestampMixin

if TYPE_CHECKING:
    from app.db.models.chat import Chat
    from app.db.models.banned_user import BannedUser
    from app.db.models.captain_spreadsheet import CaptainSpreadsheet
    from app.db.models.chat_captain import ChatCaptain
    from app.db.models.telegram_bot import TelegramBot


class Organization(Base, TimestampMixin):
    __tablename__ = "organizations"

    id: Mapped[int] = mapped_column(primary_key=True)
    title: Mapped[str] = mapped_column(String(32), nullable=False)
    admin_chat_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    admin_chat_thread_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    is_admins_accept_messages: Mapped[bool] = mapped_column(
        default=True, nullable=False
    )
    greeting_message: Mapped[str | None] = mapped_column(nullable=True)
    is_private: Mapped[bool] = mapped_column(default=False, nullable=False)
    is_verified: Mapped[bool] = mapped_column(default=False, nullable=False)
    owner: Mapped[int] = mapped_column(
        BigInteger, unique=True, index=True, nullable=False
    )

    chats: Mapped[list["Chat"]] = relationship(
        back_populates="organization", passive_deletes=True
    )
    banned_users: Mapped[list["BannedUser"]] = relationship(
        back_populates="organization", passive_deletes=True
    )
    captain_spreadsheet: Mapped["CaptainSpreadsheet | None"] = relationship(
        back_populates="organization", uselist=False, passive_deletes=True
    )
    captains: Mapped[list["ChatCaptain"]] = relationship(
        back_populates="organization", passive_deletes=True
    )
    bot: Mapped["TelegramBot | None"] = relationship(
        back_populates="organization", uselist=False
    )
