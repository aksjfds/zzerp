from datetime import date, datetime

from sqlalchemy import (
    BigInteger,
    Boolean,
    Date,
    ForeignKey,
    Integer,
    Text,
    TIMESTAMP,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column

from database import Base, SessionLocal


class Product(Base):
    __tablename__ = "product"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    order_id: Mapped[str] = mapped_column(Text, nullable=False)
    zz_code: Mapped[str] = mapped_column(Text, nullable=False)
    product_name: Mapped[str] = mapped_column(Text, nullable=False)
    delivery_date: Mapped[date] = mapped_column(Date, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP,
        nullable=False,
        server_default=text("NOW()"),
    )

    @staticmethod
    def serialize(product: "Product", process: list[str]) -> dict:
        return {
            "id": product.id,
            "orderId": product.order_id,
            "zzCode": product.zz_code,
            "productName": product.product_name,
            "deliveryDate": product.delivery_date.isoformat(),
            "process": process,
            "createdAt": product.created_at.strftime("%Y-%m-%d %H:%M"),
        }

    @classmethod
    def create(
        cls,
        order_id: str,
        zz_code: str,
        product_name: str,
        delivery_date: date,
        process: list[str],
        quantity: int,
    ) -> dict:
        if not process:
            raise ValueError("产品部门流程不能为空")
        if len(set(process)) != len(process):
            raise ValueError("产品部门流程不能包含重复部门")

        with SessionLocal() as session:
            exists = (
                session.query(cls)
                .filter(
                    cls.order_id == order_id,
                    cls.zz_code == zz_code,
                    cls.product_name == product_name,
                )
                .one_or_none()
            )
            if exists is not None:
                raise ValueError("当前订单中已存在该产品")

            product = cls(
                order_id=order_id,
                zz_code=zz_code,
                product_name=product_name,
                delivery_date=delivery_date,
            )
            session.add(product)
            session.flush()

            for index, department in enumerate(process, start=1):
                session.add(
                    ProductDepartmentStep(
                        product_id=product.id,
                        sequence_no=index,
                        department=department,
                    )
                )

            first_department = process[0]
            repository = Repository(
                department=first_department,
                product_id=product.id,
                quantity=quantity,
            )
            session.add(repository)
            session.add(
                Record(
                    product_id=product.id,
                    from_repository="in",
                    to_repository=first_department,
                    quantity=quantity,
                    note="创建产品",
                )
            )
            session.commit()
            session.refresh(product)
            session.refresh(repository)

            item = cls.serialize(product, process)
            item["repositories"] = [Repository.serialize(repository)]
            item["quantity"] = quantity
            return item

    @classmethod
    def list_all(cls, department: str | None = None) -> list[dict]:
        with SessionLocal() as session:
            product_query = session.query(cls)
            repository_query = session.query(Repository)

            if department:
                product_query = product_query.join(
                    Repository,
                    Repository.product_id == cls.id,
                ).filter(
                    Repository.department == department,
                    Repository.quantity > 0,
                )
                repository_query = repository_query.filter(
                    Repository.department == department
                )

            products = product_query.order_by(
                cls.delivery_date.asc(),
                cls.created_at.desc(),
                cls.id.desc(),
            ).all()
            repositories = repository_query.all()
            department_steps = (
                session.query(ProductDepartmentStep)
                .order_by(ProductDepartmentStep.sequence_no.asc())
                .all()
            )

            repository_map: dict[int, list[dict]] = {}
            for repository in repositories:
                repository_map.setdefault(repository.product_id, []).append(
                    Repository.serialize(repository)
                )

            process_map: dict[int, list[str]] = {}
            for step in department_steps:
                process_map.setdefault(step.product_id, []).append(step.department)

            result = []
            for product in products:
                item = cls.serialize(product, process_map.get(product.id, []))
                item["repositories"] = repository_map.get(product.id, [])
                item["quantity"] = sum(
                    repository["quantity"] for repository in item["repositories"]
                )
                result.append(item)

            return result


class ProductDepartmentStep(Base):
    __tablename__ = "product_department_step"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    product_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("product.id", ondelete="CASCADE"),
        nullable=False,
    )
    sequence_no: Mapped[int] = mapped_column(Integer, nullable=False)
    department: Mapped[str] = mapped_column(Text, nullable=False)


class Repository(Base):
    __tablename__ = "repository"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    department: Mapped[str] = mapped_column(Text, nullable=False)
    product_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("product.id", ondelete="CASCADE"),
        nullable=False,
    )
    quantity: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    @staticmethod
    def serialize(repository: "Repository") -> dict:
        return {
            "id": repository.id,
            "department": repository.department,
            "productId": repository.product_id,
            "quantity": repository.quantity,
        }


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
            items = (
                session.query(cls)
                .filter(cls.department == department)
                .order_by(cls.procedure_name.asc())
                .all()
            )
            return [cls.serialize(item) for item in items]

    @classmethod
    def create(cls, department: str, procedure_name: str) -> dict:
        with SessionLocal() as session:
            item = (
                session.query(cls)
                .filter(
                    cls.department == department,
                    cls.procedure_name == procedure_name,
                )
                .one_or_none()
            )
            if item is None:
                item = cls(
                    department=department,
                    procedure_name=procedure_name,
                )
                session.add(item)
                session.commit()
                session.refresh(item)
            return cls.serialize(item)


class Worker(Base):
    __tablename__ = "worker"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(Text, nullable=False)
    department: Mapped[str] = mapped_column(Text, nullable=False)
    active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)

    @staticmethod
    def serialize(worker: "Worker") -> dict:
        return {
            "id": worker.id,
            "name": worker.name,
            "department": worker.department,
            "active": worker.active,
        }

    @classmethod
    def list_by_department(cls, department: str) -> list[dict]:
        with SessionLocal() as session:
            workers = (
                session.query(cls)
                .filter(cls.department == department, cls.active.is_(True))
                .order_by(cls.name.asc())
                .all()
            )
            return [cls.serialize(worker) for worker in workers]

    @classmethod
    def create(cls, department: str, name: str) -> dict:
        with SessionLocal() as session:
            worker = (
                session.query(cls)
                .filter(cls.department == department, cls.name == name)
                .one_or_none()
            )
            if worker is None:
                worker = cls(department=department, name=name, active=True)
                session.add(worker)
                session.commit()
                session.refresh(worker)
            elif not worker.active:
                worker.active = True
                session.commit()
                session.refresh(worker)
            return cls.serialize(worker)


class DepartmentProcess(Base):
    __tablename__ = "department_process"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    product_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("product.id", ondelete="CASCADE"),
        nullable=False,
    )
    department: Mapped[str] = mapped_column(Text, nullable=False)
    sequence_no: Mapped[int] = mapped_column(Integer, nullable=False)
    process_name: Mapped[str] = mapped_column(Text, nullable=False)
    requires_qc: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    available_quantity: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP,
        nullable=False,
        server_default=text("NOW()"),
    )

    @staticmethod
    def serialize(item: "DepartmentProcess") -> dict:
        return {
            "id": item.id,
            "productId": item.product_id,
            "department": item.department,
            "sequenceNo": item.sequence_no,
            "processName": item.process_name,
            "requiresQc": item.requires_qc,
            "availableQuantity": item.available_quantity,
        }

    @classmethod
    def list_by_department(cls, department: str) -> list[dict]:
        with SessionLocal() as session:
            items = (
                session.query(cls)
                .filter(cls.department == department)
                .order_by(cls.product_id.asc(), cls.sequence_no.asc())
                .all()
            )
            return [cls.serialize(item) for item in items]

    @classmethod
    def configure(
        cls,
        product_id: int,
        department: str,
        steps: list[dict],
    ) -> list[dict]:
        if not steps:
            raise ValueError("至少需要配置一道部门工艺")

        with SessionLocal() as session:
            product = session.get(Product, product_id)
            if product is None:
                raise ValueError("产品不存在")

            belongs_to_route = (
                session.query(ProductDepartmentStep)
                .filter(
                    ProductDepartmentStep.product_id == product_id,
                    ProductDepartmentStep.department == department,
                )
                .first()
            )
            if belongs_to_route is None:
                raise ValueError("产品的部门流程不包含当前部门")

            existing_processes = session.query(cls).filter(
                cls.product_id == product_id,
                cls.department == department,
            )
            existing_ids = [item.id for item in existing_processes.all()]
            if existing_ids:
                has_work_orders = (
                    session.query(WorkOrder)
                    .filter(WorkOrder.process_id.in_(existing_ids))
                    .first()
                )
                if has_work_orders is not None:
                    raise ValueError("已有工单，不能修改部门工艺")
                existing_processes.delete(synchronize_session=False)

            repository = (
                session.query(Repository)
                .filter(
                    Repository.product_id == product_id,
                    Repository.department == department,
                )
                .one_or_none()
            )
            available = repository.quantity if repository is not None else 0

            created = []
            names: set[str] = set()
            for index, step in enumerate(steps, start=1):
                process_name = str(step["process_name"]).strip()
                if not process_name:
                    raise ValueError("工艺名称不能为空")
                if process_name in names:
                    raise ValueError("同一部门不能配置重复工艺")
                names.add(process_name)

                item = cls(
                    product_id=product_id,
                    department=department,
                    sequence_no=index,
                    process_name=process_name,
                    requires_qc=bool(step["requires_qc"]),
                    available_quantity=available if index == 1 else 0,
                )
                session.add(item)
                created.append(item)

            session.commit()
            for item in created:
                session.refresh(item)
            return [cls.serialize(item) for item in created]


class WorkOrder(Base):
    __tablename__ = "work_order"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    work_order_no: Mapped[str | None] = mapped_column(Text, unique=True, nullable=True)
    product_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("product.id"), nullable=False)
    process_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("department_process.id"),
        nullable=False,
    )
    worker_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("worker.id"), nullable=False)
    issued_quantity: Mapped[int] = mapped_column(Integer, nullable=False)
    status: Mapped[str] = mapped_column(Text, nullable=False, default="open")
    created_by: Mapped[int] = mapped_column(BigInteger, ForeignKey("users.id"), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP,
        nullable=False,
        server_default=text("NOW()"),
    )
    closed_at: Mapped[datetime | None] = mapped_column(TIMESTAMP, nullable=True)
    note: Mapped[str | None] = mapped_column(Text, nullable=True)

    @staticmethod
    def _totals(batches: list["WorkOrderBatch"]) -> dict:
        submitted = sum(batch.submitted_quantity for batch in batches)
        completed = [batch for batch in batches if batch.status == "completed"]
        ok = sum(batch.ok_quantity or 0 for batch in completed)
        rework = sum(batch.rework_quantity or 0 for batch in completed)
        scrap = sum(batch.scrap_quantity or 0 for batch in completed)
        lost = sum(batch.lost_quantity or 0 for batch in completed)
        pending_qc = sum(
            batch.submitted_quantity
            for batch in batches
            if batch.status == "pending_qc"
        )
        return {
            "submittedQuantity": submitted,
            "okQuantity": ok,
            "reworkQuantity": rework,
            "scrapQuantity": scrap,
            "lostQuantity": lost,
            "pendingQcQuantity": pending_qc,
        }

    @classmethod
    def _serialize_in_session(cls, session, item: "WorkOrder") -> dict:
        product = session.get(Product, item.product_id)
        process = session.get(DepartmentProcess, item.process_id)
        worker = session.get(Worker, item.worker_id)
        batches = (
            session.query(WorkOrderBatch)
            .filter(WorkOrderBatch.work_order_id == item.id)
            .order_by(WorkOrderBatch.batch_no.asc())
            .all()
        )
        totals = cls._totals(batches)
        processing = (
            item.issued_quantity
            + totals["reworkQuantity"]
            - totals["submittedQuantity"]
        )
        return {
            "id": item.id,
            "workOrderNo": item.work_order_no,
            "productId": item.product_id,
            "orderId": product.order_id,
            "zzCode": product.zz_code,
            "productName": product.product_name,
            "processId": item.process_id,
            "processName": process.process_name,
            "department": process.department,
            "requiresQc": process.requires_qc,
            "workerId": item.worker_id,
            "workerName": worker.name,
            "issuedQuantity": item.issued_quantity,
            "processingQuantity": processing,
            "status": item.status,
            "note": item.note,
            "createdAt": item.created_at.strftime("%Y-%m-%d %H:%M"),
            "closedAt": (
                item.closed_at.strftime("%Y-%m-%d %H:%M")
                if item.closed_at
                else None
            ),
            "batches": [
                cls._serialize_batch_in_session(session, batch) for batch in batches
            ],
            **totals,
        }

    @staticmethod
    def _serialize_batch_in_session(session, batch: "WorkOrderBatch") -> dict:
        data = WorkOrderBatch.serialize(batch)
        if batch.qc_worker_id:
            qc_worker = session.get(Worker, batch.qc_worker_id)
            data["qcWorkerName"] = qc_worker.name if qc_worker else None
        else:
            data["qcWorkerName"] = None
        return data

    @classmethod
    def list_by_department(cls, department: str) -> list[dict]:
        with SessionLocal() as session:
            items = (
                session.query(cls)
                .join(DepartmentProcess, DepartmentProcess.id == cls.process_id)
                .filter(DepartmentProcess.department == department)
                .order_by(cls.created_at.desc(), cls.id.desc())
                .all()
            )
            return [cls._serialize_in_session(session, item) for item in items]

    @classmethod
    def create(
        cls,
        product_id: int,
        process_id: int,
        worker_id: int,
        issued_quantity: int,
        created_by: int,
        allowed_department: str,
        note: str | None,
    ) -> dict:
        if issued_quantity <= 0:
            raise ValueError("领取数量必须大于 0")

        with SessionLocal() as session:
            process = (
                session.query(DepartmentProcess)
                .filter(DepartmentProcess.id == process_id)
                .with_for_update()
                .one_or_none()
            )
            if process is None or process.product_id != product_id:
                raise ValueError("产品工艺不存在")
            cls._ensure_department(process.department, allowed_department)
            if process.available_quantity < issued_quantity:
                raise ValueError("领取数量超过当前工艺可开单数量")

            worker = session.get(Worker, worker_id)
            if worker is None or not worker.active:
                raise ValueError("工人不存在或已停用")
            if worker.department != process.department:
                raise ValueError("工人与工艺部门不一致")

            process.available_quantity -= issued_quantity
            item = cls(
                product_id=product_id,
                process_id=process_id,
                worker_id=worker_id,
                issued_quantity=issued_quantity,
                created_by=created_by,
                note=note,
            )
            session.add(item)
            session.flush()
            item.work_order_no = f"MO-{datetime.now():%Y%m%d}-{item.id:06d}"
            session.commit()
            session.refresh(item)
            return cls._serialize_in_session(session, item)

    @classmethod
    def create_submission(
        cls,
        work_order_id: int,
        quantity: int,
        submitted_by: int,
        allowed_department: str,
    ) -> dict:
        if quantity <= 0:
            raise ValueError("送检数量必须大于 0")

        with SessionLocal() as session:
            item = (
                session.query(cls)
                .filter(cls.id == work_order_id)
                .with_for_update()
                .one_or_none()
            )
            if item is None:
                raise ValueError("工单不存在")
            process = session.get(DepartmentProcess, item.process_id)
            cls._ensure_department(process.department, allowed_department)
            if item.status != "open":
                raise ValueError("工单已经结单")
            if not process.requires_qc:
                raise ValueError("当前工艺不需要 QC")

            batches = cls._batches(session, item.id)
            processing = cls._processing_quantity(item, batches)
            if quantity > processing:
                raise ValueError("送检数量超过当前加工中数量")

            batch = WorkOrderBatch(
                work_order_id=item.id,
                batch_no=len(batches) + 1,
                submitted_quantity=quantity,
                status="pending_qc",
                submitted_by=submitted_by,
            )
            session.add(batch)
            session.commit()
            session.refresh(batch)
            return WorkOrderBatch.serialize(batch)

    @classmethod
    def create_direct_report(
        cls,
        work_order_id: int,
        ok_quantity: int,
        scrap_quantity: int,
        lost_quantity: int,
        reason: str | None,
        submitted_by: int,
        allowed_department: str,
    ) -> dict:
        submitted_quantity = ok_quantity + scrap_quantity + lost_quantity
        if submitted_quantity <= 0:
            raise ValueError("本次报工数量必须大于 0")

        with SessionLocal() as session:
            item = (
                session.query(cls)
                .filter(cls.id == work_order_id)
                .with_for_update()
                .one_or_none()
            )
            if item is None:
                raise ValueError("工单不存在")
            process = session.get(DepartmentProcess, item.process_id)
            cls._ensure_department(process.department, allowed_department)
            if item.status != "open":
                raise ValueError("工单已经结单")
            if process.requires_qc:
                raise ValueError("当前工艺必须由 QC 录入结果")

            batches = cls._batches(session, item.id)
            if submitted_quantity > cls._processing_quantity(item, batches):
                raise ValueError("报工数量超过当前加工中数量")

            batch = WorkOrderBatch(
                work_order_id=item.id,
                batch_no=len(batches) + 1,
                submitted_quantity=submitted_quantity,
                ok_quantity=ok_quantity,
                rework_quantity=0,
                scrap_quantity=scrap_quantity,
                lost_quantity=lost_quantity,
                defect_reason=reason,
                status="completed",
                submitted_by=submitted_by,
                inspected_by=submitted_by,
                inspected_at=datetime.now(),
            )
            session.add(batch)
            session.flush()
            cls._apply_result(session, item, process, batch)
            cls._close_if_complete(session, item)
            session.commit()
            session.refresh(batch)
            return WorkOrderBatch.serialize(batch)

    @classmethod
    def inspect_submission(
        cls,
        batch_id: int,
        ok_quantity: int,
        rework_quantity: int,
        scrap_quantity: int,
        lost_quantity: int,
        defect_reason: str | None,
        inspected_by: int,
        allowed_department: str,
    ) -> dict:
        if allowed_department not in {"sys", "qc"}:
            raise PermissionError("只有 QC 可以提交质检结果")

        with SessionLocal() as session:
            batch = (
                session.query(WorkOrderBatch)
                .filter(WorkOrderBatch.id == batch_id)
                .with_for_update()
                .one_or_none()
            )
            if batch is None:
                raise ValueError("送检批次不存在")
            if batch.status != "pending_qc":
                raise ValueError("该送检批次已经完成质检")

            total = ok_quantity + rework_quantity + scrap_quantity + lost_quantity
            if min(ok_quantity, rework_quantity, scrap_quantity, lost_quantity) < 0:
                raise ValueError("质检数量不能小于 0")
            if total != batch.submitted_quantity:
                raise ValueError("OK、返修、报废和遗失之和必须等于送检数量")

            if batch.qc_worker_id is None:
                raise ValueError("请先将送检批次分配给 QC 工人")

            qc_worker = session.get(Worker, batch.qc_worker_id)
            if (
                qc_worker is None
                or not qc_worker.active
                or qc_worker.department != "qc"
            ):
                raise ValueError("已分配的 QC 工人无效，请重新分配")

            item = (
                session.query(cls)
                .filter(cls.id == batch.work_order_id)
                .with_for_update()
                .one()
            )
            process = session.get(DepartmentProcess, item.process_id)

            batch.ok_quantity = ok_quantity
            batch.rework_quantity = rework_quantity
            batch.scrap_quantity = scrap_quantity
            batch.lost_quantity = lost_quantity
            batch.defect_reason = defect_reason
            batch.status = "completed"
            batch.inspected_by = inspected_by
            batch.inspected_at = datetime.now()
            session.flush()

            cls._apply_result(session, item, process, batch)
            cls._close_if_complete(session, item)
            session.commit()
            session.refresh(batch)
            return WorkOrderBatch.serialize(batch)

    @classmethod
    def assign_qc_worker(
        cls,
        batch_id: int,
        qc_worker_id: int,
        allowed_department: str,
    ) -> dict:
        if allowed_department not in {"sys", "qc"}:
            raise PermissionError("只有 QC 可以分配质检工人")

        with SessionLocal() as session:
            batch = (
                session.query(WorkOrderBatch)
                .filter(WorkOrderBatch.id == batch_id)
                .with_for_update()
                .one_or_none()
            )
            if batch is None:
                raise ValueError("送检批次不存在")
            if batch.status != "pending_qc":
                raise ValueError("该送检批次已经完成质检")

            qc_worker = session.get(Worker, qc_worker_id)
            if (
                qc_worker is None
                or not qc_worker.active
                or qc_worker.department != "qc"
            ):
                raise ValueError("请选择有效的 QC 工人")

            batch.qc_worker_id = qc_worker_id
            session.commit()
            session.refresh(batch)
            return cls._serialize_batch_in_session(session, batch)

    @classmethod
    def pending_qc(cls) -> list[dict]:
        with SessionLocal() as session:
            batches = (
                session.query(WorkOrderBatch)
                .filter(WorkOrderBatch.status == "pending_qc")
                .order_by(WorkOrderBatch.submitted_at.asc(), WorkOrderBatch.id.asc())
                .all()
            )
            result = []
            for batch in batches:
                item = session.get(cls, batch.work_order_id)
                process = session.get(DepartmentProcess, item.process_id)
                product = session.get(Product, item.product_id)
                worker = session.get(Worker, item.worker_id)
                data = cls._serialize_batch_in_session(session, batch)
                data.update(
                    {
                        "workOrderNo": item.work_order_no,
                        "orderId": product.order_id,
                        "zzCode": product.zz_code,
                        "productName": product.product_name,
                        "ownerDepartment": process.department,
                        "processName": process.process_name,
                        "workerName": worker.name,
                    }
                )
                result.append(data)
            return result

    @staticmethod
    def _ensure_department(department: str, allowed_department: str) -> None:
        if allowed_department not in {"sys", department}:
            raise PermissionError("无权操作其他部门工单")

    @staticmethod
    def _batches(session, work_order_id: int) -> list["WorkOrderBatch"]:
        return (
            session.query(WorkOrderBatch)
            .filter(WorkOrderBatch.work_order_id == work_order_id)
            .order_by(WorkOrderBatch.batch_no.asc())
            .all()
        )

    @classmethod
    def _processing_quantity(
        cls,
        item: "WorkOrder",
        batches: list["WorkOrderBatch"],
    ) -> int:
        totals = cls._totals(batches)
        return (
            item.issued_quantity
            + totals["reworkQuantity"]
            - totals["submittedQuantity"]
        )

    @classmethod
    def _close_if_complete(cls, session, item: "WorkOrder") -> None:
        batches = cls._batches(session, item.id)
        totals = cls._totals(batches)
        processing = cls._processing_quantity(item, batches)
        resolved = (
            totals["okQuantity"]
            + totals["scrapQuantity"]
            + totals["lostQuantity"]
        )
        if (
            processing == 0
            and totals["pendingQcQuantity"] == 0
            and resolved == item.issued_quantity
        ):
            item.status = "closed"
            item.closed_at = datetime.now()

    @classmethod
    def _apply_result(
        cls,
        session,
        item: "WorkOrder",
        process: DepartmentProcess,
        batch: "WorkOrderBatch",
    ) -> None:
        ok = batch.ok_quantity or 0
        scrap = batch.scrap_quantity or 0
        lost = batch.lost_quantity or 0

        repository = (
            session.query(Repository)
            .filter(
                Repository.product_id == item.product_id,
                Repository.department == process.department,
            )
            .with_for_update()
            .one_or_none()
        )
        if repository is None:
            raise ValueError("当前部门没有该产品库存")

        if repository.quantity < scrap + lost:
            raise ValueError("报废和遗失数量超过当前部门库存")
        repository.quantity -= scrap + lost

        next_process = (
            session.query(DepartmentProcess)
            .filter(
                DepartmentProcess.product_id == item.product_id,
                DepartmentProcess.department == process.department,
                DepartmentProcess.sequence_no > process.sequence_no,
            )
            .order_by(DepartmentProcess.sequence_no.asc())
            .with_for_update()
            .first()
        )
        if next_process is not None:
            next_process.available_quantity += ok
            return

        if repository.quantity < ok:
            raise ValueError("流转数量超过当前部门库存")
        repository.quantity -= ok
        target_department = cls._next_global_department(
            session,
            item.product_id,
            process.department,
        )
        target = (
            session.query(Repository)
            .filter(
                Repository.product_id == item.product_id,
                Repository.department == target_department,
            )
            .with_for_update()
            .one_or_none()
        )
        if target is None:
            target = Repository(
                product_id=item.product_id,
                department=target_department,
                quantity=0,
            )
            session.add(target)
        target.quantity += ok

        first_target_process = (
            session.query(DepartmentProcess)
            .filter(
                DepartmentProcess.product_id == item.product_id,
                DepartmentProcess.department == target_department,
            )
            .order_by(DepartmentProcess.sequence_no.asc())
            .with_for_update()
            .first()
        )
        if first_target_process is not None:
            first_target_process.available_quantity += ok

        if ok > 0:
            session.add(
                Record(
                    product_id=item.product_id,
                    from_repository=process.department,
                    to_repository=target_department,
                    quantity=ok,
                    note=f"工单 {item.work_order_no} 完成 {process.process_name}",
                )
            )

    @staticmethod
    def _next_global_department(
        session,
        product_id: int,
        current_department: str,
    ) -> str:
        steps = (
            session.query(ProductDepartmentStep)
            .filter(ProductDepartmentStep.product_id == product_id)
            .order_by(ProductDepartmentStep.sequence_no.asc())
            .all()
        )
        for index, step in enumerate(steps):
            if step.department == current_department:
                if index + 1 < len(steps):
                    return steps[index + 1].department
                return "out"
        raise ValueError("产品部门流程不包含当前部门")


class WorkOrderBatch(Base):
    __tablename__ = "work_order_batch"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    work_order_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("work_order.id"),
        nullable=False,
    )
    batch_no: Mapped[int] = mapped_column(Integer, nullable=False)
    submitted_quantity: Mapped[int] = mapped_column(Integer, nullable=False)
    ok_quantity: Mapped[int | None] = mapped_column(Integer, nullable=True)
    rework_quantity: Mapped[int | None] = mapped_column(Integer, nullable=True)
    scrap_quantity: Mapped[int | None] = mapped_column(Integer, nullable=True)
    lost_quantity: Mapped[int | None] = mapped_column(Integer, nullable=True)
    qc_worker_id: Mapped[int | None] = mapped_column(
        BigInteger,
        ForeignKey("worker.id"),
        nullable=True,
    )
    defect_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(Text, nullable=False)
    submitted_by: Mapped[int] = mapped_column(BigInteger, ForeignKey("users.id"), nullable=False)
    submitted_at: Mapped[datetime] = mapped_column(
        TIMESTAMP,
        nullable=False,
        server_default=text("NOW()"),
    )
    inspected_by: Mapped[int | None] = mapped_column(
        BigInteger,
        ForeignKey("users.id"),
        nullable=True,
    )
    inspected_at: Mapped[datetime | None] = mapped_column(TIMESTAMP, nullable=True)

    @staticmethod
    def serialize(batch: "WorkOrderBatch") -> dict:
        return {
            "id": batch.id,
            "workOrderId": batch.work_order_id,
            "batchNo": batch.batch_no,
            "submittedQuantity": batch.submitted_quantity,
            "okQuantity": batch.ok_quantity,
            "reworkQuantity": batch.rework_quantity,
            "scrapQuantity": batch.scrap_quantity,
            "lostQuantity": batch.lost_quantity,
            "qcWorkerId": batch.qc_worker_id,
            "defectReason": batch.defect_reason,
            "status": batch.status,
            "submittedAt": batch.submitted_at.strftime("%Y-%m-%d %H:%M"),
            "inspectedAt": (
                batch.inspected_at.strftime("%Y-%m-%d %H:%M")
                if batch.inspected_at
                else None
            ),
        }


class Record(Base):
    __tablename__ = "records"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    product_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("product.id", ondelete="CASCADE"),
        nullable=False,
    )
    from_repository: Mapped[str] = mapped_column(Text, nullable=False)
    to_repository: Mapped[str] = mapped_column(Text, nullable=False)
    quantity: Mapped[int] = mapped_column(Integer, nullable=False)
    note: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP,
        nullable=False,
        server_default=text("NOW()"),
    )

    @classmethod
    def list_by_product(
        cls,
        order_id: str,
        zz_code: str,
        product_name: str,
        department: str | None = None,
    ) -> list[dict]:
        with SessionLocal() as session:
            product = (
                session.query(Product)
                .filter(
                    Product.order_id == order_id,
                    Product.zz_code == zz_code,
                    Product.product_name == product_name,
                )
                .one_or_none()
            )
            if product is None:
                return []

            query = session.query(cls).filter(cls.product_id == product.id)
            if department:
                query = query.filter(
                    (cls.from_repository == department)
                    | (cls.to_repository == department)
                )
            records = query.order_by(cls.created_at.desc(), cls.id.desc()).all()
            return [
                {
                    "id": record.id,
                    "orderId": product.order_id,
                    "zzCode": product.zz_code,
                    "product": product.product_name,
                    "fromRepository": record.from_repository,
                    "toRepository": record.to_repository,
                    "quantity": record.quantity,
                    "note": record.note,
                    "createdAt": record.created_at.strftime("%Y-%m-%d %H:%M"),
                }
                for record in records
            ]
