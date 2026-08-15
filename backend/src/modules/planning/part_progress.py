from __future__ import annotations

from collections import defaultdict

from sqlalchemy import select

from database import SessionLocal
from modules.sales.model_api import Customer
from modules.engineering.model_api import Product, ProductBom
from modules.planning.persistence import ProductionPlan, ProductionPlanItem
from modules.planning.assembly_progress import (
    assembly_arrival_progress,
    assembly_completion_summary,
)
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
from modules.standard_execution.tag_api import is_final_tag_set
from modules.sales.model_api import CustomerOrder, CustomerOrderItem
from modules.production_core.operational_api import load_production_flow
from modules.production_core.operational_api import load_product_flow
from modules.production_core.flow import physical_route_nodes
from modules.production_core.operational_api import production_item_name
from modules.production_core.operational_api import (
    calculate_work_order_progress,
    order_remaining_quantity,
    terminal_unit_quantity,
)


DEPARTMENT_ORDER = (
    "stamp",
    "cnc",
    "polish",
    "outsource",
    "purchasing",
    "qc",
    "assembly",
    "finished",
)


def list_part_progress(
    page: int,
    page_size: int,
    keyword: str | None,
    customer_order_id: int | None,
    focus_order_id: int | None,
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
        if customer_order_id is not None:
            statement = statement.where(CustomerOrder.id == customer_order_id)
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
        production_items_by_order_item = _group(
            production_items,
            "customer_order_item_id",
        )
        shipping_by_order_item = {}
        for order_item_id, order_production_items in (
            production_items_by_order_item.items()
        ):
            order_item = session.get(CustomerOrderItem, order_item_id)
            order_movements = [
                movement
                for item in order_production_items
                for movement in movements_by_item.get(item.id, [])
            ]
            shipping_by_order_item[order_item_id] = _shipping_summary(
                session,
                order_item,
                order_movements,
            )
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
                shipping_by_order_item[production_item.customer_order_item_id],
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

        orders = _group_rows_by_order(rows, focus_order_id)
        total = len(orders)
        offset = (page - 1) * page_size
        return (
            orders[offset:offset + page_size],
            total,
            [_department(item) for item in ordered_departments],
        )


def list_department_production_progress(
    department_code: str,
    page: int,
    page_size: int,
    keyword: str | None,
) -> tuple[list[dict], int]:
    if department_code == "assembly":
        return _list_assembly_production_progress(page, page_size, keyword)
    orders, _, _ = list_part_progress(
        page=1,
        page_size=1_000_000,
        keyword=keyword,
        customer_order_id=None,
        focus_order_id=None,
        order_status=None,
        department_code=department_code,
        only_exception=False,
        only_unfinished=False,
    )
    parts = [part for order in orders for part in order["parts"]]
    plan_refs = _production_plan_refs({
        part["production_item_id"] for part in parts
    })
    rows = []
    for part in parts:
        plan_ref = plan_refs[part["production_item_id"]]
        task_quantity = plan_ref["planned_production_quantity"]
        workshop_arrivals = part["department_workshop_arrivals"].get(
            department_code,
            {},
        )
        for processing_workshop in (
            part["department_workshops"].get(department_code) or [""]
        ):
            arrived_quantity = workshop_arrivals.get(processing_workshop, 0)
            completed_quantity = (
                part["department_workshop_completions"]
                .get(department_code, {})
                .get(
                    processing_workshop,
                    part["departments"].get(department_code, {}).get(
                        "completed_quantity",
                        0,
                    ) if not processing_workshop else 0,
                )
            )
            rows.append({
                "production_plan_item_id": plan_ref["production_plan_item_id"],
                "production_item_id": part["production_item_id"],
                "flow_node_id": None,
                "part_no": part["part_no"],
                "part_name": f'{part["product_name"]}-{part["part_name"]}',
                "processing_workshop": processing_workshop,
                "customer_order_no": part["customer_order_no"],
                "order_date": part["order_date"],
                "task_quantity": task_quantity,
                "arrived_quantity": arrived_quantity,
                "material_arrivals": [],
                "completed_quantity": completed_quantity,
                "remark": part["remark"],
            })
    rows.extend(
        _list_planned_department_progress(
            department_code,
            keyword,
        )
    )
    rows.sort(
        key=lambda item: (
            item["order_date"],
            item["customer_order_no"],
            item["part_no"],
        ),
        reverse=True,
    )
    total = len(rows)
    offset = (page - 1) * page_size
    page_rows = rows[offset:offset + page_size]
    return [
        {
            key: value
            for key, value in row.items()
            if key not in {"customer_order_no", "order_date"}
        }
        for row in page_rows
    ], total


def _list_assembly_production_progress(
    page: int,
    page_size: int,
    keyword: str | None,
) -> tuple[list[dict], int]:
    with SessionLocal() as session:
        plan_rows = session.execute(
            select(
                ProductionPlanItem,
                ProductionPlan,
                CustomerOrderItem,
                CustomerOrder,
                Product,
            )
            .join(
                ProductionPlan,
                ProductionPlan.id == ProductionPlanItem.production_plan_id,
            )
            .join(
                CustomerOrderItem,
                CustomerOrderItem.id == ProductionPlanItem.customer_order_item_id,
            )
            .join(
                CustomerOrder,
                CustomerOrder.id == ProductionPlan.customer_order_id,
            )
            .join(Product, Product.id == ProductionPlanItem.product_id)
            .where(
                ProductionPlan.status.in_(("draft", "confirmed")),
                CustomerOrder.status != "cancelled",
                ProductionPlanItem.item_type == "assembly",
                ProductionPlanItem.planned_production_quantity > 0,
            )
        ).all()
        if not plan_rows:
            return [], 0

        order_item_ids = {
            order_item.id
            for _, _, order_item, _, _ in plan_rows
        }
        production_items = list(session.scalars(
            select(ProductionItem).where(
                ProductionItem.customer_order_item_id.in_(order_item_ids)
            )
        ).all())
        production_item_by_id = {item.id: item for item in production_items}
        production_items_by_order_item = _group(
            production_items,
            "customer_order_item_id",
        )
        production_item_ids = set(production_item_by_id)
        movements = list(session.scalars(
            select(ProductionMovement).where(
                ProductionMovement.production_item_id.in_(production_item_ids)
            )
        ).all()) if production_item_ids else []
        movements_by_order_item: dict[int, list[ProductionMovement]] = defaultdict(list)
        for movement in movements:
            production_item = production_item_by_id.get(movement.production_item_id)
            if production_item is not None:
                movements_by_order_item[production_item.customer_order_item_id].append(
                    movement
                )

        work_orders_by_task: dict[tuple[int, str], list[WorkOrder]] = defaultdict(list)
        work_orders = []
        if production_item_ids:
            for work_order, order_item_id in session.execute(
                select(WorkOrder, ProductionItem.customer_order_item_id)
                .join(
                    ProductionItem,
                    ProductionItem.id == WorkOrder.production_item_id,
                )
                .where(
                    ProductionItem.customer_order_item_id.in_(order_item_ids),
                    WorkOrder.status != "cancelled",
                )
            ):
                work_orders.append(work_order)
                work_orders_by_task[(order_item_id, work_order.flow_node_id)].append(
                    work_order
                )
        work_order_ids = {item.id for item in work_orders}
        batches_by_order: dict[int, list[WorkOrderBatch]] = defaultdict(list)
        if work_order_ids:
            for batch in session.scalars(
                select(WorkOrderBatch).where(
                    WorkOrderBatch.work_order_id.in_(work_order_ids)
                )
            ):
                batches_by_order[batch.work_order_id].append(batch)

        bom_items = {
            item.id: item
            for item in session.scalars(
                select(ProductBom).where(
                    ProductBom.product_id.in_(
                        {product.id for _, _, _, _, product in plan_rows}
                    )
                )
            )
        }
        procedures = {
            item.id: item for item in session.scalars(select(Procedure)).all()
        }
        workshops = {
            item.id: item for item in session.scalars(select(Workshop)).all()
        }
        assembly_department = session.scalar(
            select(Department).where(Department.department_code == "assembly")
        )
        normalized_keyword = (keyword or "").strip().lower()
        flow_cache: dict[tuple[int, int], tuple[dict, dict[str, dict]]] = {}
        rows = []
        for plan_item, plan, order_item, order, product in plan_rows:
            flow_key = (plan_item.product_id, plan_item.product_version)
            if flow_key not in flow_cache:
                flow_cache[flow_key] = load_product_flow(
                    session,
                    plan_item.product_id,
                    plan_item.product_version,
                )
            flow, nodes = flow_cache[flow_key]
            assembly_node = nodes.get(plan_item.flow_node_id)
            if assembly_node is None or assembly_node.get("type") != "assembly":
                continue
            output_unit_quantity = max(
                int(assembly_node.get("output_pcs") or 1),
                1,
            )
            task_nodes = _assembly_department_task_nodes(
                flow,
                nodes,
                plan_item.flow_node_id,
                assembly_department.id if assembly_department else None,
                procedures,
                workshops,
            )
            search_text = " ".join((
                plan_item.item_code,
                plan_item.item_name,
                product.factory_code,
                product.product_name,
                order.customer_order_no,
                *(
                    str(node.get("label") or "")
                    for node in task_nodes
                ),
                *(
                    procedures[node["procedure_id"]].procedure_name
                    for node in task_nodes
                    if node.get("procedure_id") in procedures
                ),
            )).lower()
            if normalized_keyword and normalized_keyword not in search_text:
                continue
            remarks = [
                value.strip()
                for value in (order_item.remark, order.remark)
                if value and value.strip()
            ]
            output_item = next(
                (
                    item
                    for item in production_items_by_order_item.get(order_item.id, [])
                    if item.product_bom_id is None
                    and item.origin_flow_node_id == plan_item.flow_node_id
                ),
                None,
            )
            for task_node in task_nodes:
                task_node_id = task_node["id"]
                task_procedure = procedures.get(task_node.get("procedure_id"))
                task_workshop = (
                    workshops.get(task_procedure.workshop_id)
                    if task_procedure else None
                )
                task_orders = work_orders_by_task.get(
                    (order_item.id, task_node_id),
                    [],
                )
                if task_node_id == plan_item.flow_node_id:
                    completed_quantity = assembly_completion_summary(
                        task_orders,
                        batches_by_order,
                        output_unit_quantity,
                    )
                    arrived_quantity, material_arrivals = assembly_arrival_progress(
                        flow,
                        nodes,
                        plan_item.flow_node_id,
                        output_unit_quantity,
                        production_items_by_order_item.get(order_item.id, []),
                        movements_by_order_item.get(order_item.id, []),
                        bom_items,
                        plan_item.planned_production_quantity,
                    )
                else:
                    completed_quantity = _process_completion_summary(
                        session,
                        task_orders,
                        batches_by_order,
                        production_item_by_id,
                        task_procedure,
                    )
                    arrived_quantity = sum(
                        movement.quantity
                        for movement in movements_by_order_item.get(order_item.id, [])
                        if movement.target_flow_node_id == task_node_id
                        and movement.source_flow_node_id != task_node_id
                    )
                    material_arrivals = []
                processing_workshop = (
                    task_workshop.workshop_name
                    if task_workshop else str(task_node.get("label") or "装配")
                )
                rows.append({
                    "production_plan_item_id": plan_item.id,
                    "production_item_id": output_item.id if output_item else None,
                    "flow_node_id": task_node_id,
                    "part_no": plan_item.item_code,
                    "part_name": f"{product.product_name}-{plan_item.item_name}",
                    "processing_workshop": processing_workshop,
                    "customer_order_no": order.customer_order_no,
                    "order_date": order.created_at.date().isoformat(),
                    "task_quantity": plan_item.planned_production_quantity,
                    "arrived_quantity": arrived_quantity,
                    "material_arrivals": material_arrivals,
                    "completed_quantity": completed_quantity,
                    "remark": "；".join(dict.fromkeys(remarks)),
                })
        rows.sort(
            key=lambda item: (
                item["order_date"],
                item["customer_order_no"],
                item["part_no"],
            ),
            reverse=True,
        )
        total = len(rows)
        offset = (page - 1) * page_size
        return [
            {
                key: value
                for key, value in row.items()
                if key not in {"customer_order_no", "order_date"}
            }
            for row in rows[offset:offset + page_size]
        ], total


def _assembly_department_task_nodes(
    flow: dict,
    nodes: dict[str, dict],
    origin_node_id: str,
    assembly_department_id: int | None,
    procedures: dict[int, Procedure],
    workshops: dict[int, Workshop],
) -> list[dict]:
    result = []
    for node in physical_route_nodes(flow, nodes, origin_node_id):
        if node["id"] == origin_node_id:
            result.append(node)
            continue
        if node.get("type") != "process":
            continue
        procedure = procedures.get(node.get("procedure_id"))
        workshop = workshops.get(procedure.workshop_id) if procedure else None
        if workshop and workshop.department_id == assembly_department_id:
            result.append(node)
    return result


def _process_completion_summary(
    session,
    work_orders: list[WorkOrder],
    batches_by_order: dict[int, list[WorkOrderBatch]],
    production_item_by_id: dict[int, ProductionItem],
    procedure: Procedure | None,
) -> int:
    completed_quantity = 0
    for work_order in work_orders:
        production_item = production_item_by_id.get(work_order.production_item_id)
        if (
            work_order.work_order_type == "tag"
            and procedure is not None
            and production_item is not None
            and not is_final_tag_set(
                session,
                production_item,
                procedure.id,
                work_order.target_tag_set_id,
            )
        ):
            continue
        batches = batches_by_order.get(work_order.id, [])
        progress = calculate_work_order_progress(work_order, batches)
        completed_quantity += progress.qualified_quantity
    return completed_quantity


def _production_plan_refs(production_item_ids: set[int]) -> dict[int, dict]:
    if not production_item_ids:
        return {}
    with SessionLocal() as session:
        production_items = list(session.scalars(
            select(ProductionItem).where(ProductionItem.id.in_(production_item_ids))
        ).all())
        order_item_ids = {
            item.customer_order_item_id for item in production_items
        }
        plan_items = list(session.scalars(
            select(ProductionPlanItem)
            .join(
                ProductionPlan,
                ProductionPlan.id == ProductionPlanItem.production_plan_id,
            )
            .where(
                ProductionPlan.status == "confirmed",
                ProductionPlanItem.customer_order_item_id.in_(order_item_ids),
            )
        ).all())
        plan_item_by_identity = {
            (
                item.customer_order_item_id,
                item.product_id,
                item.product_version,
                item.product_bom_id,
                item.flow_node_id,
            ): item
            for item in plan_items
        }
        return {
            item.id: {
                "production_plan_item_id": plan_item.id,
                "planned_production_quantity": (
                    plan_item.planned_production_quantity
                ),
            }
            for item in production_items
            for plan_item in [plan_item_by_identity[
                (
                    item.customer_order_item_id,
                    item.product_id,
                    item.product_version,
                    item.product_bom_id,
                    item.origin_flow_node_id,
                )
            ]]
        }


def _list_planned_department_progress(
    department_code: str,
    keyword: str | None,
) -> list[dict]:
    """Return plan items which do not have a runtime production item yet."""
    with SessionLocal() as session:
        plan_items = list(session.scalars(
            select(ProductionPlanItem)
            .join(
                ProductionPlan,
                ProductionPlan.id == ProductionPlanItem.production_plan_id,
            )
            .join(
                CustomerOrder,
                CustomerOrder.id == ProductionPlan.customer_order_id,
            )
            .where(
                ProductionPlan.status.in_(("draft", "confirmed")),
                CustomerOrder.status != "cancelled",
                ProductionPlanItem.item_type.in_(("part", "assembly")),
                ProductionPlanItem.planned_production_quantity > 0,
            )
            .order_by(ProductionPlan.id.desc(), ProductionPlanItem.sort_order)
        ).all())
        if not plan_items:
            return []

        order_item_ids = {item.customer_order_item_id for item in plan_items}
        runtime_keys = {
            (
                item.customer_order_item_id,
                item.product_id,
                item.product_version,
                item.product_bom_id,
                item.origin_flow_node_id,
            )
            for item in session.scalars(
                select(ProductionItem).where(
                    ProductionItem.customer_order_item_id.in_(order_item_ids)
                )
            ).all()
        }
        plans = {
            item.id: item
            for item in session.scalars(
                select(ProductionPlan).where(
                    ProductionPlan.id.in_(
                        {item.production_plan_id for item in plan_items}
                    )
                )
            ).all()
        }
        order_items = {
            item.id: item
            for item in session.scalars(
                select(CustomerOrderItem).where(
                    CustomerOrderItem.id.in_(order_item_ids)
                )
            ).all()
        }
        orders = {
            item.id: item
            for item in session.scalars(
                select(CustomerOrder).where(
                    CustomerOrder.id.in_(
                        {plan.customer_order_id for plan in plans.values()}
                    )
                )
            ).all()
        }
        products = {
            item.id: item
            for item in session.scalars(
                select(Product).where(
                    Product.id.in_({item.product_id for item in plan_items})
                )
            ).all()
        }
        departments = list(session.scalars(select(Department)).all())
        department_by_code = {
            item.department_code: item for item in departments
        }
        workshops = {
            item.id: item for item in session.scalars(select(Workshop)).all()
        }
        procedures = {
            item.id: item for item in session.scalars(select(Procedure)).all()
        }
        normalized_keyword = (keyword or "").strip().lower()
        rows = []
        for item in plan_items:
            runtime_key = (
                item.customer_order_item_id,
                item.product_id,
                item.product_version,
                item.product_bom_id,
                item.flow_node_id,
            )
            if runtime_key in runtime_keys:
                continue
            flow, nodes = load_product_flow(
                session,
                item.product_id,
                item.product_version,
            )
            route_nodes = _physical_route_nodes(flow, nodes, item.flow_node_id)
            belongs_to_department = any(
                node.get("type") != "assembly"
                or node.get("id") == item.flow_node_id
                for node in route_nodes
                if (
                    (department := _node_department(
                        node,
                        department_by_code,
                        workshops,
                        procedures,
                    ))
                    and department.department_code == department_code
                )
            )
            if not belongs_to_department:
                continue
            processing_workshops = _department_workshop_names(
                route_nodes,
                department_code,
                department_by_code,
                workshops,
                procedures,
                origin_flow_node_id=item.flow_node_id,
            )
            plan = plans[item.production_plan_id]
            order_item = order_items[item.customer_order_item_id]
            order = orders[plan.customer_order_id]
            product = products[item.product_id]
            search_text = " ".join((
                item.item_code,
                item.item_name,
                product.factory_code,
                product.product_name,
                order.customer_order_no,
            )).lower()
            if normalized_keyword and normalized_keyword not in search_text:
                continue
            remarks = [
                value.strip()
                for value in (order_item.remark, order.remark)
                if value and value.strip()
            ]
            remarks.append(
                "生产计划待确认"
                if plan.status == "draft"
                else "等待前序生产"
            )
            quantity = item.planned_production_quantity
            for processing_workshop in processing_workshops or [""]:
                rows.append({
                    "production_plan_item_id": item.id,
                    "production_item_id": None,
                    "flow_node_id": None,
                    "part_no": item.item_code,
                    "part_name": f"{product.product_name}-{item.item_name}",
                    "processing_workshop": processing_workshop,
                    "customer_order_no": order.customer_order_no,
                    "order_date": order.created_at.date().isoformat(),
                    "task_quantity": quantity,
                    "arrived_quantity": 0,
                    "material_arrivals": [],
                    "completed_quantity": 0,
                    "remark": "；".join(dict.fromkeys(remarks)),
                })
        return rows


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
    shipping_summary,
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
    item_shipping_summary = _production_item_shipping_summary(
        context,
        movements,
        target_quantity,
    )
    if bom_item:
        unit_quantity = max(target_quantity // order_item.quantity, 1)
        shipped_quantity = min(
            shipping_summary["shipped_quantity"] * unit_quantity,
            target_quantity,
        )
        completion_date = shipping_summary["completion_date"]
    else:
        shipped_quantity = item_shipping_summary["shipped_quantity"]
        completion_date = item_shipping_summary["completion_date"]
    remarks = [
        value.strip()
        for value in (order_item.remark, order.remark)
        if value and value.strip()
    ]
    part_no = (
        bom_item.part_no
        if bom_item
        else context.nodes.get(
            production_item.origin_flow_node_id,
            {},
        ).get("part_no")
        or product.factory_code
    )
    cells = {
        item.department_code: _empty_cell()
        for item in ordered_departments
    }
    route_nodes = _physical_route(context, production_item.origin_flow_node_id)
    department_workshops: dict[str, list[str]] = {}
    department_workshop_arrivals: dict[str, dict[str, int]] = {}
    department_workshop_completions: dict[str, dict[str, int]] = {}
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
        if node.get("type") in {"process", "assembly"}:
            workshop = _node_workshop(node, workshops, procedures)
            if workshop:
                names = department_workshops.setdefault(
                    department.department_code,
                    [],
                )
                if workshop.workshop_name not in names:
                    names.append(workshop.workshop_name)

    for movement in movements:
        target_node = context.nodes.get(movement.target_flow_node_id or "", {})
        target_workshop = _node_workshop(target_node, workshops, procedures)
        if target_workshop is None:
            continue
        target_department = department_by_id.get(target_workshop.department_id)
        if target_department is None:
            continue
        source_node = context.nodes.get(movement.source_flow_node_id or "", {})
        source_workshop = _node_workshop(source_node, workshops, procedures)
        if source_workshop and source_workshop.id == target_workshop.id:
            continue
        arrivals = department_workshop_arrivals.setdefault(
            target_department.department_code,
            {},
        )
        arrivals[target_workshop.workshop_name] = (
            arrivals.get(target_workshop.workshop_name, 0)
            + movement.quantity
        )

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
            progress = calculate_work_order_progress(work_order, order_batches)
            if work_order.status == "open":
                cell["processing_quantity"] += progress.processing_quantity
            workshop = _node_workshop(node, workshops, procedures)
            procedure = procedures.get(work_order.procedure_id)
            completion_is_final = (
                work_order.work_order_type != "tag"
                or (
                    procedure is not None
                    and is_final_tag_set(
                        session,
                        production_item,
                        procedure.id,
                        work_order.target_tag_set_id,
                    )
                )
            )
            if workshop and completion_is_final:
                completions = department_workshop_completions.setdefault(
                    department.department_code,
                    {},
                )
                completions[workshop.workshop_name] = (
                    completions.get(workshop.workshop_name, 0)
                    + progress.qualified_quantity
                )

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
            finished = cells.get("finished")
            if finished:
                finished["in_route"] = True
                finished["completed_quantity"] += movement.quantity

    return {
        "production_item_id": production_item.id,
        "customer_order_id": order.id,
        "customer_order_no": order.customer_order_no,
        "customer_name": customer.customer_name,
        "order_status": order.status,
        "factory_code": product.factory_code,
        "product_name": product.product_name,
        "part_no": part_no,
        "part_name": part_name,
        "part_display_name": f"{product.factory_code}-{product.product_name}-{part_name}",
        "target_quantity": target_quantity,
        "order_date": order.created_at.date().isoformat(),
        "shipped_quantity": shipped_quantity,
        "outstanding_quantity": max(target_quantity - shipped_quantity, 0),
        "completion_date": (
            completion_date
            if shipped_quantity >= target_quantity
            else None
        ),
        "remark": "；".join(dict.fromkeys(remarks)),
        "delivery_date": order_item.delivery_date.isoformat(),
        "departments": cells,
        "department_workshops": department_workshops,
        "department_workshop_arrivals": department_workshop_arrivals,
        "department_workshop_completions": department_workshop_completions,
        "search_text": " ".join((
            order.customer_order_no,
            customer.customer_name,
            product.factory_code,
            product.product_name,
            part_no,
            part_name,
        )).lower(),
    }


def _shipping_summary(session, order_item, movements: list) -> dict:
    flow, nodes = load_product_flow(
        session,
        order_item.product_id,
        order_item.product_version,
    )
    shipping_nodes = [
        node for node in nodes.values() if node.get("type") == "shipping"
    ]
    if len(shipping_nodes) != 1:
        return {"shipped_quantity": 0, "completion_date": None}
    shipping_node = shipping_nodes[0]
    unit_quantity = terminal_unit_quantity(
        session,
        flow,
        nodes,
        shipping_node["id"],
    )
    if not unit_quantity:
        return {"shipped_quantity": 0, "completion_date": None}
    shipments = sorted(
        (
            movement
            for movement in movements
            if movement.movement_type == "customer_shipment"
            and movement.target_flow_node_id == shipping_node["id"]
        ),
        key=lambda movement: (movement.created_at, movement.id),
    )
    shipped_material = sum(movement.quantity for movement in shipments)
    shipped_quantity = min(
        shipped_material // unit_quantity,
        order_item.quantity,
    )
    completion_date = None
    if shipped_quantity >= order_item.quantity:
        cumulative = 0
        target = order_item.quantity * unit_quantity
        for movement in shipments:
            cumulative += movement.quantity
            if cumulative >= target:
                completion_date = movement.created_at.date().isoformat()
                break
    return {
        "shipped_quantity": shipped_quantity,
        "completion_date": completion_date,
    }


def _production_item_shipping_summary(
    context,
    movements: list,
    target_quantity: int,
) -> dict:
    shipping_node_ids = {
        node["id"]
        for node in context.nodes.values()
        if node.get("type") == "shipping"
    }
    shipments = sorted(
        (
            movement
            for movement in movements
            if movement.movement_type == "customer_shipment"
            and movement.target_flow_node_id in shipping_node_ids
        ),
        key=lambda movement: (movement.created_at, movement.id),
    )
    shipped_quantity = min(
        sum(movement.quantity for movement in shipments),
        target_quantity,
    )
    completion_date = None
    if target_quantity and shipped_quantity >= target_quantity:
        cumulative = 0
        for movement in shipments:
            cumulative += movement.quantity
            if cumulative >= target_quantity:
                completion_date = movement.created_at.date().isoformat()
                break
    return {
        "shipped_quantity": shipped_quantity,
        "completion_date": completion_date,
    }


def _physical_route(context, origin_node_id: str) -> list[dict]:
    return _physical_route_nodes(
        context.flow,
        context.nodes,
        origin_node_id,
    )


def _physical_route_nodes(
    flow: dict,
    nodes: dict[str, dict],
    origin_node_id: str,
) -> list[dict]:
    route = []
    origin = nodes.get(origin_node_id)
    if origin and origin.get("type") == "assembly":
        route.append(origin)
    current = _normal_target(flow, nodes, origin_node_id)
    visited = set()
    while current and current["id"] not in visited:
        visited.add(current["id"])
        route.append(current)
        if current.get("type") == "assembly":
            break
        current = _normal_target(flow, nodes, current["id"])
    return route


def _normal_target(
    flow: dict,
    nodes: dict[str, dict],
    node_id: str,
) -> dict | None:
    targets = [
        nodes.get(edge.get("target_node_id"))
        for edge in flow.get("edges", [])
        if edge.get("source_node_id") == node_id
    ]
    targets = [item for item in targets if item is not None]
    return targets[0] if len(targets) == 1 else None


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
        "shipping": "finished",
    }.get(node_type)
    return department_by_code.get(code) if code else None


def _node_workshop(node, workshops, procedures):
    if node.get("type") not in {"process", "assembly"}:
        return None
    procedure = procedures.get(node.get("procedure_id"))
    return workshops.get(procedure.workshop_id) if procedure else None


def _department_workshop_names(
    route_nodes,
    department_code,
    department_by_code,
    workshops,
    procedures,
    origin_flow_node_id=None,
):
    names = []
    for node in route_nodes:
        department = _node_department(
            node,
            department_by_code,
            workshops,
            procedures,
        )
        if department is None or department.department_code != department_code:
            continue
        if node.get("type") == "assembly" and node.get("id") != origin_flow_node_id:
            continue
        if node.get("type") not in {"process", "assembly"}:
            continue
        workshop = _node_workshop(node, workshops, procedures)
        if workshop and workshop.workshop_name not in names:
            names.append(workshop.workshop_name)
    return names


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


def _group_rows_by_order(
    rows: list[dict],
    focus_order_id: int | None = None,
) -> list[dict]:
    orders: dict[int, dict] = {}
    for row in rows:
        order_id = row["customer_order_id"]
        group = orders.setdefault(
            order_id,
            {
                "customer_order_id": order_id,
                "customer_order_no": row["customer_order_no"],
                "customer_name": row["customer_name"],
                "order_status": row["order_status"],
                "parts": [],
            },
        )
        group["parts"].append(row)
    grouped = list(orders.values())
    if focus_order_id is not None:
        grouped.sort(
            key=lambda item: item["customer_order_id"] != focus_order_id
        )
    return grouped
