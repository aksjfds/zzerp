from sqlalchemy import BigInteger, ForeignKey, Integer, Text
from sqlalchemy.orm import Mapped, mapped_column

from database import Base


class Repository(Base):
    __tablename__ = "repository"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    customer_order_item_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("customer_order_item.id", ondelete="CASCADE"),
        nullable=False,
    )
    product_bom_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("product_bom.id"), nullable=False
    )
    flow_node_id: Mapped[str] = mapped_column(Text, nullable=False)
    department_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("department.id"), nullable=False
    )
    quantity: Mapped[int] = mapped_column(Integer, nullable=False)
