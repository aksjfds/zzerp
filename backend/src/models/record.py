from datetime import datetime

from sqlalchemy import BigInteger, Integer, String, TIMESTAMP, func, or_, text
from sqlalchemy.orm import Mapped, mapped_column

from backend.src.database import Base, SessionLocal


class Repository(Base):
    __tablename__ = "repository"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    repository_name: Mapped[str] = mapped_column(String(50), nullable=False)
    order_id: Mapped[int] = mapped_column(Integer, nullable=False)
    item: Mapped[str] = mapped_column(String(100), nullable=False)
    quantity: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    def __init__(
        self,
        order_id: int,
        item: str,
        repository_name: str,
        quantity: int = 0,
    ):
        self.order_id = order_id
        self.item = item
        self.repository_name = repository_name
        self.quantity = quantity

    @classmethod
    def create_from_work_order(
        cls,
        item: str,
        procedures: list[str],
        quantity: int,
        order_id: int | None = None,
        operator: str | None = None,
    ) -> list["Repository"]:
        if not procedures:
            raise ValueError("至少需要一道工序")

        with SessionLocal() as session:
            if order_id is None:
                max_order_id = session.query(func.max(cls.order_id)).scalar() or 0
                resolved_order_id = max_order_id + 1
            else:
                resolved_order_id = order_id

            repositories: list[Repository] = []

            repository_names = [*procedures, "out"]

            for index, repository_name in enumerate(repository_names):
                repository = cls(
                    order_id=resolved_order_id,
                    item=item,
                    repository_name=repository_name,
                    quantity=quantity if index == 0 else 0,
                )
                session.add(repository)
                repositories.append(repository)

            session.add(
                Record(
                    order_id=resolved_order_id,
                    item=item,
                    from_repository="in",
                    to_repository=procedures[0],
                    quantity=quantity,
                    operator=operator,
                    note="创建工单",
                )
            )

            session.commit()

            for repository in repositories:
                session.refresh(repository)

            return repositories

    @classmethod
    def get_work_orders(cls) -> list[dict]:
        with SessionLocal() as session:
            repositories = (
                session.query(cls)
                .order_by(cls.order_id.desc(), cls.id.asc())
                .all()
            )

            work_orders: dict[tuple[int, str], dict] = {}

            for repository in repositories:
                key = (repository.order_id, repository.item)
                work_order = work_orders.setdefault(
                    key,
                    {
                        "id": repository.order_id,
                        "item": repository.item,
                        "quantity": 0,
                        "steps": [],
                    },
                )

                work_order["quantity"] += repository.quantity
                if repository.repository_name != "out":
                    work_order["steps"].append(
                        {
                            "name": repository.repository_name,
                            "quantity": repository.quantity,
                        }
                    )

            return list(work_orders.values())

    @classmethod
    def move_quantity(
        cls,
        order_id: int,
        item: str,
        from_repository: str,
        to_repository: str,
        quantity: int,
        operator: str | None = None,
        worker: str | None = None,
        note: str | None = None,
    ) -> None:
        if quantity <= 0:
            raise ValueError("数量必须大于 0")

        with SessionLocal() as session:
            repositories = (
                session.query(cls)
                .filter(cls.order_id == order_id, cls.item == item)
                .order_by(cls.id.asc())
                .all()
            )
            repository_by_name = {
                repository.repository_name: repository
                for repository in repositories
            }

            source = repository_by_name.get(from_repository)
            target = repository_by_name.get(to_repository)

            if source is None:
                raise ValueError("来源仓库不存在")

            if source.quantity < quantity:
                raise ValueError("数量不能超过当前仓库库存")

            source.quantity -= quantity

            if target is not None:
                target.quantity += quantity

            session.add(
                Record(
                    order_id=order_id,
                    item=item,
                    from_repository=from_repository,
                    to_repository=to_repository,
                    worker=worker,
                    quantity=quantity,
                    operator=operator,
                    note=note,
                )
            )
            session.commit()

    @classmethod
    def move_to_next_repository(
        cls,
        order_id: int,
        item: str,
        repository_name: str,
        quantity: int,
        operator: str | None = None,
        worker: str | None = None,
        note: str | None = None,
    ) -> None:
        target_repository = cls._get_adjacent_repository(
            order_id=order_id,
            item=item,
            repository_name=repository_name,
            direction=1,
        )
        cls.move_quantity(
            order_id=order_id,
            item=item,
            from_repository=repository_name,
            to_repository=target_repository or "out",
            quantity=quantity,
            operator=operator,
            worker=worker,
            note=note or "工序出库",
        )

    @classmethod
    def rework_to_previous_repository(
        cls,
        order_id: int,
        item: str,
        repository_name: str,
        quantity: int,
        operator: str | None = None,
        worker: str | None = None,
        note: str | None = None,
    ) -> None:
        target_repository = cls._get_adjacent_repository(
            order_id=order_id,
            item=item,
            repository_name=repository_name,
            direction=-1,
        )

        if target_repository is None:
            raise ValueError("第一道工序不能返工")

        cls.move_quantity(
            order_id=order_id,
            item=item,
            from_repository=repository_name,
            to_repository=target_repository,
            quantity=quantity,
            operator=operator,
            worker=worker,
            note=note or "返工",
        )

    @classmethod
    def _get_adjacent_repository(
        cls,
        order_id: int,
        item: str,
        repository_name: str,
        direction: int,
    ) -> str | None:
        with SessionLocal() as session:
            repositories = (
                session.query(cls)
                .filter(cls.order_id == order_id, cls.item == item)
                .order_by(cls.id.asc())
                .all()
            )
            current_index = next(
                (
                    index
                    for index, repository in enumerate(repositories)
                    if repository.repository_name == repository_name
                ),
                None,
            )

            if current_index is None:
                raise ValueError("仓库不存在")

            target_index = current_index + direction

            if target_index < 0 or target_index >= len(repositories):
                return None

            return repositories[target_index].repository_name


class Record(Base):
    __tablename__ = "records"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    order_id: Mapped[int] = mapped_column(Integer, nullable=False)
    item: Mapped[str] = mapped_column(String(100), nullable=False)
    from_repository: Mapped[str | None] = mapped_column(String(50), nullable=True)
    to_repository: Mapped[str | None] = mapped_column(String(50), nullable=True)
    worker: Mapped[str | None] = mapped_column(String(100), nullable=True)
    quantity: Mapped[int] = mapped_column(Integer, nullable=False)
    operator: Mapped[str | None] = mapped_column(String(100), nullable=True)
    note: Mapped[str | None] = mapped_column(String(255), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP, nullable=False, server_default=text("CURRENT_TIMESTAMP")
    )

    def __init__(
        self,
        order_id: int,
        item: str,
        quantity: int,
        from_repository: str | None = None,
        to_repository: str | None = None,
        worker: str | None = None,
        operator: str | None = None,
        note: str | None = None,
    ):
        self.order_id = order_id
        self.item = item
        self.from_repository = from_repository
        self.to_repository = to_repository
        self.worker = worker
        self.quantity = quantity
        self.operator = operator
        self.note = note

    @classmethod
    def get_by_work_order_step(cls, order_id: int, item: str, repository: str) -> list[dict]:
        with SessionLocal() as session:
            records = (
                session.query(cls)
                .filter(
                    cls.order_id == order_id,
                    cls.item == item,
                    or_(
                        cls.from_repository == repository,
                        cls.to_repository == repository,
                    ),
                )
                .order_by(cls.created_at.desc(), cls.id.desc())
                .all()
            )

            return [
                {
                    "id": record.id,
                    "createdAt": record.created_at.strftime("%Y-%m-%d %H:%M"),
                    "fromRepository": record.from_repository,
                    "toRepository": record.to_repository,
                    "worker": record.worker,
                    "quantity": record.quantity,
                    "operator": record.operator,
                    "note": record.note,
                }
                for record in records
            ]
