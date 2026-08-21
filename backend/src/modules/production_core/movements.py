from modules.production_core.persistence import ProductionItem, ProductionMovement


def record_movement(
    session,
    *,
    production_item: ProductionItem,
    quantity: int,
    movement_type: str,
    source_flow_node_id: str | None,
    target_flow_node_id: str | None,
    source_department_id: int | None = None,
    target_department_id: int | None = None,
    work_order_id: int | None = None,
    work_order_batch_id: int | None = None,
) -> ProductionMovement | None:
    if quantity <= 0:
        return None
    movement = ProductionMovement(
        production_item_id=production_item.id,
        source_flow_node_id=source_flow_node_id,
        target_flow_node_id=target_flow_node_id,
        source_department_id=source_department_id,
        target_department_id=target_department_id,
        quantity=quantity,
        movement_type=movement_type,
        work_order_id=work_order_id,
        work_order_batch_id=work_order_batch_id,
    )
    session.add(movement)
    return movement
