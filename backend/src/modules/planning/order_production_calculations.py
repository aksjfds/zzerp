from __future__ import annotations

"""Customer-order production status calculations."""

from collections import defaultdict
from dataclasses import dataclass

from domain.production_types import (
    WORK_ORDER_STATUS_CANCELLED,
    WORK_ORDER_SUPPLIER_PROCESSING,
)
from modules.errors import DomainError
from modules.production_core.model_api import (
    ProductionMovement,
    Repository,
    WorkOrder,
    WorkOrderBatch,
)
from modules.sales.model_api import CustomerOrderItem
from modules.production_core.flow_api import assembly_material_key
from modules.production_core.operational_api import (
    calculate_supplier_processing_qc_progress,
    production_item_name,
    rework_pending_by_order,
)
from modules.planning.order_production_context import OrderProductionReadContext


@dataclass(frozen=True, slots=True)
class _SupplierProgressProjection:
    source_node_id: str
    supplier_node_id: str
    qc_node_id: str
    source_edge_id: str
    qc_edge_id: str
    task_quantity: int
    inspected_quantity: int
    remaining_qualified_quantity: int
    pending_destination_quantity: int
    abnormal_quantity: int


@dataclass(frozen=True, slots=True)
class _OrderItemProgressData:
    repositories: list[Repository]
    movements: list[ProductionMovement]
    work_orders: list[WorkOrder]
    work_order_batches: list[WorkOrderBatch]
    batches_by_id: dict[int, WorkOrderBatch]
    pending_finished_quantity: int
    received_finished_quantity: int


@dataclass(slots=True)
class _ProgressTotals:
    current_by_node: dict[str, int]
    current_inputs: dict[str, dict[str, int]]
    current_repository_sources: dict[str, dict[str, list[Repository]]]
    pending_rework_by_node: dict[str, int]
    material_inputs: dict[str, dict[str, int]]
    entered_by_node: dict[str, int]
    transferred_by_node: dict[str, int]
    transferred_by_edge: dict[str, int]
    abnormal_by_node: dict[str, int]
    assembly_output_by_node: dict[str, int]
    internal_process_returns: dict[str, int]
    process_abnormal_by_node: dict[str, int]


def _calculate_order_item_state(
    context: OrderProductionReadContext,
    order_item: CustomerOrderItem,
    flow: dict,
    nodes: dict[str, dict],
) -> dict:
    data = _load_order_item_progress_data(context, order_item)
    totals = _initialize_progress_totals(context, data)
    edge_id_by_nodes, targets_by_source = _flow_connections(flow)
    _apply_supplier_projections(
        context, data, totals, nodes, edge_id_by_nodes, targets_by_source
    )
    _apply_production_movements(
        context, data, totals, edge_id_by_nodes
    )
    stats = _build_node_stats(context, data, totals, flow, nodes)
    transferred_by_node = {
        item["flow_node_id"]: item["transferred_quantity"] for item in stats
    }
    return {
        "node_stats": stats,
        "edge_stats": [
            {
                "flow_edge_id": edge["id"],
                "transferred_quantity": transferred_by_node.get(
                    edge["source_node_id"],
                    totals.transferred_by_edge[edge["id"]],
                ),
            }
            for edge in flow.get("edges", [])
        ],
    }


def _load_order_item_progress_data(
    context: OrderProductionReadContext,
    order_item: CustomerOrderItem,
) -> _OrderItemProgressData:
    production_items = context.production_items_by_order_item.get(order_item.id, [])
    production_item_ids = [item.id for item in production_items]
    repositories = [
        repository
        for item_id in production_item_ids
        for repository in context.repositories_by_item.get(item_id, [])
    ]
    movements = [
        movement
        for item_id in production_item_ids
        for movement in context.movements_by_item.get(item_id, [])
    ]
    work_orders = [
        work_order
        for item_id in production_item_ids
        for work_order in context.work_orders_by_item.get(item_id, [])
    ]
    work_order_batches = [
        batch
        for work_order in work_orders
        for batch in context.batches_by_order.get(work_order.id, [])
    ]
    receipt_states = [
        context.finished_receipts_by_batch[batch.id]
        for batch in work_order_batches
        if batch.id in context.finished_receipts_by_batch
    ]
    return _OrderItemProgressData(
        repositories=repositories,
        movements=movements,
        work_orders=work_orders,
        work_order_batches=work_order_batches,
        batches_by_id={batch.id: batch for batch in work_order_batches},
        pending_finished_quantity=sum(
            quantity for status, quantity in receipt_states if status == "pending"
        ),
        received_finished_quantity=sum(
            quantity for status, quantity in receipt_states if status == "received"
        ),
    )


def _empty_progress_totals() -> _ProgressTotals:
    nested_ints = lambda: defaultdict(int)
    nested_repositories = lambda: defaultdict(list)
    return _ProgressTotals(
        current_by_node=defaultdict(int),
        current_inputs=defaultdict(nested_ints),
        current_repository_sources=defaultdict(nested_repositories),
        pending_rework_by_node=defaultdict(int),
        material_inputs=defaultdict(nested_ints),
        entered_by_node=defaultdict(int),
        transferred_by_node=defaultdict(int),
        transferred_by_edge=defaultdict(int),
        abnormal_by_node=defaultdict(int),
        assembly_output_by_node=defaultdict(int),
        internal_process_returns=defaultdict(int),
        process_abnormal_by_node=defaultdict(int),
    )


def _initialize_progress_totals(
    context: OrderProductionReadContext,
    data: _OrderItemProgressData,
) -> _ProgressTotals:
    totals = _empty_progress_totals()
    for repository in data.repositories:
        node_id = repository.flow_node_id
        totals.current_by_node[node_id] += repository.quantity
        totals.current_repository_sources[node_id][
            repository.source_flow_node_id
        ].append(repository)
        production_item = context.display.production_items.get(
            repository.production_item_id
        )
        source_name = (
            production_item_name(
                context.session, production_item, set(), context.display
            )
            if production_item
            else "未知来源"
        )
        totals.current_inputs[node_id][source_name] += repository.quantity
    pending_qc_by_node = _pending_qc_quantities(data)
    for node_id, quantity in pending_qc_by_node.items():
        totals.current_by_node[node_id] += quantity
    for movement in data.movements:
        if (
            movement.movement_type == "qc_qualified"
            and movement.source_flow_node_id == movement.target_flow_node_id
            and movement.source_department_id == movement.target_department_id
            and movement.target_flow_node_id
        ):
            totals.current_by_node[movement.target_flow_node_id] += max(
                movement.quantity, 0
            )
    tracked_order_ids = {
        order.id
        for order in data.work_orders
        if order.work_order_type != WORK_ORDER_SUPPLIER_PROCESSING
    }
    pending_rework = rework_pending_by_order(
        batch
        for batch in data.work_order_batches
        if batch.work_order_id in tracked_order_ids
    )
    for work_order in data.work_orders:
        quantity = pending_rework.get(work_order.id, 0)
        totals.current_by_node[work_order.flow_node_id] += quantity
        totals.pending_rework_by_node[work_order.flow_node_id] += quantity
    return totals


def _pending_qc_quantities(data: _OrderItemProgressData) -> dict[str, int]:
    result: dict[str, int] = defaultdict(int)
    for movement in data.movements:
        batch = data.batches_by_id.get(movement.work_order_batch_id)
        pending_destination = (
            batch is not None
            and batch.recorded_at is not None
            and (batch.qualified_quantity or 0) > 0
            and batch.destination_decided_at is None
        )
        if (
            batch is not None
            and (batch.recorded_at is None or pending_destination)
            and movement.target_flow_node_id
            and movement.movement_type in {"process", "assembly_output"}
        ):
            result[movement.target_flow_node_id] += (
                int(batch.qualified_quantity or 0)
                if pending_destination
                else batch.submitted_quantity
            )
    return result


def _flow_connections(
    flow: dict,
) -> tuple[dict[tuple[str, str], str], dict[str, list[str]]]:
    edge_id_by_nodes = {
        (edge["source_node_id"], edge["target_node_id"]): edge["id"]
        for edge in flow.get("edges", [])
    }
    targets_by_source: dict[str, list[str]] = defaultdict(list)
    for edge in flow.get("edges", []):
        targets_by_source[edge["source_node_id"]].append(edge["target_node_id"])
    return edge_id_by_nodes, targets_by_source


def _apply_supplier_projections(
    context: OrderProductionReadContext,
    data: _OrderItemProgressData,
    totals: _ProgressTotals,
    nodes: dict[str, dict],
    edge_id_by_nodes: dict[tuple[str, str], str],
    targets_by_source: dict[str, list[str]],
) -> None:
    projections = _supplier_progress_projections(
        work_orders=data.work_orders,
        batches_by_order=context.batches_by_order,
        nodes=nodes,
        target_node_ids_by_source=targets_by_source,
        edge_id_by_nodes=edge_id_by_nodes,
    )
    for projection in projections:
        supplier_id = projection.supplier_node_id
        totals.entered_by_node[supplier_id] += projection.task_quantity
        totals.current_by_node[supplier_id] += projection.remaining_qualified_quantity
        totals.transferred_by_node[supplier_id] += projection.inspected_quantity
        totals.abnormal_by_node[supplier_id] += projection.abnormal_quantity
        totals.transferred_by_node[
            projection.source_node_id
        ] += projection.task_quantity
        totals.transferred_by_edge[
            projection.source_edge_id
        ] += projection.task_quantity
        totals.transferred_by_edge[
            projection.qc_edge_id
        ] += projection.inspected_quantity
        totals.current_by_node[
            projection.qc_node_id
        ] += projection.pending_destination_quantity
        totals.abnormal_by_node[
            projection.qc_node_id
        ] += projection.abnormal_quantity


def _apply_production_movements(
    context: OrderProductionReadContext,
    data: _OrderItemProgressData,
    totals: _ProgressTotals,
    edge_id_by_nodes: dict[tuple[str, str], str],
) -> None:
    work_order_by_id = {order.id: order for order in data.work_orders}
    for movement in data.movements:
        work_order = work_order_by_id.get(movement.work_order_id)
        _apply_movement_quantities(
            totals, movement, work_order, edge_id_by_nodes
        )
        batch = data.batches_by_id.get(movement.work_order_batch_id)
        if (
            movement.movement_type == "assembly_output"
            and movement.source_flow_node_id
            and (batch is None or batch.rework_source_batch_id is None)
        ):
            totals.assembly_output_by_node[
                movement.source_flow_node_id
            ] += movement.quantity
        if (
            movement.movement_type == "assembly_input"
            and movement.source_flow_node_id
        ):
            production_item = context.display.production_items.get(
                movement.production_item_id
            )
            source_name = (
                production_item_name(
                    context.session, production_item, set(), context.display
                )
                if production_item
                else "未知来源"
            )
            totals.material_inputs[
                movement.source_flow_node_id
            ][source_name] += movement.quantity


def _apply_movement_quantities(
    totals: _ProgressTotals,
    movement: ProductionMovement,
    work_order: WorkOrder | None,
    edge_id_by_nodes: dict[tuple[str, str], str],
) -> None:
    source_id = movement.source_flow_node_id
    target_id = movement.target_flow_node_id
    if (
        target_id
        and movement.movement_type in {"qc_qualified", "qc_rework"}
        and work_order is not None
        and work_order.flow_node_id == target_id
    ):
        totals.internal_process_returns[target_id] += movement.quantity
    if target_id and target_id != source_id:
        totals.entered_by_node[target_id] += movement.quantity
    leaves_source = target_id != source_id and (
        target_id is not None
        or movement.work_order_batch_id is None
        or movement.movement_type in {"qc_qualified", "qc_inventory"}
    )
    if (
        source_id
        and movement.movement_type not in {"scrap", "lost"}
        and leaves_source
    ):
        totals.transferred_by_node[source_id] += movement.quantity
    if source_id and movement.movement_type in {"scrap", "lost"}:
        totals.abnormal_by_node[source_id] += movement.quantity
        if work_order is not None:
            totals.process_abnormal_by_node[
                work_order.flow_node_id
            ] += movement.quantity
    edge_id = edge_id_by_nodes.get((source_id, target_id))
    if edge_id is not None:
        totals.transferred_by_edge[edge_id] += movement.quantity


def _build_node_stats(
    context: OrderProductionReadContext,
    data: _OrderItemProgressData,
    totals: _ProgressTotals,
    flow: dict,
    nodes: dict[str, dict],
) -> list[dict]:
    process_totals = {
        node["id"]: _process_node_totals(
            totals.entered_by_node[node["id"]],
            totals.internal_process_returns[node["id"]],
            totals.current_by_node[node["id"]],
            totals.process_abnormal_by_node[node["id"]],
        )
        for node in flow.get("nodes", [])
        if node.get("type") == "process"
    }
    node_types = {
        node["id"]: node.get("type") for node in flow.get("nodes", [])
    }
    qc_totals = {
        node["id"]: _qc_node_totals(
            [
                (
                    process_totals[source_id][1]
                    if node_types.get(source_id) == "process"
                    else totals.transferred_by_edge[edge["id"]]
                )
                for edge in flow.get("edges", [])
                if edge["target_node_id"] == node["id"]
                for source_id in [edge["source_node_id"]]
            ],
            totals.current_by_node[node["id"]],
            totals.abnormal_by_node[node["id"]],
        )
        for node in flow.get("nodes", [])
        if node.get("type") == "qc"
    }
    return [
        _node_stat(context, data, totals, flow, nodes, node, process_totals, qc_totals)
        for node in flow.get("nodes", [])
    ]


def _node_stat(
    context: OrderProductionReadContext,
    data: _OrderItemProgressData,
    totals: _ProgressTotals,
    flow: dict,
    nodes: dict[str, dict],
    node: dict,
    process_totals: dict[str, tuple[int, int]],
    qc_totals: dict[str, tuple[int, int]],
) -> dict:
    node_id = node["id"]
    node_type = node.get("type")
    current = totals.current_by_node[node_id]
    entered = totals.entered_by_node[node_id]
    transferred = totals.transferred_by_node[node_id]
    abnormal = totals.abnormal_by_node[node_id]
    input_details: dict[str, int] = {}
    output_quantity = 0
    if node_type == "part":
        entered = transferred
        current = max(entered - transferred, 0)
    elif node_type == "process":
        abnormal = totals.process_abnormal_by_node[node_id]
        entered, transferred = process_totals[node_id]
    elif node_type == WORK_ORDER_SUPPLIER_PROCESSING:
        entered = totals.entered_by_node[node_id]
        transferred = totals.transferred_by_node[node_id]
    elif node_type == "qc":
        entered, transferred = qc_totals[node_id]
    elif node_type == "assembly":
        input_details = _assembly_input_details(totals, node_id)
        output_quantity = totals.assembly_output_by_node[node_id]
        output_pcs = int(node.get("output_pcs", 1))
        transferred = output_quantity // output_pcs if output_pcs else 0
        current = _assembly_current_quantity(
            context, totals, flow, nodes, node_id
        )
    elif node_type == "finished_inbound":
        entered = (
            data.pending_finished_quantity + data.received_finished_quantity
        )
        current = data.pending_finished_quantity
        transferred = data.received_finished_quantity
        output_quantity = entered
    return {
        "flow_node_id": node_id,
        "node_type": node_type,
        "current_quantity": current,
        "entered_quantity": entered,
        "transferred_quantity": transferred,
        "abnormal_quantity": abnormal,
        "output_quantity": output_quantity,
        "pending_receipt_quantity": (
            data.pending_finished_quantity
            if node_type == "finished_inbound"
            else 0
        ),
        "received_quantity": (
            data.received_finished_quantity
            if node_type == "finished_inbound"
            else 0
        ),
        "input_details": input_details,
    }


def _assembly_input_details(
    totals: _ProgressTotals,
    node_id: str,
) -> dict[str, int]:
    result = dict(totals.current_inputs[node_id])
    for name, quantity in totals.material_inputs[node_id].items():
        result[name] = result.get(name, 0) + quantity
    return result


def _assembly_current_quantity(
    context: OrderProductionReadContext,
    totals: _ProgressTotals,
    flow: dict,
    nodes: dict[str, dict],
    node_id: str,
) -> int:
    source_ids = {
        edge["source_node_id"]
        for edge in flow.get("edges", [])
        if edge["target_node_id"] == node_id
    }
    source_groups: dict[str, list[str]] = defaultdict(list)
    for source_id in source_ids:
        material_key = assembly_material_key(flow, nodes, source_id)
        if material_key is not None:
            source_groups[material_key].append(source_id)
    capacities = [
        _assembly_source_capacity(
            context,
            [
                repository
                for source_id in source_group
                for repository in totals.current_repository_sources[node_id].get(
                    source_id, []
                )
            ],
            nodes,
        )
        for source_group in source_groups.values()
    ]
    return min(capacities, default=0) + totals.pending_rework_by_node[node_id]


def _assembly_source_capacity(
    context: OrderProductionReadContext,
    repositories: list[Repository],
    nodes: dict[str, dict],
) -> int:
    if not repositories:
        return 0
    first_item = context.display.production_items.get(
        repositories[0].production_item_id
    )
    bom_item = (
        context.bom_items.get(first_item.product_bom_id)
        if first_item and first_item.product_bom_id
        else None
    )
    unit_quantity = (
        bom_item.pcs
        if bom_item
        else int(
            nodes.get(
                first_item.origin_flow_node_id if first_item else "", {}
            ).get("output_pcs", 1)
        )
    )
    source_quantity = sum(repository.quantity for repository in repositories)
    return source_quantity // unit_quantity if unit_quantity else 0
def _supplier_progress_projections(
    *,
    work_orders,
    batches_by_order,
    nodes: dict[str, dict],
    target_node_ids_by_source: dict[str, list[str]],
    edge_id_by_nodes: dict[tuple[str, str], str],
) -> list[_SupplierProgressProjection]:
    projections = []
    for work_order in work_orders:
        if (
            work_order.work_order_type != WORK_ORDER_SUPPLIER_PROCESSING
            or work_order.status == WORK_ORDER_STATUS_CANCELLED
        ):
            continue
        source_node_id = work_order.source_flow_node_id
        supplier_node_id = work_order.flow_node_id
        qc_node_ids = [
            node_id
            for node_id in target_node_ids_by_source.get(supplier_node_id, [])
            if nodes.get(node_id, {}).get("type") == "qc"
        ]
        source_edge_id = edge_id_by_nodes.get(
            (source_node_id, supplier_node_id)
        ) if source_node_id is not None else None
        if source_node_id is None or source_edge_id is None or len(qc_node_ids) != 1:
            raise DomainError(
                "supplier_processing_flow_invalid",
                "委外加工工单绑定的生产流程不完整",
                status_code=409,
            )
        qc_node_id = qc_node_ids[0]
        qc_edge_id = edge_id_by_nodes.get((supplier_node_id, qc_node_id))
        if qc_edge_id is None:
            raise DomainError(
                "supplier_processing_flow_invalid",
                "委外加工工单缺少直连 QC 线路",
                status_code=409,
            )
        progress = calculate_supplier_processing_qc_progress(
            work_order,
            batches_by_order.get(work_order.id, []),
        )
        projections.append(_SupplierProgressProjection(
            source_node_id=source_node_id,
            supplier_node_id=supplier_node_id,
            qc_node_id=qc_node_id,
            source_edge_id=source_edge_id,
            qc_edge_id=qc_edge_id,
            task_quantity=work_order.quantity,
            inspected_quantity=progress.inspected_quantity,
            remaining_qualified_quantity=progress.remaining_qualified_quantity,
            pending_destination_quantity=progress.pending_destination_quantity,
            abnormal_quantity=(
                progress.rework_quantity
                + progress.scrap_quantity
                + progress.lost_quantity
            ),
        ))
    return projections


def _process_node_totals(
    recorded_entered: int,
    internal_returned: int,
    current: int,
    abnormal: int,
) -> tuple[int, int]:
    entered = max(recorded_entered - internal_returned, 0)
    transferred = max(entered - current - abnormal, 0)
    return entered, transferred


def _qc_node_totals(
    incoming_quantities: list[int],
    current: int,
    abnormal: int,
) -> tuple[int, int]:
    entered = sum(incoming_quantities)
    transferred = max(entered - current - abnormal, 0)
    return entered, transferred
