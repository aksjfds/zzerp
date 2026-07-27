from __future__ import annotations

from collections import defaultdict

from sqlalchemy import select

from database import SessionLocal
from modules.sales.model_api import Customer
from modules.engineering.model_api import Product, ProductBom
from modules.organization.model_api import Department, Procedure, Workshop
from modules.assembly.model_api import WorkOrderMaterial
from modules.production_core.model_api import (
    ProductionItem,
    ProductionMovement,
    Repository,
    WorkOrder,
)
from modules.quality.model_api import WorkOrderBatch
from modules.standard_execution.model_api import ProcedureTagStock
from modules.sales.model_api import CustomerOrder, CustomerOrderItem
from modules.production_core.operational_api import load_production_flow
from modules.production_core.operational_api import production_item_name
from modules.production_core.operational_api import (
    calculate_work_order_progress,
    order_remaining_quantity,
)


DEPARTMENT_ORDER = ("stamp", "cnc", "polish", "qc", "assembly", "warehouse")


def list_part_progress(
    page: int,
    page_size: int,
    keyword: str | None,
    order_status: str | None,
    department_code: str | None,
    only_exception: bool,
    only_unfinished: bool,
) -> tuple[list[dict], int, list[dict]]:
    with SessionLocal() as session:
        departments = list(session.scalars(
            select(Department).where(
                Department.department_code.in_(DEPARTMENT_ORDER)
            )
        ).all())
        department_by_id = {item.id: item for item in departments}
        department_by_code = {item.department_code: item for item in departments}
        ordered_departments = [
            department_by_code[code]
            for code in DEPARTMENT_ORDER
            if code in department_by_code
        ]

        statement = (
            select(ProductionItem)
            .join(
                CustomerOrderItem,
                CustomerOrderItem.id == ProductionItem.customer_order_item_id,
            )
            .join(
                CustomerOrder,
                CustomerOrder.id == CustomerOrderItem.customer_order_id,
            )
            .order_by(
                CustomerOrderItem.delivery_date,
                CustomerOrder.customer_order_no,
                ProductionItem.id,
            )
        )
        if order_status:
            statement = statement.where(CustomerOrder.status == order_status)
        production_items = list(session.scalars(statement).all())
        if not production_items:
            return [], 0, [_department(item) for item in ordered_departments]

        item_ids = [item.id for item in production_items]
        repositories = list(session.scalars(
            select(Repository).where(Repository.production_item_id.in_(item_ids))
        ).all())
        tag_stocks = list(session.scalars(
            select(ProcedureTagStock).where(
                ProcedureTagStock.production_item_id.in_(item_ids)
            )
        ).all())
        work_orders = list(session.scalars(
            select(WorkOrder).where(WorkOrder.production_item_id.in_(item_ids))
        ).all())
        work_order_ids = [item.id for item in work_orders]
        work_order_materials = list(session.scalars(
            select(WorkOrderMaterial).where(
                WorkOrderMaterial.work_order_id.in_(work_order_ids)
            )
        ).all()) if work_order_ids else []
        batches = list(session.scalars(
            select(WorkOrderBatch).where(
                WorkOrderBatch.work_order_id.in_(work_order_ids)
            )
        ).all()) if work_order_ids else []
        movements = list(session.scalars(
            select(ProductionMovement).where(
                ProductionMovement.production_item_id.in_(item_ids)
            )
        ).all())

        repositories_by_item = _group(repositories, "production_item_id")
        stocks_by_item = _group(tag_stocks, "production_item_id")
        orders_by_item = _group(work_orders, "production_item_id")
        work_order_by_id = {item.id: item for item in work_orders}
        assembly_processing_by_item: dict[int, int] = defaultdict(int)
        reserved_repository: dict[int, int] = defaultdict(int)
        reserved_stock: dict[int, int] = defaultdict(int)
        for order in work_orders:
            if (
                order.work_order_type == "assembly"
                and order.status == "open"
                and order.completed_quantity == 0
            ):
                orders_by_item[order.production_item_id] = [
                    item
                    for item in orders_by_item[order.production_item_id]
                    if item.id != order.id
                ]
        for material in work_order_materials:
            order = work_order_by_id.get(material.work_order_id)
            if (
                order is None
                or order.work_order_type != "assembly"
                or order.status != "open"
                or order.completed_quantity != 0
            ):
                continue
            assembly_processing_by_item[material.production_item_id] += (
                material.quantity
            )
            if material.repository_id is not None:
                reserved_repository[material.repository_id] += material.quantity
        batches_by_order = _group(batches, "work_order_id")
        movements_by_item = _group(movements, "production_item_id")
        movements_by_batch = _group(
            [item for item in movements if item.work_order_batch_id is not None],
            "work_order_batch_id",
        )
        for order in work_orders:
            if order.status != "open":
                continue
            remaining = order_remaining_quantity(order)
            if order.repository_id is not None:
                reserved_repository[order.repository_id] += remaining
            if order.procedure_tag_stock_id is not None:
                reserved_stock[order.procedure_tag_stock_id] += remaining

        workshops = {
            item.id: item for item in session.scalars(select(Workshop)).all()
        }
        procedures = {
            item.id: item for item in session.scalars(select(Procedure)).all()
        }

        rows = []
        normalized_keyword = (keyword or "").strip().lower()
        for production_item in production_items:
            row = _serialize_item(
                session,
                production_item,
                ordered_departments,
                department_by_id,
                department_by_code,
                workshops,
                procedures,
                repositories_by_item.get(production_item.id, []),
                stocks_by_item.get(production_item.id, []),
                orders_by_item.get(production_item.id, []),
                batches_by_order,
                movements_by_item.get(production_item.id, []),
                movements_by_batch,
                reserved_repository,
                reserved_stock,
                assembly_processing_by_item.get(production_item.id, 0),
            )
            if normalized_keyword and normalized_keyword not in row["search_text"]:
                continue
            cells = row["departments"]
            if department_code and not cells.get(
                department_code, {}
            ).get("in_route"):
                continue
            has_exception = any(
                cell["scrap_quantity"] > 0 or cell["lost_quantity"] > 0
                for cell in cells.values()
            )
            unfinished = any(
                cell["waiting_quantity"] > 0
                or cell["processing_quantity"] > 0
                or cell["pending_qc_quantity"] > 0
                for cell in cells.values()
            )
            if only_exception and not has_exception:
                continue
            if only_unfinished and not unfinished:
                continue
            row.pop("search_text", None)
            rows.append(row)

        total = len(rows)
        offset = (page - 1) * page_size
        return (
            rows[offset:offset + page_size],
            total,
            [_department(item) for item in ordered_departments],
        )


def _serialize_item(
    session,
    production_item,
    ordered_departments,
    department_by_id,
    department_by_code,
    workshops,
    procedures,
    repositories,
    tag_stocks,
    work_orders,
    batches_by_order,
    movements,
    movements_by_batch,
    reserved_repository,
    reserved_stock,
    assembly_processing_quantity,
) -> dict:
    order_item = session.get(CustomerOrderItem, production_item.customer_order_item_id)
    order = session.get(CustomerOrder, order_item.customer_order_id)
    product = session.get(Product, production_item.product_id)
    customer = session.get(Customer, order.customer_id)
    bom_item = (
        session.get(ProductBom, production_item.product_bom_id)
        if production_item.product_bom_id else None
    )
    context = load_production_flow(session, production_item)
    part_name = production_item_name(session, production_item, set())
    target_quantity = (
        order_item.quantity * bom_item.pcs
        if bom_item else _assembly_target_quantity(
            context,
            production_item,
            work_orders,
        )
    )
    cells = {
        item.department_code: _empty_cell()
        for item in ordered_departments
    }
    route_nodes = _physical_route(context, production_item.origin_flow_node_id)
    edge_pairs = {
        (edge.get("source_node_id"), edge.get("target_node_id"))
        for edge in context.flow.get("edges", [])
    }
    for node in route_nodes:
        department = _node_department(
            node,
            department_by_code,
            workshops,
            procedures,
        )
        if department is None or department.department_code not in cells:
            continue
        cell = cells[department.department_code]
        cell["in_route"] = True

    if assembly_processing_quantity:
        assembly_cell = cells.get("assembly")
        if assembly_cell:
            assembly_cell["in_route"] = True
            assembly_cell["processing_quantity"] += assembly_processing_quantity

    for repository in repositories:
        department = department_by_id.get(repository.department_id)
        if department and department.department_code in cells:
            cell = cells[department.department_code]
            cell["in_route"] = True
            cell["waiting_quantity"] += max(
                repository.quantity - reserved_repository[repository.id],
                0,
            )
    for stock in tag_stocks:
        department = department_by_id.get(stock.department_id)
        if department and department.department_code in cells:
            cell = cells[department.department_code]
            cell["in_route"] = True
            cell["waiting_quantity"] += max(
                stock.quantity - reserved_stock[stock.id],
                0,
            )

    for work_order in work_orders:
        order_batches = batches_by_order.get(work_order.id, [])
        node = context.nodes.get(work_order.flow_node_id, {})
        department = _node_department(
            node,
            department_by_code,
            workshops,
            procedures,
        )
        if (
            department
            and department.department_code in cells
            and work_order.status != "cancelled"
        ):
            cell = cells[department.department_code]
            cell["in_route"] = True
            if work_order.status == "open":
                progress = calculate_work_order_progress(work_order, order_batches)
                cell["processing_quantity"] += progress.processing_quantity

        qc_cell = cells.get("qc")
        if qc_cell is None or work_order.status == "cancelled":
            continue
        for batch in order_batches:
            if batch.recorded_at is None:
                qc_cell["in_route"] = True
                qc_cell["pending_qc_quantity"] += batch.submitted_quantity
            elif batch.qualified_quantity:
                batch_movements = movements_by_batch.get(batch.id, [])
                held_qualified = sum(
                    movement.quantity
                    for movement in batch_movements
                    if (
                        movement.movement_type == "qc_qualified"
                        and movement.source_flow_node_id
                        == movement.target_flow_node_id
                    )
                )
                dispatched = sum(
                    movement.quantity
                    for movement in batch_movements
                    if movement.movement_type == "qc_dispatch"
                )
                held = max(held_qualified - dispatched, 0)
                if held:
                    qc_cell["in_route"] = True
                    qc_cell["waiting_quantity"] += held

    for movement in movements:
        source_department = department_by_id.get(movement.source_department_id)
        if movement.movement_type in {"scrap", "lost"} and source_department:
            cell = cells.get(source_department.department_code)
            if cell:
                key = f"{movement.movement_type}_quantity"
                cell[key] += movement.quantity
            continue
        if movement.movement_type == "assembly_input" and source_department:
            cell = cells.get(source_department.department_code)
            if cell:
                cell["completed_quantity"] += movement.quantity
            continue
        if (
            (movement.source_flow_node_id, movement.target_flow_node_id)
            not in edge_pairs
        ):
            continue
        if source_department:
            cell = cells.get(source_department.department_code)
            if cell:
                cell["completed_quantity"] += movement.quantity
        target_node = context.nodes.get(movement.target_flow_node_id or "", {})
        if target_node.get("type") == "shipping":
            warehouse = cells.get("warehouse")
            if warehouse:
                warehouse["in_route"] = True
                warehouse["completed_quantity"] += movement.quantity

    return {
        "production_item_id": production_item.id,
        "customer_order_id": order.id,
        "customer_order_no": order.customer_order_no,
        "customer_name": customer.customer_name,
        "order_status": order.status,
        "factory_code": product.factory_code,
        "product_name": product.product_name,
        "part_name": part_name,
        "part_display_name": f"{product.factory_code}-{product.product_name}-{part_name}",
        "target_quantity": target_quantity,
        "delivery_date": order_item.delivery_date.isoformat(),
        "departments": cells,
        "search_text": " ".join((
            order.customer_order_no,
            customer.customer_name,
            product.factory_code,
            product.product_name,
            part_name,
        )).lower(),
    }


def _physical_route(context, origin_node_id: str) -> list[dict]:
    route = []
    origin = context.nodes.get(origin_node_id)
    if origin and origin.get("type") == "assembly":
        route.append(origin)
    current = context.normal_target(origin_node_id)
    visited = set()
    while current and current["id"] not in visited:
        visited.add(current["id"])
        route.append(current)
        if current.get("type") == "assembly":
            break
        current = context.normal_target(current["id"])
    return route


def _node_department(node, department_by_code, workshops, procedures):
    node_type = node.get("type")
    if node_type == "process":
        procedure = procedures.get(node.get("procedure_id"))
        workshop = workshops.get(procedure.workshop_id) if procedure else None
        return (
            next(
                (
                    department
                    for department in department_by_code.values()
                    if workshop and department.id == workshop.department_id
                ),
                None,
            )
        )
    code = {
        "qc": "qc",
        "assembly": "assembly",
        "shipping": "warehouse",
    }.get(node_type)
    return department_by_code.get(code) if code else None


def _assembly_target_quantity(context, production_item, work_orders) -> int:
    output_pcs = int(
        context.nodes.get(production_item.origin_flow_node_id, {}).get(
            "output_pcs",
            1,
        )
    )
    return sum(
        order.quantity * output_pcs
        for order in work_orders
        if (
            order.work_order_type == "assembly"
            and order.status != "cancelled"
        )
    )


def _empty_cell() -> dict:
    return {
        "in_route": False,
        "waiting_quantity": 0,
        "processing_quantity": 0,
        "pending_qc_quantity": 0,
        "completed_quantity": 0,
        "scrap_quantity": 0,
        "lost_quantity": 0,
    }


def _department(item) -> dict:
    return {
        "department_id": item.id,
        "department_code": item.department_code,
        "department_name": item.department_name,
    }


def _group(items, attribute: str) -> dict:
    grouped = defaultdict(list)
    for item in items:
        grouped[getattr(item, attribute)].append(item)
    return grouped
