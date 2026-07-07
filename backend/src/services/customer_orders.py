from datetime import datetime

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError

from database import SessionLocal
from models.engineering import Product, ProductBom, ProductProcessFlow
from models.production import ProductionItem, WorkOrder, WorkOrderBatch
from models.organization import Procedure
from models.sales import CustomerOrder, CustomerOrderItem
from repositories.customer_orders import CustomerOrderRepository
from schemas.sales import CustomerOrderCreate, CustomerOrderItemInput, CustomerOrderUpdate
from schemas.engineering import ProcessFlowPayload
from domain.process_flow import validate_process_flow
from services.errors import DomainError


def _not_found() -> DomainError:
    return DomainError("customer_order_not_found", "客户订单不存在", status_code=404)


def _serialize(session, order: CustomerOrder, products: dict[int, Product] | None = None) -> dict:
    if products is None:
        product_ids = {item.product_id for item in order.items}
        products = {
            item.id: item
            for item in session.scalars(select(Product).where(Product.id.in_(product_ids))).all()
        }
    return {
        "id": order.id,
        "customer_order_no": order.customer_order_no,
        "customer_name": order.customer_name,
        "status": order.status,
        "revision": order.revision,
        "remark": order.remark or "",
        "items": [
            {
                "id": item.id,
                "product_id": item.product_id,
                "product_version": item.product_version,
                "product_name": products[item.product_id].product_name,
                "factory_code": products[item.product_id].factory_code,
                "quantity": item.quantity,
                "delivery_date": item.delivery_date,
                "remark": item.remark or "",
            }
            for item in order.items
        ],
        "created_at": order.created_at.isoformat(timespec="minutes"),
        "updated_at": order.updated_at.isoformat(timespec="minutes"),
    }


def _resolve_products(session, items: list[CustomerOrderItemInput]) -> dict[int, Product]:
    product_ids = {item.product_id for item in items}
    products = {
        item.id: item
        for item in session.scalars(
            select(Product)
            .where(Product.id.in_(product_ids))
            .order_by(Product.id)
            .with_for_update()
        ).all()
    }
    if len(products) != len(product_ids):
        raise DomainError("invalid_order_product", "订单包含不存在的产品", path="items")
    for product in products.values():
        bom_ids = set(session.scalars(
            select(ProductBom.id).where(
                ProductBom.product_id == product.id,
                ProductBom.product_version == product.version,
            )
        ).all())
        has_flow = session.scalar(
            select(ProductProcessFlow.id).where(
                ProductProcessFlow.product_id == product.id,
                ProductProcessFlow.product_version == product.version,
            ).limit(1)
        )
        flow = session.get(ProductProcessFlow, has_flow) if has_flow else None
        if not bom_ids or flow is None or not flow.flow_json.get("nodes"):
            raise DomainError(
                "product_engineering_data_missing",
                f"产品 {product.factory_code} 缺少当前版本 BOM 或流程图",
                path="items",
            )
        validated = ProcessFlowPayload.model_validate(flow.flow_json)
        validate_process_flow(validated, bom_ids)
        procedure_ids = {
            node.procedure_id for node in validated.nodes if node.type == "process"
        }
        existing_procedure_ids = set(
            session.scalars(
                select(Procedure.id).where(Procedure.id.in_(procedure_ids))
            ).all()
        )
        if existing_procedure_ids != procedure_ids:
            raise DomainError(
                "process_procedure_invalid",
                f"产品 {product.factory_code} 的流程包含失效工艺",
                path="items",
            )
    return products


def _replace_items(
    order: CustomerOrder,
    items: list[CustomerOrderItemInput],
    products: dict[int, Product],
) -> None:
    order.items.clear()
    for item in items:
        product = products[item.product_id]
        order.items.append(
            CustomerOrderItem(
                product_id=product.id,
                product_version=product.version,
                quantity=item.quantity,
                delivery_date=item.delivery_date,
                remark=item.remark or None,
            )
        )


def list_orders(page: int, page_size: int) -> tuple[list[dict], int]:
    with SessionLocal() as session:
        repository = CustomerOrderRepository(session)
        orders = repository.list((page - 1) * page_size, page_size)
        product_ids = {item.product_id for order in orders for item in order.items}
        products = {
            item.id: item
            for item in session.scalars(select(Product).where(Product.id.in_(product_ids))).all()
        }
        return [_serialize(session, item, products) for item in orders], repository.count()


def get_order(order_id: int) -> dict:
    with SessionLocal() as session:
        order = CustomerOrderRepository(session).get(order_id)
        if order is None:
            raise _not_found()
        return _serialize(session, order)


def create_order(payload: CustomerOrderCreate) -> dict:
    try:
        with SessionLocal.begin() as session:
            repository = CustomerOrderRepository(session)
            products = _resolve_products(session, payload.items)
            order = CustomerOrder(
                customer_order_no=payload.customer_order_no,
                customer_name=payload.customer_name,
                remark=payload.remark or None,
            )
            repository.add(order)
            _replace_items(order, payload.items, products)
            session.flush()
            result = _serialize(session, order)
        return result
    except IntegrityError as exc:
        _raise_order_integrity_error(exc)


def _raise_order_integrity_error(exc: IntegrityError) -> None:
    constraint = getattr(
        getattr(getattr(exc, "orig", None), "diag", None), "constraint_name", ""
    )
    if "customer_order_no" in constraint:
        raise DomainError(
            "customer_order_no_conflict", "客户订单编号已存在", status_code=409
        ) from exc
    raise DomainError(
        "customer_order_data_conflict",
        "客户订单数据违反关联或数量约束",
        status_code=409,
    ) from exc


def update_order(order_id: int, payload: CustomerOrderUpdate) -> dict:
    try:
        with SessionLocal.begin() as session:
            repository = CustomerOrderRepository(session)
            order = repository.get_for_update(order_id)
            if order is None:
                raise _not_found()
            if order.status != "draft":
                raise DomainError("customer_order_not_editable", "只有草稿订单允许修改")
            if order.revision != payload.expected_revision:
                raise DomainError(
                    "customer_order_revision_conflict",
                    "客户订单已被其他用户更新，请重新加载",
                    status_code=409,
                )
            products = _resolve_products(session, payload.items)
            if payload.customer_order_no is not None:
                order.customer_order_no = payload.customer_order_no
            if payload.customer_name is not None:
                order.customer_name = payload.customer_name
            order.remark = payload.remark or None
            order.updated_at = datetime.now()
            order.revision += 1
            _replace_items(order, payload.items, products)
            session.flush()
            return _serialize(session, order)
    except IntegrityError as exc:
        _raise_order_integrity_error(exc)


def change_status(order_id: int, target: str, expected_revision: int) -> dict:
    with SessionLocal.begin() as session:
        repository = CustomerOrderRepository(session)
        order = repository.get_for_update(order_id)
        if order is None:
            raise _not_found()
        if order.revision != expected_revision:
            raise DomainError(
                "customer_order_revision_conflict",
                "客户订单已被其他用户更新，请重新加载",
                status_code=409,
            )
        if target == "confirmed":
            if order.status != "draft":
                raise DomainError("invalid_customer_order_status", "当前订单状态不允许确认")
            from services.production_repositories import provision_order_repositories

            provision_order_repositories(session, order)
        elif target == "cancelled":
            if order.status not in {"draft", "confirmed", "planned"}:
                raise DomainError("invalid_customer_order_status", "当前订单状态不允许取消")
            if order.status != "draft":
                work_orders = session.scalars(
                    select(WorkOrder)
                    .join(ProductionItem, ProductionItem.id == WorkOrder.production_item_id)
                    .join(CustomerOrderItem, CustomerOrderItem.id == ProductionItem.customer_order_item_id)
                    .where(CustomerOrderItem.customer_order_id == order.id)
                ).all()
                if any(item.completed_quantity > 0 for item in work_orders):
                    raise DomainError("customer_order_started", "订单已经产生生产完成数量，不能取消")
                if work_orders:
                    batch_count = session.scalar(
                        select(func.count(WorkOrderBatch.id)).where(
                            WorkOrderBatch.work_order_id.in_([item.id for item in work_orders])
                        )
                    )
                    if batch_count:
                        raise DomainError("customer_order_started", "订单已经送检，不能取消")
                for item in work_orders:
                    session.delete(item)
                production_items = session.scalars(
                    select(ProductionItem)
                    .join(CustomerOrderItem, CustomerOrderItem.id == ProductionItem.customer_order_item_id)
                    .where(CustomerOrderItem.customer_order_id == order.id)
                ).all()
                for item in production_items:
                    session.delete(item)
        else:
            raise DomainError("invalid_customer_order_status", "不支持的订单状态操作")
        order.status = target
        order.updated_at = datetime.now()
        order.revision += 1
        session.flush()
        return _serialize(session, order)


def delete_order(order_id: int, expected_revision: int) -> None:
    with SessionLocal.begin() as session:
        repository = CustomerOrderRepository(session)
        order = repository.get_for_update(order_id)
        if order is None:
            raise _not_found()
        if order.status != "draft":
            raise DomainError("customer_order_not_deletable", "只有草稿订单允许删除")
        if order.revision != expected_revision:
            raise DomainError(
                "customer_order_revision_conflict",
                "客户订单已被其他用户更新，请重新加载",
                status_code=409,
            )
        repository.delete(order)
