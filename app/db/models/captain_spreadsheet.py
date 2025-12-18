from typing import TYPE_CHECKING
from sqlalchemy import ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.db.base import Base
from app.db.timestamps import TimestampMixin


if TYPE_CHECKING:
    from app.db.models.organization import Organization


class CaptainSpreadsheet(Base, TimestampMixin):
    __tablename__ = "captain_spreadsheets"

    organization_id: Mapped[int] = mapped_column(
        ForeignKey("organizations.id", ondelete="CASCADE"), primary_key=True
    )
    spreadsheet_id: Mapped[str] = mapped_column(nullable=False)

    chat_title_column: Mapped[str] = mapped_column(String(3), nullable=False)
    username_column: Mapped[str] = mapped_column(String(3), nullable=False)
    sheet_name: Mapped[str | None] = mapped_column(nullable=True)
    rows_range_min: Mapped[int | None] = mapped_column(nullable=True)
    rows_range_max: Mapped[int | None] = mapped_column(nullable=True)

    organization: Mapped["Organization"] = relationship(
        back_populates="captain_spreadsheet", uselist=False
    )
