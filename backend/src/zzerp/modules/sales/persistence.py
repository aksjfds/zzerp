from __future__ import annotations

from datetime import datetime

from sqlalchemy import TIMESTAMP, BigInteger, Index, Text, UniqueConstraint, text
from sqlalchemy.orm import Mapped, mapped_column

from zzerp.database import Base


class Customer(Base):
    __tablename__ = "customer"
    __table_args__ = (
        UniqueConstraint("customer_name", name="uq_customer_name"),
        Index(
            "idx_customer_name_trgm",
            "customer_name",
            postgresql_using="gin",
            postgresql_ops={"customer_name": "gin_trgm_ops"},
        ),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    customer_name: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), nullable=False, server_default=text("CURRENT_TIMESTAMP")
    )
    updated_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), nullable=False, server_default=text("CURRENT_TIMESTAMP")
    )
