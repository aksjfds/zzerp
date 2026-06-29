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
from sqlalchemy.dialects.postgresql import ARRAY
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
        if "qc" in process:
            raise ValueError("QC 不能作为产品正式部门流程")
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

    @classmethod
    def department_progress(cls, product_id: int, department: str) -> dict:
        with SessionLocal() as session:
            product = session.get(cls, product_id)
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
            if belongs_to_route is None and department != "out":
                raise ValueError("产品流程不包含该部门")

            entered_quantity = sum(
                record.quantity
                for record in session.query(Record)
                .filter(
                    Record.product_id == product_id,
                    Record.to_repository == department,
                )
                .all()
            )
            repository = (
                session.query(Repository)
                .filter(
                    Repository.product_id == product_id,
                    Repository.department == department,
                )
                .one_or_none()
            )
            current_quantity = repository.quantity if repository else 0
            route = session.query(PolishProcess).filter(
                PolishProcess.product_id == product_id,
            ).one_or_none() if department == "polish" else None
            processes = PolishProcess.parse_flow(route.process_flow) if route else []

            process_items = []
            for index, process in enumerate(processes, start=1):
                work_orders = (
                    session.query(WorkOrder)
                    .filter(
                        WorkOrder.product_id == product_id,
                        WorkOrder.department == department,
                        WorkOrder.process_name == process["processName"],
                    )
                    .all()
                )
                issued_quantity = sum(item.issued_quantity for item in work_orders)
                processing_quantity = 0
                pending_qc_quantity = 0
                cleaning_quantity = 0
                cleaned_ready_quantity = 0
                ok_quantity = 0
                rework_quantity = 0
                scrap_quantity = 0
                lost_quantity = 0

                for item in work_orders:
                    batches = WorkOrder._batches(session, item.id)
                    totals = WorkOrder._totals(batches)
                    processing_quantity += WorkOrder._processing_quantity(item, batches, session)
                    cleaning_batches = WorkOrder._cleaning_batches(session, item.id)
                    cleaning_quantity += sum(
                        cleaning.quantity
                        for cleaning in cleaning_batches
                        if cleaning.status == "cleaning"
                    )
                    if process["requiresCleaning"]:
                        cleaned_ready_quantity += max(
                            0,
                            sum(
                                cleaning.quantity
                                for cleaning in cleaning_batches
                                if cleaning.status == "completed"
                            ) - totals["submittedQuantity"],
                        )
                    pending_qc_quantity += totals["pendingQcQuantity"]
                    ok_quantity += totals["okQuantity"]
                    rework_quantity += totals["reworkQuantity"]
                    scrap_quantity += totals["scrapQuantity"]
                    lost_quantity += totals["lostQuantity"]

                progress = (
                    min(100, round(ok_quantity * 100 / entered_quantity, 1))
                    if entered_quantity > 0
                    else 0
                )
                process_items.append(
                    {
                        "id": index,
                        "sequenceNo": index,
                        "processName": process["processName"],
                        "requiresCleaning": process["requiresCleaning"],
                        "requiresQc": process["requiresQc"],
                        "waitingQuantity": WorkOrder._available_for_process_in_session(
                            session,
                            route,
                            process["processName"],
                        ),
                        "issuedQuantity": issued_quantity,
                        "processingQuantity": processing_quantity,
                        "cleaningQuantity": cleaning_quantity,
                        "cleanedReadyQuantity": cleaned_ready_quantity,
                        "pendingQcQuantity": pending_qc_quantity,
                        "okQuantity": ok_quantity,
                        "reworkQuantity": rework_quantity,
                        "scrapQuantity": scrap_quantity,
                        "lostQuantity": lost_quantity,
                        "progress": progress,
                    }
                )

            return {
                "productId": product.id,
                "orderId": product.order_id,
                "zzCode": product.zz_code,
                "productName": product.product_name,
                "department": department,
                "enteredQuantity": entered_quantity,
                "currentQuantity": current_quantity,
                "processes": process_items,
            }


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


class PolishProcessPreset(Base):
    __tablename__ = "polish_process_preset"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    preset_name: Mapped[str] = mapped_column(Text, nullable=False, unique=True)
    process_flow: Mapped[list[str]] = mapped_column(ARRAY(Text), nullable=False)
    active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP,
        nullable=False,
        server_default=text("NOW()"),
    )
    updated_at: Mapped[datetime] = mapped_column(
        TIMESTAMP,
        nullable=False,
        server_default=text("NOW()"),
    )

    @staticmethod
    def serialize(item: "PolishProcessPreset") -> dict:
        return {
            "id": item.id,
            "presetName": item.preset_name,
            "processFlow": item.process_flow,
            "steps": PolishProcess.parse_flow(item.process_flow),
            "active": item.active,
        }

    @classmethod
    def list_all(cls) -> list[dict]:
        with SessionLocal() as session:
            items = session.query(cls).order_by(cls.preset_name.asc()).all()
            return [cls.serialize(item) for item in items]

    @classmethod
    def save(
        cls,
        preset_name: str,
        steps: list[dict],
        preset_id: int | None = None,
        active: bool = True,
    ) -> dict:
        name = preset_name.strip()
        if not name:
            raise ValueError("预设名称不能为空")
        process_flow = PolishProcess.encode_steps(steps)
        with SessionLocal() as session:
            duplicate = session.query(cls).filter(cls.preset_name == name)
            if preset_id is not None:
                duplicate = duplicate.filter(cls.id != preset_id)
            if duplicate.first() is not None:
                raise ValueError("预设名称已存在")
            item = session.get(cls, preset_id) if preset_id else None
            if preset_id and item is None:
                raise ValueError("预设不存在")
            if item is None:
                item = cls(preset_name=name, process_flow=process_flow, active=active)
                session.add(item)
            else:
                item.preset_name = name
                item.process_flow = process_flow
                item.active = active
                item.updated_at = datetime.now()
            session.commit()
            session.refresh(item)
            return cls.serialize(item)


class PolishProcess(Base):
    __tablename__ = "polish_process"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    product_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("product.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
    )
    preset_id: Mapped[int | None] = mapped_column(
        BigInteger,
        ForeignKey("polish_process_preset.id", ondelete="SET NULL"),
        nullable=True,
    )
    process_flow: Mapped[list[str]] = mapped_column(ARRAY(Text), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP,
        nullable=False,
        server_default=text("NOW()"),
    )

    @staticmethod
    def parse_token(token: str) -> dict:
        parts = [part.strip() for part in token.split("-")]
        if not parts or not parts[0]:
            raise ValueError("工艺名称不能为空")
        name = parts[0]
        if name in {"清洗", "QC"}:
            raise ValueError("清洗和 QC 不能作为独立工艺")
        modifiers = parts[1:]
        if modifiers not in ([], ["清洗"], ["QC"], ["清洗", "QC"]):
            raise ValueError("工艺附加流程只允许按 清洗、QC 顺序配置")
        return {
            "processName": name,
            "requiresCleaning": "清洗" in modifiers,
            "requiresQc": "QC" in modifiers,
        }

    @classmethod
    def parse_flow(cls, process_flow: list[str]) -> list[dict]:
        steps = [cls.parse_token(token) for token in process_flow]
        names = [step["processName"] for step in steps]
        if not steps:
            raise ValueError("至少需要一道磨房工艺")
        if len(set(names)) != len(names):
            raise ValueError("同一路线不能包含重复工艺")
        return steps

    @classmethod
    def encode_steps(cls, steps: list[dict]) -> list[str]:
        process_flow = []
        for step in steps:
            name = str(step["process_name"]).strip()
            if not name or "-" in name:
                raise ValueError("工艺名称不能为空且不能包含 -")
            token = name
            if bool(step.get("requires_cleaning")):
                token += "-清洗"
            if bool(step.get("requires_qc")):
                token += "-QC"
            process_flow.append(token)
        cls.parse_flow(process_flow)
        return process_flow

    @classmethod
    def list_by_department(cls, department: str) -> list[dict]:
        if department != "polish":
            return []
        with SessionLocal() as session:
            routes = session.query(cls).order_by(cls.product_id.asc()).all()
            result = []
            for route in routes:
                for index, step in enumerate(cls.parse_flow(route.process_flow), start=1):
                    result.append(
                        {
                            "productId": route.product_id,
                            "department": "polish",
                            "sequenceNo": index,
                            **step,
                            "availableQuantity": WorkOrder._available_for_process_in_session(
                                session,
                                route,
                                step["processName"],
                            ),
                        }
                    )
            return result

    @classmethod
    def configure(
        cls,
        product_id: int,
        department: str,
        steps: list[dict],
        preset_id: int | None = None,
    ) -> list[dict]:
        if department != "polish":
            raise ValueError("当前只支持配置磨房工艺")
        process_flow = cls.encode_steps(steps)
        with SessionLocal() as session:
            product = session.get(Product, product_id)
            if product is None:
                raise ValueError("产品不存在")
            belongs_to_route = session.query(ProductDepartmentStep).filter(
                ProductDepartmentStep.product_id == product_id,
                ProductDepartmentStep.department == "polish",
            ).first()
            if belongs_to_route is None:
                raise ValueError("产品流程不包含磨房")
            if session.query(WorkOrder).filter(
                WorkOrder.product_id == product_id,
                WorkOrder.department == "polish",
            ).first() is not None:
                raise ValueError("已有工单，不能修改磨房工艺")
            if preset_id is not None:
                preset = session.get(PolishProcessPreset, preset_id)
                if preset is None or not preset.active:
                    raise ValueError("预设不存在或已停用")
            route = session.query(cls).filter(cls.product_id == product_id).one_or_none()
            if route is None:
                route = cls(product_id=product_id, preset_id=preset_id, process_flow=process_flow)
                session.add(route)
            else:
                route.preset_id = preset_id
                route.process_flow = process_flow
            session.commit()
        return cls.list_by_department("polish")


class WorkOrder(Base):
    __tablename__ = "work_order"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    work_order_no: Mapped[str | None] = mapped_column(Text, unique=True, nullable=True)
    product_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("product.id"), nullable=False)
    department: Mapped[str] = mapped_column(Text, nullable=False)
    process_name: Mapped[str] = mapped_column(Text, nullable=False)
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
        process = cls._process_step_in_session(session, item)
        worker = session.get(Worker, item.worker_id)
        batches = (
            session.query(WorkOrderBatch)
            .filter(WorkOrderBatch.work_order_id == item.id)
            .order_by(WorkOrderBatch.batch_no.asc())
            .all()
        )
        totals = cls._totals(batches)
        processing = (
            cls._processing_quantity(item, batches, session)
        )
        cleaning_batches = cls._cleaning_batches(session, item.id)
        cleaning_quantity = sum(
            batch.quantity for batch in cleaning_batches if batch.status == "cleaning"
        )
        cleaned_quantity = sum(
            batch.quantity for batch in cleaning_batches if batch.status == "completed"
        )
        cleaned_ready_quantity = (
            cleaned_quantity - totals["submittedQuantity"]
            if process["requiresCleaning"]
            else 0
        )
        return {
            "id": item.id,
            "workOrderNo": item.work_order_no,
            "productId": item.product_id,
            "orderId": product.order_id,
            "zzCode": product.zz_code,
            "productName": product.product_name,
            "processName": item.process_name,
            "department": item.department,
            "requiresCleaning": process["requiresCleaning"],
            "requiresQc": process["requiresQc"],
            "workerId": item.worker_id,
            "workerName": worker.name,
            "issuedQuantity": item.issued_quantity,
            "processingQuantity": processing,
            "cleaningQuantity": cleaning_quantity,
            "cleanedReadyQuantity": max(0, cleaned_ready_quantity),
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
            "cleaningBatches": [
                PolishCleaningBatch.serialize(batch) for batch in cleaning_batches
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
                .filter(cls.department == department)
                .order_by(cls.created_at.desc(), cls.id.desc())
                .all()
            )
            return [cls._serialize_in_session(session, item) for item in items]

    @classmethod
    def worker_overview(
        cls,
        start_date: date,
        end_date: date,
        worker_id: int | None = None,
        product_id: int | None = None,
        process_name: str | None = None,
    ) -> list[dict]:
        start_at = datetime.combine(start_date, datetime.min.time())
        end_at = datetime.combine(end_date, datetime.max.time())
        with SessionLocal() as session:
            worker_query = session.query(Worker).filter(
                Worker.department == "polish",
            )
            if worker_id is not None:
                worker_query = worker_query.filter(Worker.id == worker_id)
            workers = worker_query.order_by(Worker.name.asc()).all()

            order_query = session.query(cls).filter(
                cls.department == "polish",
                cls.status == "closed",
                cls.closed_at >= start_at,
                cls.closed_at <= end_at,
            )
            if worker_id is not None:
                order_query = order_query.filter(cls.worker_id == worker_id)
            if product_id is not None:
                order_query = order_query.filter(cls.product_id == product_id)
            if process_name:
                order_query = order_query.filter(cls.process_name == process_name)
            orders = order_query.order_by(cls.closed_at.desc(), cls.id.desc()).all()

            product_ids = {item.product_id for item in orders}
            products = (
                session.query(Product).filter(Product.id.in_(product_ids)).all()
                if product_ids
                else []
            )
            product_map = {item.id: item for item in products}

            order_ids = {item.id for item in orders}
            batches = (
                session.query(WorkOrderBatch)
                .filter(WorkOrderBatch.work_order_id.in_(order_ids))
                .order_by(WorkOrderBatch.batch_no.asc())
                .all()
                if order_ids
                else []
            )
            batch_map: dict[int, list[WorkOrderBatch]] = {}
            for batch in batches:
                batch_map.setdefault(batch.work_order_id, []).append(batch)

            order_map: dict[int, list[WorkOrder]] = {}
            for item in orders:
                order_map.setdefault(item.worker_id, []).append(item)

            result = []
            for worker in workers:
                order_items = []
                issued_total = 0
                ok_total = 0
                scrap_total = 0
                lost_total = 0
                for item in order_map.get(worker.id, []):
                    product = product_map[item.product_id]
                    totals = cls._totals(batch_map.get(item.id, []))
                    issued_total += item.issued_quantity
                    ok_total += totals["okQuantity"]
                    scrap_total += totals["scrapQuantity"]
                    lost_total += totals["lostQuantity"]
                    denominator = item.issued_quantity or 1
                    order_items.append(
                        {
                            "id": item.id,
                            "workOrderNo": item.work_order_no,
                            "productId": item.product_id,
                            "orderId": product.order_id,
                            "zzCode": product.zz_code,
                            "productName": product.product_name,
                            "processName": item.process_name,
                            "issuedQuantity": item.issued_quantity,
                            "okQuantity": totals["okQuantity"],
                            "scrapQuantity": totals["scrapQuantity"],
                            "lostQuantity": totals["lostQuantity"],
                            "completionRate": round(
                                totals["okQuantity"] * 100 / denominator,
                                2,
                            ),
                            "scrapRate": round(
                                totals["scrapQuantity"] * 100 / denominator,
                                2,
                            ),
                            "lostRate": round(
                                totals["lostQuantity"] * 100 / denominator,
                                2,
                            ),
                            "closedAt": item.closed_at.strftime("%Y-%m-%d %H:%M"),
                        }
                    )

                denominator = issued_total or 1
                result.append(
                    {
                        "workerId": worker.id,
                        "workerName": worker.name,
                        "workOrderCount": len(order_items),
                        "issuedQuantity": issued_total,
                        "okQuantity": ok_total,
                        "scrapQuantity": scrap_total,
                        "lostQuantity": lost_total,
                        "completionRate": round(ok_total * 100 / denominator, 2),
                        "scrapRate": round(scrap_total * 100 / denominator, 2),
                        "lostRate": round(lost_total * 100 / denominator, 2),
                        "orders": order_items,
                    }
                )
            return result

    @classmethod
    def _route_in_session(cls, session, product_id: int) -> PolishProcess:
        route = session.query(PolishProcess).filter(
            PolishProcess.product_id == product_id,
        ).one_or_none()
        if route is None:
            raise ValueError("产品尚未配置磨房工艺")
        return route

    @classmethod
    def _process_step_in_session(cls, session, item: "WorkOrder") -> dict:
        route = cls._route_in_session(session, item.product_id)
        step = next(
            (
                current
                for current in PolishProcess.parse_flow(route.process_flow)
                if current["processName"] == item.process_name
            ),
            None,
        )
        if step is None:
            raise ValueError("工单对应的磨房工艺不存在")
        return step

    @classmethod
    def _process_ok_in_session(cls, session, product_id: int, process_name: str) -> int:
        items = session.query(cls).filter(
            cls.product_id == product_id,
            cls.department == "polish",
            cls.process_name == process_name,
        ).all()
        return sum(
            cls._totals(cls._batches(session, item.id))["okQuantity"]
            for item in items
        )

    @classmethod
    def _available_for_process_in_session(
        cls,
        session,
        route: PolishProcess,
        process_name: str,
    ) -> int:
        steps = PolishProcess.parse_flow(route.process_flow)
        names = [step["processName"] for step in steps]
        if process_name not in names:
            raise ValueError("产品工艺不存在")
        index = names.index(process_name)
        if index == 0:
            input_quantity = sum(
                record.quantity
                for record in session.query(Record).filter(
                    Record.product_id == route.product_id,
                    Record.to_repository == "polish",
                ).all()
            )
        else:
            input_quantity = cls._process_ok_in_session(
                session,
                route.product_id,
                names[index - 1],
            )
        issued = sum(
            item.issued_quantity
            for item in session.query(cls).filter(
                cls.product_id == route.product_id,
                cls.department == "polish",
                cls.process_name == process_name,
            ).all()
        )
        return max(0, input_quantity - issued)

    @staticmethod
    def _cleaning_batches(session, work_order_id: int) -> list["PolishCleaningBatch"]:
        return session.query(PolishCleaningBatch).filter(
            PolishCleaningBatch.work_order_id == work_order_id,
        ).order_by(PolishCleaningBatch.batch_no.asc()).all()

    @classmethod
    def create(
        cls,
        product_id: int,
        department: str,
        process_name: str,
        worker_id: int,
        issued_quantity: int,
        created_by: int,
        allowed_department: str,
        note: str | None,
    ) -> dict:
        if issued_quantity <= 0:
            raise ValueError("领取数量必须大于 0")

        with SessionLocal() as session:
            if department != "polish":
                raise ValueError("当前只支持磨房工单")
            route = (
                session.query(PolishProcess)
                .filter(PolishProcess.product_id == product_id)
                .with_for_update()
                .one_or_none()
            )
            if route is None:
                raise ValueError("产品工艺不存在")
            cls._ensure_department(department, allowed_department)
            process = next(
                (
                    step
                    for step in PolishProcess.parse_flow(route.process_flow)
                    if step["processName"] == process_name
                ),
                None,
            )
            if process is None:
                raise ValueError("产品工艺不存在")
            available = cls._available_for_process_in_session(session, route, process_name)
            if available < issued_quantity:
                raise ValueError("领取数量超过当前工艺可开单数量")

            worker = session.get(Worker, worker_id)
            if worker is None or not worker.active:
                raise ValueError("工人不存在或已停用")
            if worker.department != department:
                raise ValueError("工人与工艺部门不一致")

            item = cls(
                product_id=product_id,
                department=department,
                process_name=process_name,
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
            process = cls._process_step_in_session(session, item)
            cls._ensure_department(item.department, allowed_department)
            if item.status != "open":
                raise ValueError("工单已经结单")
            if not process["requiresQc"]:
                raise ValueError("当前工艺不需要 QC")

            batches = cls._batches(session, item.id)
            available = cls._downstream_ready_quantity(session, item, process, batches)
            if quantity > available:
                raise ValueError("送检数量超过当前可送检数量")

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
            process = cls._process_step_in_session(session, item)
            cls._ensure_department(item.department, allowed_department)
            if item.status != "open":
                raise ValueError("工单已经结单")
            if process["requiresQc"]:
                raise ValueError("当前工艺必须由 QC 录入结果")

            batches = cls._batches(session, item.id)
            available = cls._downstream_ready_quantity(session, item, process, batches)
            if submitted_quantity > available:
                raise ValueError("报工数量超过当前可报工数量")

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
            process = cls._process_step_in_session(session, item)

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
                product = session.get(Product, item.product_id)
                worker = session.get(Worker, item.worker_id)
                data = cls._serialize_batch_in_session(session, batch)
                data.update(
                    {
                        "workOrderNo": item.work_order_no,
                        "orderId": product.order_id,
                        "zzCode": product.zz_code,
                        "productName": product.product_name,
                        "ownerDepartment": item.department,
                        "processName": item.process_name,
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
        session=None,
    ) -> int:
        totals = cls._totals(batches)
        if session is not None:
            process = cls._process_step_in_session(session, item)
            if process["requiresCleaning"]:
                sent_cleaning = sum(
                    batch.quantity for batch in cls._cleaning_batches(session, item.id)
                )
                return item.issued_quantity + totals["reworkQuantity"] - sent_cleaning
        return (
            item.issued_quantity
            + totals["reworkQuantity"]
            - totals["submittedQuantity"]
        )

    @classmethod
    def _downstream_ready_quantity(
        cls,
        session,
        item: "WorkOrder",
        process: dict,
        batches: list["WorkOrderBatch"],
    ) -> int:
        if not process["requiresCleaning"]:
            return cls._processing_quantity(item, batches, session)
        cleaned = sum(
            batch.quantity
            for batch in cls._cleaning_batches(session, item.id)
            if batch.status == "completed"
        )
        return max(0, cleaned - cls._totals(batches)["submittedQuantity"])

    @classmethod
    def create_cleaning_submission(
        cls,
        work_order_id: int,
        quantity: int,
        sent_by: int,
        allowed_department: str,
    ) -> dict:
        if quantity <= 0:
            raise ValueError("送洗数量必须大于 0")
        with SessionLocal() as session:
            item = session.query(cls).filter(cls.id == work_order_id).with_for_update().one_or_none()
            if item is None:
                raise ValueError("工单不存在")
            cls._ensure_department(item.department, allowed_department)
            process = cls._process_step_in_session(session, item)
            if not process["requiresCleaning"]:
                raise ValueError("当前工艺不需要清洗")
            if item.status != "open":
                raise ValueError("工单已经结单")
            processing = cls._processing_quantity(item, cls._batches(session, item.id), session)
            if quantity > processing:
                raise ValueError("送洗数量超过当前加工中数量")
            cleaning_batches = cls._cleaning_batches(session, item.id)
            batch = PolishCleaningBatch(
                work_order_id=item.id,
                batch_no=len(cleaning_batches) + 1,
                quantity=quantity,
                status="cleaning",
                sent_by=sent_by,
            )
            session.add(batch)
            session.commit()
            session.refresh(batch)
            return PolishCleaningBatch.serialize(batch)

    @classmethod
    def complete_cleaning_submission(
        cls,
        cleaning_batch_id: int,
        completed_by: int,
        allowed_department: str,
    ) -> dict:
        with SessionLocal() as session:
            batch = session.query(PolishCleaningBatch).filter(
                PolishCleaningBatch.id == cleaning_batch_id,
            ).with_for_update().one_or_none()
            if batch is None:
                raise ValueError("清洗批次不存在")
            item = session.get(cls, batch.work_order_id)
            cls._ensure_department(item.department, allowed_department)
            if batch.status != "cleaning":
                raise ValueError("该清洗批次已经完成")
            batch.status = "completed"
            batch.completed_by = completed_by
            batch.completed_at = datetime.now()
            session.commit()
            session.refresh(batch)
            return PolishCleaningBatch.serialize(batch)

    @classmethod
    def _close_if_complete(cls, session, item: "WorkOrder") -> None:
        batches = cls._batches(session, item.id)
        totals = cls._totals(batches)
        processing = cls._processing_quantity(item, batches, session)
        process = cls._process_step_in_session(session, item)
        cleaning_batches = cls._cleaning_batches(session, item.id)
        cleaning = sum(batch.quantity for batch in cleaning_batches if batch.status == "cleaning")
        ready = cls._downstream_ready_quantity(session, item, process, batches)
        resolved = (
            totals["okQuantity"]
            + totals["scrapQuantity"]
            + totals["lostQuantity"]
        )
        if (
            processing == 0
            and cleaning == 0
            and ready == 0
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
        process: dict,
        batch: "WorkOrderBatch",
    ) -> None:
        ok = batch.ok_quantity or 0
        scrap = batch.scrap_quantity or 0
        lost = batch.lost_quantity or 0

        repository = (
            session.query(Repository)
            .filter(
                Repository.product_id == item.product_id,
                Repository.department == item.department,
            )
            .with_for_update()
            .one_or_none()
        )
        if repository is None:
            raise ValueError("当前部门没有该产品库存")

        if repository.quantity < scrap + lost:
            raise ValueError("报废和遗失数量超过当前部门库存")
        repository.quantity -= scrap + lost

        route = cls._route_in_session(session, item.product_id)
        process_names = [
            step["processName"] for step in PolishProcess.parse_flow(route.process_flow)
        ]
        current_index = process_names.index(item.process_name)
        if current_index + 1 < len(process_names):
            return

        if repository.quantity < ok:
            raise ValueError("流转数量超过当前部门库存")
        repository.quantity -= ok
        target_department = cls._next_global_department(
            session,
            item.product_id,
            item.department,
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

        if ok > 0:
            session.add(
                Record(
                    product_id=item.product_id,
                    from_repository=item.department,
                    to_repository=target_department,
                    quantity=ok,
                    note=f"工单 {item.work_order_no} 完成 {item.process_name}",
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


class PolishCleaningBatch(Base):
    __tablename__ = "polish_cleaning_batch"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    work_order_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("work_order.id"),
        nullable=False,
    )
    batch_no: Mapped[int] = mapped_column(Integer, nullable=False)
    quantity: Mapped[int] = mapped_column(Integer, nullable=False)
    status: Mapped[str] = mapped_column(Text, nullable=False)
    sent_by: Mapped[int] = mapped_column(BigInteger, ForeignKey("users.id"), nullable=False)
    sent_at: Mapped[datetime] = mapped_column(
        TIMESTAMP,
        nullable=False,
        server_default=text("NOW()"),
    )
    completed_by: Mapped[int | None] = mapped_column(
        BigInteger,
        ForeignKey("users.id"),
        nullable=True,
    )
    completed_at: Mapped[datetime | None] = mapped_column(TIMESTAMP, nullable=True)

    @staticmethod
    def serialize(batch: "PolishCleaningBatch") -> dict:
        return {
            "id": batch.id,
            "workOrderId": batch.work_order_id,
            "batchNo": batch.batch_no,
            "quantity": batch.quantity,
            "status": batch.status,
            "sentAt": batch.sent_at.strftime("%Y-%m-%d %H:%M"),
            "completedAt": (
                batch.completed_at.strftime("%Y-%m-%d %H:%M")
                if batch.completed_at
                else None
            ),
        }


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
