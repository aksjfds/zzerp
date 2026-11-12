from sqlalchemy import Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from database import Base


class ProductionDepartment(Base):
    __tablename__ = "production_department"
    __table_args__ = (UniqueConstraint("name", name="uq_production_department_name"),)

    code: Mapped[str] = mapped_column(Text, primary_key=True)
    name: Mapped[str] = mapped_column(Text, nullable=False)
