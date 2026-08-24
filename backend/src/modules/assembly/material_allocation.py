from __future__ import annotations

"""Assembly material allocation and output-item resolution."""

from collections import defaultdict
from sqlalchemy import select
from domain.assembly import required_material_quantity
from modules.production_core.model_api import WorkOrderMaterial
from modules.errors import DomainError
from domain.material_identity import production_item_material_key
from modules.production_core.assembly_api import assembly_item_unit_quantity, open_work_order_ids
from modules.production_core.context_api import InventorySourceContext, ProductionItemContext
from modules.production_core.model_api import ProductionItem
from modules.production_core.ownership_api import create_production_item

def _validate_material_allocations(
    session,
    repositories: list[InventorySourceContext],
    input_items: list[ProductionItemContext],
    requested_quantities: dict[int, int],
    quantity: int,
) -> dict[int, int]:
    repositories_by_source: dict[
        str,
        list[tuple[InventorySourceContext, ProductionItemContext]],
    ] = {}
    for repository, input_item in zip(repositories, input_items, strict=True):
        repositories_by_source.setdefault(production_item_material_key(input_item), []).append(
            (repository, input_item)
        )

    repository_ids = {repository.id for repository in repositories}
    material_rows = session.execute(
        select(
            WorkOrderMaterial.repository_id,
            WorkOrderMaterial.work_order_id,
            WorkOrderMaterial.quantity,
        ).where(WorkOrderMaterial.repository_id.in_(repository_ids))
    ).all()
    open_ids = open_work_order_ids(
        session,
        {row.work_order_id for row in material_rows},
    )
    reserved_by_repository: dict[int, int] = defaultdict(int)
    for row in material_rows:
        if row.repository_id is not None and row.work_order_id in open_ids:
            reserved_by_repository[row.repository_id] += row.quantity

    for material_key, source_repositories in repositories_by_source.items():
        first_item = source_repositories[0][1]
        required_quantity = required_material_quantity(
            quantity,
            assembly_item_unit_quantity(session, first_item),
        )
        selected_quantity = sum(
            requested_quantities[repository.id]
            for repository, _ in source_repositories
        )
        if selected_quantity != required_quantity:
            raise DomainError(
                "assembly_material_quantity_mismatch",
                f"同一物料的来源数量合计必须为 {required_quantity}",
            )
        for repository, _ in source_repositories:
            reserved = reserved_by_repository[repository.id]
            if requested_quantities[repository.id] > max(repository.quantity - reserved, 0):
                raise DomainError(
                    "assembly_quantity_exceeded",
                    "所填来源数量超过当前可用数量",
                )
    return {
        repository_id: material_quantity
        for repository_id, material_quantity in requested_quantities.items()
        if material_quantity > 0
    }

def _get_or_create_output_item(
    session,
    *,
    customer_order_item_id: int,
    product_id: int,
    product_version: int,
    assembly_node_id: str,
):
    output_item = session.scalar(
        select(ProductionItem)
        .where(
            ProductionItem.customer_order_item_id == customer_order_item_id,
            ProductionItem.product_id == product_id,
            ProductionItem.product_version == product_version,
            ProductionItem.product_bom_id.is_(None),
            ProductionItem.origin_flow_node_id == assembly_node_id,
        )
        .with_for_update()
    )
    if output_item is not None:
        return output_item
    return create_production_item(
        session,
        customer_order_item_id=customer_order_item_id,
        product_id=product_id,
        product_version=product_version,
        product_bom_id=None,
        origin_flow_node_id=assembly_node_id,
    )
