"""Destructive-database smoke test for the v6 planning and inventory lifecycle.

Run only after rebuilding the configured development database from zzerp.sql.
The script intentionally creates orders and inventory records in that database.
"""

from __future__ import annotations

from datetime import date
import os
from pathlib import Path
import sys


ROOT_DIR = Path(__file__).resolve().parents[1]
BACKEND_SRC = ROOT_DIR / "backend" / "src"
os.environ.setdefault("APP_ENV", "development")
sys.path.insert(0, str(BACKEND_SRC))
sys.path.insert(0, str(ROOT_DIR))

if os.getenv("ALLOW_FULL_FLOW_VALIDATION") != "yes":
    raise RuntimeError(
        "Full-flow validation refused. Set ALLOW_FULL_FLOW_VALIDATION=yes explicitly."
    )

from sqlalchemy import func, select  # noqa: E402

from database import SessionLocal  # noqa: E402
from modules.inventory.api import (  # noqa: E402
    confirm_receipt,
    issue_outbound_plan,
    list_outbound_plans,
)
from modules.inventory.finished_goods_api import (  # noqa: E402
    confirm_finished_order_receipt,
    register_pending_finished_goods,
    ship_finished_order_item,
)
from modules.inventory.identity import inventory_identity_key  # noqa: E402
from modules.inventory.model_api import (  # noqa: E402
    FinishedOrderStock,
    InventoryReceipt,
    InventoryStock,
)
from modules.inventory.ownership_api import create_receipt  # noqa: E402
from modules.planning.api import get_order_plan, update_order_plan  # noqa: E402
from modules.production_core.model_api import (  # noqa: E402
    ProductionItem,
    ProductionMovement,
    Repository,
)
from modules.sales.model_api import Customer, CustomerOrder, CustomerOrderItem  # noqa: E402
from modules.sales.orders import (  # noqa: E402
    change_status,
    confirm_production_plan,
    create_order,
)
from schemas.sales import CustomerOrderCreate, CustomerOrderItemInput  # noqa: E402


ACTOR = "admin"


def require(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def create_planned_order(order_no: str, quantity: int) -> dict:
    with SessionLocal() as session:
        customer_id = session.scalar(
            select(Customer.id).where(Customer.customer_name == "示例客户")
        )
        product_id = session.scalar(
            select(CustomerOrderItem.product_id)
            .join(CustomerOrder, CustomerOrder.id == CustomerOrderItem.customer_order_id)
            .limit(1)
        )
        if product_id is None:
            from modules.engineering.model_api import Product

            product_id = session.scalar(
                select(Product.id).where(Product.factory_code == "DEMO-001")
            )
    require(customer_id is not None and product_id is not None, "示例产品种子数据缺失")
    order = create_order(CustomerOrderCreate(
        customer_order_no=order_no,
        customer_id=customer_id,
        remark="v6 全流程验证",
        items=[CustomerOrderItemInput(
            product_id=product_id,
            quantity=quantity,
            delivery_date=date.today(),
            remark=None,
        )],
    ))
    order = change_status(
        order["id"],
        "confirmed",
        order["revision"],
        actor_username=ACTOR,
    )
    plan = get_order_plan(order["id"])
    plan = update_order_plan(
        order["id"],
        plan["revision"],
        {item["id"]: item["net_required_quantity"] for item in plan["items"]},
    )
    return confirm_production_plan(
        order["id"],
        order["revision"],
        plan["revision"],
        actor_username=ACTOR,
    )


def outbound_plan(department_code: str, customer_order_id: int) -> dict:
    plan = next(
        (
            item for item in list_outbound_plans(department_code)
            if item["customer_order_id"] == customer_order_id
        ),
        None,
    )
    require(plan is not None, f"{department_code} 未生成待出库计划")
    return plan


def assert_order_closed(order_id: int) -> None:
    with SessionLocal() as session:
        status = session.scalar(
            select(CustomerOrder.status).where(CustomerOrder.id == order_id)
        )
    require(status == "closed", f"订单 {order_id} 未自动结单，当前状态：{status}")


def main() -> None:
    with SessionLocal() as session:
        require(
            session.scalar(select(func.count(InventoryStock.id))) == 0,
            "验证要求使用刚由 zzerp.sql 重建、尚无库存的数据库",
        )

    # A：生产 7、需求 5；验证成品待入库、入库、发货、结单和 2 件结余。
    order_a = create_planned_order("FLOW-A", 5)
    with SessionLocal.begin() as session:
        order_item = session.scalar(select(CustomerOrderItem).where(
            CustomerOrderItem.customer_order_id == order_a["id"]
        ))
        production_items = list(session.scalars(
            select(ProductionItem).where(
                ProductionItem.customer_order_item_id == order_item.id
            )
        ))
        for repository in session.scalars(
            select(Repository).where(
                Repository.production_item_id.in_([item.id for item in production_items])
            )
        ):
            session.delete(repository)
        finished_item = ProductionItem(
            customer_order_item_id=order_item.id,
            product_id=order_item.product_id,
            product_version=order_item.product_version,
            product_bom_id=None,
            origin_flow_node_id="demo-assembly-body-spring",
        )
        session.add(finished_item)
        session.flush()
        register_pending_finished_goods(
            session,
            production_item=finished_item,
            shipping_node_id="demo-shipping",
            quantity=7,
        )
    confirm_finished_order_receipt(order_a["items"][0]["id"], ACTOR)
    shipment = ship_finished_order_item(order_a["items"][0]["id"], 5, ACTOR)
    require(shipment["shipped_quantity"] == 5, "订单 A 发货数量不正确")
    assert_order_closed(order_a["id"])
    with SessionLocal() as session:
        surplus_receipt = session.scalar(select(InventoryReceipt).where(
            InventoryReceipt.source_customer_order_id == order_a["id"],
            InventoryReceipt.department_code == "finished",
            InventoryReceipt.status == "pending",
        ))
        require(
            surplus_receipt is not None and surplus_receipt.quantity == 2,
            "订单 A 的 2 件成品结余未转为待入库库存",
        )
        surplus_receipt_id = surplus_receipt.id
    confirm_receipt(surplus_receipt_id, ACTOR, "finished")

    # B：下一订单完全使用 2 件跨订单成品库存；库存出库后仍需成品部确认发货。
    order_b = create_planned_order("FLOW-B", 2)
    plan_b = outbound_plan("finished", order_b["id"])
    issue_outbound_plan(
        plan_b["production_plan_id"],
        "finished",
        {item["reservation_id"]: item["remaining_quantity"] for item in plan_b["items"]},
        ACTOR,
    )
    with SessionLocal() as session:
        allocated = session.scalar(select(func.sum(FinishedOrderStock.available_quantity)).where(
            FinishedOrderStock.customer_order_id == order_b["id"]
        )) or 0
    require(allocated == 2, "成品库存出库后没有转为订单可发货成品")
    ship_finished_order_item(order_b["items"][0]["id"], 2, ACTOR)
    assert_order_closed(order_b["id"])

    # C：一件已完成装配体从仓库出库，跳过其可选 QC 后注入成品待入库流程。
    with SessionLocal() as session:
        from modules.engineering.model_api import Product

        product = session.scalar(select(Product).where(Product.factory_code == "DEMO-001"))
        product_id = product.id
    with SessionLocal.begin() as session:
        receipt = create_receipt(
            session,
            identity_key=inventory_identity_key(
                department_code="warehouse",
                item_type="assembly",
                product_id=product_id,
                product_version=1,
                product_bom_id=None,
                flow_node_id="demo-assembly-body-spring",
            ),
            department_code="warehouse",
            item_type="assembly",
            product_id=product_id,
            product_version=1,
            product_bom_id=None,
            flow_node_id="demo-assembly-body-spring",
            item_code="DEMO-001-81",
            item_name="主体-弹簧装配体",
            quantity=1,
        )
        receipt_id = receipt.id
    confirm_receipt(receipt_id, ACTOR, "warehouse")
    order_c = create_planned_order("FLOW-C", 1)
    plan_c = outbound_plan("warehouse", order_c["id"])
    issue_outbound_plan(
        plan_c["production_plan_id"],
        "warehouse",
        {item["reservation_id"]: item["remaining_quantity"] for item in plan_c["items"]},
        ACTOR,
    )
    with SessionLocal() as session:
        pending = session.scalar(select(func.sum(FinishedOrderStock.pending_quantity)).where(
            FinishedOrderStock.customer_order_id == order_c["id"]
        )) or 0
    require(pending == 1, "仓库装配体未注入成品待入库流程")
    confirm_finished_order_receipt(order_c["items"][0]["id"], ACTOR)
    ship_finished_order_item(order_c["items"][0]["id"], 1, ACTOR)
    assert_order_closed(order_c["id"])

    with SessionLocal() as session:
        shipment_count = session.scalar(select(func.count(ProductionMovement.id)).where(
            ProductionMovement.movement_type == "customer_shipment"
        ))
        require(shipment_count == 3, "客户发货流水数量不正确")
    print("v6 full-flow validation passed: planning, reservation, issue, receipt, shipment, close, surplus")


if __name__ == "__main__":
    main()
