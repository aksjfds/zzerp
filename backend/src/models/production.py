from datetime import datetime

from sqlalchemy import BigInteger, Boolean, Integer, Text, TIMESTAMP, text
from sqlalchemy.dialects.postgresql import ARRAY
from sqlalchemy.orm import Mapped, mapped_column

from backend.src.database import Base, SessionLocal


class Product(Base):
    __tablename__ = "product"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    zz_code: Mapped[str] = mapped_column(Text, nullable=False)
    product_name: Mapped[str] = mapped_column(Text, nullable=False)
    process: Mapped[list[str]] = mapped_column(ARRAY(Text), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP, nullable=False, server_default=text("NOW()")
    )

    @staticmethod
    def serialize(product: "Product") -> dict:
        return {
            "id": product.id,
            "zzCode": product.zz_code,
            "productName": product.product_name,
            "process": product.process,
            "createdAt": product.created_at.strftime("%Y-%m-%d %H:%M"),
        }

    @classmethod
    def create(cls, zz_code: str, product_name: str, process: list[str], quantity: int) -> dict:
        if not process:
            raise ValueError("产品流程不能为空")

        with SessionLocal() as session:
            exists = (
                session.query(cls)
                .filter(cls.zz_code == zz_code, cls.product_name == product_name)
                .one_or_none()
            )
            if exists is not None:
                raise ValueError("产品已存在")

            product = cls(zz_code=zz_code, product_name=product_name, process=process)
            session.add(product)
            session.flush()

            first_department = process[0]
            session.add(
                Repository(
                    department=first_department,
                    zz_code=zz_code,
                    product_name=product_name,
                    quantity=quantity,
                )
            )
            session.add(
                Record(
                    zz_code=zz_code,
                    product=product_name,
                    from_repository="in",
                    to_repository=first_department,
                    quantity=quantity,
                    note="创建产品",
                )
            )
            session.commit()
            session.refresh(product)

            return cls.serialize(product)

    @classmethod
    def list_all(cls) -> list[dict]:
        with SessionLocal() as session:
            products = session.query(cls).order_by(cls.created_at.desc(), cls.id.desc()).all()
            repositories = session.query(Repository).all()

            repository_map: dict[tuple[str, str], list[dict]] = {}
            for repository in repositories:
                key = (repository.zz_code, repository.product_name)
                repository_map.setdefault(key, []).append(Repository.serialize(repository))

            result = []
            for product in products:
                item = cls.serialize(product)
                item["repositories"] = repository_map.get((product.zz_code, product.product_name), [])
                item["quantity"] = sum(repository["quantity"] for repository in item["repositories"])
                result.append(item)

            return result


class Repository(Base):
    __tablename__ = "repository"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    department: Mapped[str] = mapped_column(Text, nullable=False)
    zz_code: Mapped[str] = mapped_column(Text, nullable=False)
    product_name: Mapped[str] = mapped_column(Text, nullable=False)
    quantity: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    @staticmethod
    def serialize(repository: "Repository") -> dict:
        return {
            "id": repository.id,
            "department": repository.department,
            "zzCode": repository.zz_code,
            "productName": repository.product_name,
            "quantity": repository.quantity,
        }

    @classmethod
    def move(
        cls,
        zz_code: str,
        product_name: str,
        from_department: str,
        to_department: str,
        quantity: int,
        note: str | None = None,
    ) -> None:
        with SessionLocal() as session:
            cls._move_in_session(
                session=session,
                zz_code=zz_code,
                product_name=product_name,
                from_department=from_department,
                to_department=to_department,
                quantity=quantity,
                note=note,
            )
            session.commit()

    @classmethod
    def _move_in_session(
        cls,
        session,
        zz_code: str,
        product_name: str,
        from_department: str,
        to_department: str,
        quantity: int,
        note: str | None = None,
    ) -> None:
        if quantity <= 0:
            raise ValueError("数量必须大于 0")

        source = (
            session.query(cls)
            .filter(
                cls.zz_code == zz_code,
                cls.product_name == product_name,
                cls.department == from_department,
            )
            .one_or_none()
        )
        if source is None:
            raise ValueError("来源部门没有该产品库存")

        if source.quantity < quantity:
            raise ValueError("流转数量不能超过当前库存")

        target = (
            session.query(cls)
            .filter(
                cls.zz_code == zz_code,
                cls.product_name == product_name,
                cls.department == to_department,
            )
            .one_or_none()
        )

        source.quantity -= quantity
        if target is None:
            target = cls(
                department=to_department,
                zz_code=zz_code,
                product_name=product_name,
                quantity=0,
            )
            session.add(target)

        target.quantity += quantity
        session.add(
            Record(
                zz_code=zz_code,
                product=product_name,
                from_repository=from_department,
                to_repository=to_department,
                quantity=quantity,
                note=note,
            )
        )


class Procedure(Base):
    __tablename__ = "procedure"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    procedure_name: Mapped[str] = mapped_column(Text, nullable=False)
    department: Mapped[str] = mapped_column(Text, nullable=False)

    @staticmethod
    def serialize(procedure: "Procedure") -> dict:
        return {
            "id": procedure.id,
            "procedureName": procedure.procedure_name,
            "department": procedure.department,
        }

    @classmethod
    def list_by_department(cls, department: str) -> list[dict]:
        with SessionLocal() as session:
            procedures = (
                session.query(cls)
                .filter(cls.department == department)
                .order_by(cls.procedure_name.asc())
                .all()
            )
            return [cls.serialize(procedure) for procedure in procedures]


class Record(Base):
    __tablename__ = "records"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    zz_code: Mapped[str] = mapped_column(Text, nullable=False)
    product: Mapped[str] = mapped_column(Text, nullable=False)
    from_repository: Mapped[str] = mapped_column(Text, nullable=False)
    to_repository: Mapped[str] = mapped_column(Text, nullable=False)
    quantity: Mapped[int] = mapped_column(Integer, nullable=False)
    note: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP, nullable=False, server_default=text("NOW()")
    )

    @staticmethod
    def serialize(record: "Record") -> dict:
        return {
            "id": record.id,
            "zzCode": record.zz_code,
            "product": record.product,
            "fromRepository": record.from_repository,
            "toRepository": record.to_repository,
            "quantity": record.quantity,
            "note": record.note,
            "createdAt": record.created_at.strftime("%Y-%m-%d %H:%M"),
        }

    @classmethod
    def list_by_product(cls, zz_code: str, product: str) -> list[dict]:
        with SessionLocal() as session:
            records = (
                session.query(cls)
                .filter(cls.zz_code == zz_code, cls.product == product)
                .order_by(cls.created_at.desc(), cls.id.desc())
                .all()
            )
            return [cls.serialize(record) for record in records]


class Task(Base):
    __tablename__ = "tasks"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    zz_code: Mapped[str] = mapped_column(Text, nullable=False)
    product: Mapped[str] = mapped_column(Text, nullable=False)
    worker: Mapped[str] = mapped_column(Text, nullable=False)
    department: Mapped[str] = mapped_column(Text, nullable=False)
    procedure: Mapped[str] = mapped_column(Text, nullable=False)
    quantity: Mapped[int] = mapped_column(Integer, nullable=False)
    ok: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    status: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    note: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP, nullable=False, server_default=text("NOW()")
    )

    @staticmethod
    def serialize(task: "Task") -> dict:
        return {
            "id": task.id,
            "zzCode": task.zz_code,
            "product": task.product,
            "worker": task.worker,
            "department": task.department,
            "procedure": task.procedure,
            "quantity": task.quantity,
            "ok": task.ok,
            "status": task.status,
            "note": task.note,
            "createdAt": task.created_at.strftime("%Y-%m-%d %H:%M"),
        }

    @classmethod
    def list_by_department(cls, department: str) -> list[dict]:
        with SessionLocal() as session:
            tasks = (
                session.query(cls)
                .filter(cls.department == department)
                .order_by(cls.created_at.desc(), cls.id.desc())
                .all()
            )
            return [cls.serialize(task) for task in tasks]

    @classmethod
    def create(
        cls,
        zz_code: str,
        product: str,
        worker: str,
        department: str,
        procedure: str,
        quantity: int,
        note: str | None = None,
    ) -> dict:
        with SessionLocal() as session:
            task = cls(
                zz_code=zz_code,
                product=product,
                worker=worker,
                department=department,
                procedure=procedure,
                quantity=quantity,
                note=note,
            )
            session.add(task)
            session.commit()
            session.refresh(task)
            return cls.serialize(task)

    @classmethod
    def complete(cls, task_id: int) -> dict:
        with SessionLocal() as session:
            task = session.query(cls).filter(cls.id == task_id).one_or_none()
            if task is None:
                raise ValueError("任务不存在")

            if task.status:
                return cls.serialize(task)

            product = (
                session.query(Product)
                .filter(Product.zz_code == task.zz_code, Product.product_name == task.product)
                .one_or_none()
            )
            if product is None:
                raise ValueError("产品不存在")

            try:
                current_index = product.process.index(task.department)
            except ValueError as exc:
                raise ValueError("产品流程不包含当前部门") from exc

            next_department = (
                product.process[current_index + 1]
                if current_index + 1 < len(product.process)
                else "out"
            )

            Repository._move_in_session(
                session=session,
                zz_code=task.zz_code,
                product_name=task.product,
                from_department=task.department,
                to_department=next_department,
                quantity=task.quantity,
                note=f"{task.worker} 完成 {task.procedure}",
            )
            task.ok = task.quantity
            task.status = True
            session.commit()
            session.refresh(task)
            return cls.serialize(task)


class Worker(Base):
    __tablename__ = "worker"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(Text, nullable=False)
    department: Mapped[str] = mapped_column(Text, nullable=False)

    @staticmethod
    def serialize(worker: "Worker") -> dict:
        return {
            "id": worker.id,
            "name": worker.name,
            "department": worker.department,
        }

    @classmethod
    def list_by_department(cls, department: str) -> list[dict]:
        with SessionLocal() as session:
            workers = (
                session.query(cls)
                .filter(cls.department == department)
                .order_by(cls.name.asc())
                .all()
            )
            return [cls.serialize(worker) for worker in workers]
