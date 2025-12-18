from typing import TYPE_CHECKING
from sqlalchemy import BigInteger, String
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.db.base import Base
from app.db.timestamps import TimestampMixin


if TYPE_CHECKING:
    from app.db.models.chat_captain import ChatCaptain
    from app.db.models.chat_user import ChatUser


class User(Base, TimestampMixin):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(
        BigInteger,
        primary_key=True,
    )
    username: Mapped[str | None] = mapped_column(String(32), nullable=True, index=True)
    first_name: Mapped[str] = mapped_column(nullable=False)
    last_name: Mapped[str | None] = mapped_column(nullable=True)

    chats: Mapped[list["ChatUser"]] = relationship(back_populates="user", uselist=True)
    chats_captain: Mapped[list["ChatCaptain"]] = relationship(
        back_populates="connected_user", passive_deletes=True
    )

    @property
    def full_name(self) -> str:
        if self.last_name:
            return f"{self.first_name} {self.last_name}"

        return self.first_name
