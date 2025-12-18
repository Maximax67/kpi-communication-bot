from typing import TYPE_CHECKING
from sqlalchemy import BigInteger, ForeignKey, LargeBinary, String
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.db.base import Base
from app.db.timestamps import TimestampMixin

if TYPE_CHECKING:
    from app.db.models.organization import Organization


class TelegramBot(Base, TimestampMixin):
    __tablename__ = "telegram_bots"

    id: Mapped[int] = mapped_column(
        BigInteger,
        primary_key=True,
    )
    token: Mapped[bytes] = mapped_column(LargeBinary, nullable=False)
    username: Mapped[str] = mapped_column(String(32), nullable=False)
    secret: Mapped[bytes] = mapped_column(LargeBinary, nullable=False)
    owner: Mapped[int] = mapped_column(BigInteger, nullable=False)
    organization_id: Mapped[int] = mapped_column(
        ForeignKey("organizations.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )

    organization: Mapped["Organization"] = relationship(
        back_populates="bot", uselist=False
    )
