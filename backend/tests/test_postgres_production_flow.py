import os
from datetime import date, timedelta
from decimal import Decimal
from uuid import uuid4

import pytest


pytestmark = pytest.mark.skipif(
    os.getenv("RUN_DATABASE_TESTS") != "1",
    reason="set RUN_DATABASE_TESTS=1 on a disposable PostgreSQL database",
)


def _seed_context():
    from sqlalchemy import select

    from database import SessionLocal
    from modules.engineering.persistence import Product
    from modules.organization.persistence import Procedure, Workshop
    from modules.sales.persistence import Customer
    from modules.standard_execution.persistence import ProcedureTag
    from modules.workforce.persistence import Worker

    with SessionLocal() as session:
        customer_id = session.scalar(
            select(Customer.id).where(Customer.customer_name == "示例客户")
        )
        product = session.scalar(
            select(Product).where(Product.factory_code == "DEMO-001")
        )
        procedure = session.scalar(
            select(Procedure)
            .join(Workshop, Workshop.id == Procedure.workshop_id)
            .where(
                Procedure.procedure_name == "粗光",
                Workshop.workshop_name == "手磨1车间",
            )
        )
        tag_names = list(
            session.scalars(
                select(ProcedureTag.tag_name)
                .where(ProcedureTag.procedure_id == procedure.id)
                .order_by(ProcedureTag.tag_name)
            )
        )
        workers = {
            name: worker_id
            for name, worker_id in session.execute(
                select(Worker.worker_name, Worker.id).where(
                    Worker.worker_name.in_(
                        {
                            "表面处理示例工人",
                            "QC示例工人",
                            "装配示例工人",
                        }
                    )
                )
            )
        }
    assert customer_id is not None
    assert product is not None
    assert procedure is not None
    assert tag_names
    assert len(workers) == 3
    return customer_id, product, procedure, tag_names, workers


def _order_repositories(order_id: int, flow_node_id: str):
    from sqlalchemy import select

    from database import SessionLocal
    from modules.production_core.persistence import ProductionItem, Repository
    from modules.sales.persistence import CustomerOrderItem

    with SessionLocal() as session:
        return list(
            session.scalars(
                select(Repository)
                .join(
                    ProductionItem,
                    ProductionItem.id == Repository.production_item_id,
                )
                .join(
                    CustomerOrderItem,
                    CustomerOrderItem.id
                    == ProductionItem.customer_order_item_id,
                )
                .where(
                    CustomerOrderItem.customer_order_id == order_id,
                    Repository.flow_node_id == flow_node_id,
                )
                .order_by(Repository.id)
            )
        )


def test_full_standard_qc_assembly_qc_flow_closes_customer_order():
    from departments.contracts import (
        CAP_ASSEMBLY,
        CAP_QUALITY,
        CAP_STANDARD_EXECUTION,
    )
    from departments.registry import department_api
    from modules.production_core.api import submit_work_order
    from modules.sales.api import change_status, create_order, get_order
    from modules.standard_execution.api import update_procedure_tag_prices
    from schemas.procedure_tag_prices import (
        ProcedureTagPriceInput,
        ProcedureTagPriceUpdate,
    )
    from schemas.production import QcInspection
    from schemas.sales import CustomerOrderCreate, CustomerOrderItemInput

    customer_id, product, procedure, tag_names, workers = _seed_context()
    update_procedure_tag_prices(
        "polish",
        product.id,
        product.version,
        "demo-part-body",
        procedure.id,
        ProcedureTagPriceUpdate(
            tags=[
                ProcedureTagPriceInput(
                    tag_name=name,
                    unit_price=Decimal("1.00"),
                )
                for name in tag_names
            ]
        ),
        "sys",
    )

    order = create_order(
        CustomerOrderCreate(
            customer_order_no=f"IT-{uuid4().hex}",
            customer_id=customer_id,
            items=[
                CustomerOrderItemInput(
                    product_id=product.id,
                    quantity=2,
                    delivery_date=date.today() + timedelta(days=7),
                )
            ],
        )
    )
    order = change_status(order["id"], "confirmed", order["revision"])
    assert order["status"] == "confirmed"

    polish_repository = _order_repositories(
        order["id"],
        "demo-process-polish",
    )
    assert len(polish_repository) == 1
    polish_api = department_api("polish", CAP_STANDARD_EXECUTION)
    polish_order = polish_api.create_source_work_order(
        polish_repository[0].id,
        None,
        tag_names,
        2,
        workers["表面处理示例工人"],
        "integration test",
    )
    submitted = submit_work_order(
        polish_order["id"],
        2,
        "qc",
        "polish",
        "integration-test",
    )
    polish_batch_id = submitted["batches"][0]["id"]

    qc_api = department_api("qc", CAP_QUALITY)
    qc_api.inspect_qc_batch(
        polish_batch_id,
        QcInspection(
            qc_worker_id=workers["QC示例工人"],
            qualified_quantity=2,
            rework_quantity=0,
            scrap_quantity=0,
            lost_quantity=0,
        ),
        "qc",
    )
    qc_api.dispatch_qc_batch(polish_batch_id, 2, "qc")

    assembly_repositories = _order_repositories(
        order["id"],
        "demo-assembly-body-spring",
    )
    assert len(assembly_repositories) == 2
    assembly_api = department_api("assembly", CAP_ASSEMBLY)
    assembly_order = assembly_api.create_assembly_work_order(
        [item.id for item in assembly_repositories],
        2,
        workers["装配示例工人"],
        "integration test",
        "assembly",
    )
    submitted = submit_work_order(
        assembly_order["id"],
        2,
        "qc",
        "assembly",
        "integration-test",
    )
    assembly_batch_id = submitted["batches"][0]["id"]
    qc_api.inspect_qc_batch(
        assembly_batch_id,
        QcInspection(
            qc_worker_id=workers["QC示例工人"],
            qualified_quantity=2,
            rework_quantity=0,
            scrap_quantity=0,
            lost_quantity=0,
        ),
        "qc",
    )
    dispatch = qc_api.dispatch_qc_batch(assembly_batch_id, 2, "qc")

    assert dispatch["remaining_quantity"] == 0
    assert get_order(order["id"])["status"] == "closed"


def test_failed_order_creation_rolls_back_everything():
    from sqlalchemy import func, select

    from database import SessionLocal
    from modules.errors import DomainError
    from modules.sales.api import create_order
    from modules.sales.persistence import Customer, CustomerOrder
    from schemas.sales import CustomerOrderCreate, CustomerOrderItemInput

    order_no = f"IT-ROLLBACK-{uuid4().hex}"
    with SessionLocal() as session:
        customer_id = session.scalar(
            select(Customer.id).where(Customer.customer_name == "示例客户")
        )

    with pytest.raises(DomainError):
        create_order(
            CustomerOrderCreate(
                customer_order_no=order_no,
                customer_id=customer_id,
                items=[
                    CustomerOrderItemInput(
                        product_id=2**62,
                        quantity=1,
                        delivery_date=date.today() + timedelta(days=1),
                    )
                ],
            )
        )

    with SessionLocal() as session:
        count = session.scalar(
            select(func.count(CustomerOrder.id)).where(
                CustomerOrder.customer_order_no == order_no
            )
        )
    assert count == 0
