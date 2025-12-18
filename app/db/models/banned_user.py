from typing import TYPE_CHECKING
from sqlalchemy import BigInteger, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.db.base import Base
from app.db.timestamps import CreatedTimestamp


if TYPE_CHECKING:
    from app.db.models.organization import Organization


class BannedUser(Base, CreatedTimestamp):
    __tablename__ = "banned_users"

    organization_id: Mapped[int] = mapped_column(
        ForeignKey("organizations.id", ondelete="CASCADE"),
        primary_key=True,
    )
    user_id: Mapped[int] = mapped_column(
        BigInteger,
        primary_key=True,
    )
    banned_by: Mapped[int] = mapped_column(BigInteger, nullable=False)
    reason: Mapped[str] = mapped_column(String, nullable=True)

    organization: Mapped["Organization"] = relationship(
        back_populates="banned_users", uselist=False
    )
