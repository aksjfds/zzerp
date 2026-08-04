"""Convert eligible order surplus into pending cross-order inventory receipts."""

from sqlalchemy import select
from sqlalchemy.orm import Session

from modules.engineering.model_api import ProductBom
from modules.inventory.finished_goods_api import transfer_order_finished_surplus
from modules.inventory.identity import inventory_identity_key
from modules.inventory.ownership_api import confirm_receipt, create_receipt
from modules.production_core.persistence import ProductionItem, Repository


def create_order_surplus_receipts(
    session: Session,
    customer_order,
    actor_username: str = "system",
) -> None:
    from modules.production_core.flow import load_product_flow
    from modules.production_core.work_order_support import consume_repository

    for order_item in customer_order.items:
        _flow, nodes = load_product_flow(session, order_item.product_id, order_item.product_version)
        repositories = list(session.scalars(
            select(Repository)
            .join(ProductionItem, ProductionItem.id == Repository.production_item_id)
            .where(ProductionItem.customer_order_item_id == order_item.id)
            .with_for_update()
        ))
        for repository in repositories:
            production_item = session.get(ProductionItem, repository.production_item_id)
            target = nodes.get(repository.flow_node_id, {})
            origin = nodes.get(production_item.origin_flow_node_id, {}) if production_item else {}
            if production_item is None or not _warehouse_eligible(production_item, target, origin):
                continue
            if production_item.product_bom_id is not None:
                bom = session.get(ProductBom, production_item.product_bom_id)
                if bom is None:
                    continue
                item_type = "part"
                item_code = bom.part_no
                item_name = bom.part_name
            else:
                item_type = "assembly"
                item_code = origin.get("assembly_code")
                item_name = origin.get("assembly_name") or origin.get("output_name")
                if not item_code or not item_name:
                    continue
            identity_key = inventory_identity_key(
                department_code="warehouse",
                item_type=item_type,
                product_id=production_item.product_id,
                product_version=production_item.product_version,
                product_bom_id=production_item.product_bom_id,
                flow_node_id=production_item.origin_flow_node_id,
            )
            receipt = create_receipt(
                session,
                identity_key=identity_key,
                department_code="warehouse",
                item_type=item_type,
                product_id=production_item.product_id,
                product_version=production_item.product_version,
                product_bom_id=production_item.product_bom_id,
                flow_node_id=production_item.origin_flow_node_id,
                item_code=item_code,
                item_name=item_name,
                quantity=repository.quantity,
                source_customer_order_id=customer_order.id,
                source_production_item_id=production_item.id,
            )
            confirm_receipt(session, receipt.id, actor_username)
            consume_repository(session, repository, repository.quantity)
    transfer_order_finished_surplus(session, customer_order, actor_username)


def _warehouse_eligible(production_item, target: dict, origin: dict) -> bool:
    if production_item.product_bom_id is not None:
        return target.get("type") == "assembly"
    return origin.get("type") == "assembly" and target.get("type") in {"assembly", "shipping"}


__all__ = ["create_order_surplus_receipts"]
