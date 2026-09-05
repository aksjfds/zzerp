from __future__ import annotations

"""Assembly work-order creation transaction."""

from database import SessionLocal
from domain.identity import can_access_department
from domain.material_identity import production_item_material_key
from domain.time import business_now
from modules.assembly.material_allocation import (
    _get_or_create_output_item,
    _validate_material_allocations,
)
from modules.errors import DomainError
from modules.organization.model_api import Workshop
from modules.organization.read_api import get_department_ids_by_codes
from modules.planning.execution_api import ensure_production_plan_active
from modules.production_core.assembly_api import (
    assign_assembly_work_order_number,
    load_production_items,
    load_repositories,
)
from modules.production_core.flow_api import assembly_material_key
from modules.production_core.operational_api import (
    consume_repository,
    node_context,
    record_movement,
    serialize_work_order,
)
from modules.production_core.ownership_api import (
    assign_work_order_material_repository,
    create_assembly_work_order_record,
    create_work_order_material,
)
from modules.production_core.reference_api import reserved_repository_quantities
from modules.production_core.transaction_api import (
    ensure_source_procedure_not_repeated,
)
from modules.sales.transaction_api import mark_order_planned
from modules.standard_execution.configuration_api import resolve_work_order_procedure
from modules.standard_execution.pricing_api import attach_work_order_price
from modules.standard_execution.procedure_api import material_key
from modules.workforce.reference_api import get_worker_reference


def create_assembly_work_order(
    materials: list[dict],
    procedure_id: int | None,
    procedure_name: str | None,
    is_temporary: bool,
    quantity: int,
    worker_id: int | None,
    remark: str | None,
    actor_username: str,
    user_department: str | None,
    user_is_system: bool,
) -> dict:
    if not can_access_department(user_department, user_is_system, "assembly"):
        raise DomainError("department_access_denied", "只有装配部可以开装配工单", status_code=403)
    with SessionLocal.begin() as session:
        requested_quantities: dict[int, int] = {}
        for material in materials:
            repository_id = int(material["repository_id"])
            if repository_id in requested_quantities:
                raise DomainError("assembly_material_duplicate", "同一物料来源不能重复填写")
            requested_quantities[repository_id] = int(material["quantity"])
        unique_repository_ids = sorted(requested_quantities)
        repositories = load_repositories(
            session,
            unique_repository_ids,
            for_update=True,
        )
        if not repositories or len(repositories) != len(unique_repository_ids):
            raise DomainError("assembly_inputs_invalid", "请选择有效的工单输入物料")
        input_items_by_id = load_production_items(
            session,
            {repository.production_item_id for repository in repositories},
        )
        input_items = [
            input_items_by_id[repository.production_item_id]
            for repository in repositories
        ]
        ensure_production_plan_active(
            session,
            input_items[0].customer_order_item_id,
        )
        order_item_ids = {item.customer_order_item_id for item in input_items}
        node_ids = {item.flow_node_id for item in repositories}
        if len(order_item_ids) != 1 or len(node_ids) != 1:
            raise DomainError("assembly_inputs_mismatch", "多路工艺输入必须属于同一订单明细和工艺节点")

        context, assembly_node = node_context(
            session, input_items[0], repositories[0].flow_node_id
        )
        if assembly_node.get("type") != "assembly":
            raise DomainError("assembly_node_invalid", "所选物料不在多路工艺节点")
        workshop_id = assembly_node.get("workshop_id")
        if not isinstance(workshop_id, int):
            raise DomainError("assembly_workshop_invalid", "多路节点未配置车间")
        procedure = resolve_work_order_procedure(
            session,
            scope=(
                input_items[0].product_id,
                input_items[0].product_version,
                f"assembly:{assembly_node['id']}",
                assembly_node["id"],
            ),
            workshop_id=workshop_id,
            procedure_id=procedure_id,
            procedure_name=procedure_name,
            is_temporary=is_temporary,
            required_input_mode="multiple",
        )
        ensure_source_procedure_not_repeated(
            session,
            {repository.source_work_order_id for repository in repositories},
            assembly_node["id"],
            procedure.id,
            {repository.processing_state_id for repository in repositories},
        )
        continuation = (
            len(repositories) == 1
            and input_items[0].product_bom_id is None
            and input_items[0].origin_flow_node_id == assembly_node["id"]
        )
        expected_sources = [
            edge.get("source_node_id")
            for edge in context.flow.get("edges", [])
            if edge.get("target_node_id") == assembly_node["id"]
        ]
        expected_materials = {
            key
            for source_id in expected_sources
            if (key := assembly_material_key(context.flow, context.nodes, source_id))
        }
        selected_materials = {
            production_item_material_key(item) for item in input_items
        }
        if not continuation and (not expected_materials or expected_materials != selected_materials):
            raise DomainError("assembly_inputs_incomplete", "必须填写多路工艺节点的全部输入物料")

        assembly_department_id = get_department_ids_by_codes(
            session,
            {"assembly"},
        ).get("assembly")
        worker = get_worker_reference(session, worker_id) if worker_id else None
        workshop = session.get(Workshop, procedure.workshop_id)
        if workshop is None or workshop.department_id != assembly_department_id:
            raise DomainError("assembly_procedure_invalid", "多路工艺不属于装配部")
        if worker_id and (
            worker is None
            or worker.department_id != assembly_department_id
            or worker.workshop_id != procedure.workshop_id
        ):
            raise DomainError("worker_invalid", "工人不属于当前装配工艺车间")

        if continuation:
            repository = repositories[0]
            reserved = reserved_repository_quantities(
                session,
                {repository.id},
            ).get(repository.id, 0)
            if (
                requested_quantities[repository.id] != quantity
                or quantity > max(repository.quantity - reserved, 0)
            ):
                raise DomainError("assembly_quantity_exceeded", "后续工艺数量必须等于所选在制数量")
            material_quantities = {repository.id: quantity}
        else:
            material_quantities = _validate_material_allocations(
                session,
                repositories,
                input_items,
                requested_quantities,
                quantity,
            )
        output_item = _get_or_create_output_item(
            session,
            customer_order_item_id=input_items[0].customer_order_item_id,
            product_id=input_items[0].product_id,
            product_version=input_items[0].product_version,
            assembly_node_id=assembly_node["id"],
        )
        order = create_assembly_work_order_record(
            session,
            production_item_id=output_item.id,
            procedure=procedure,
            flow_node_id=assembly_node["id"],
            work_order_name=procedure.procedure_name,
            created_by=actor_username,
            worker_id=worker_id,
            worker_name=worker.worker_name if worker else None,
            quantity=quantity,
            remark=remark,
            is_temporary=is_temporary,
            repository_id=repositories[0].id if continuation else None,
            source_processing_state_id=(
                repositories[0].processing_state_id if continuation else None
            ),
        )
        mark_order_planned(session, input_items[0].customer_order_item_id)
        assign_assembly_work_order_number(
            order,
            f"WO-{business_now():%Y%m%d}-{order.id:06d}",
        )
        attach_work_order_price(
            session,
            work_order_id=order.id,
            product_id=output_item.product_id,
            product_version=output_item.product_version,
            material_key=material_key(output_item),
            flow_node_id=assembly_node["id"],
            procedure_id=procedure.id,
            procedure_name=procedure.procedure_name,
            is_temporary=is_temporary,
        )
        if continuation:
            repository = repositories[0]
            create_work_order_material(
                session,
                work_order_id=order.id,
                repository_id=None,
                production_item_id=repository.production_item_id,
                source_processing_state_id=repository.processing_state_id,
                quantity=quantity,
                source_flow_node_id=repository.flow_node_id,
                source_previous_flow_node_id=repository.source_flow_node_id,
                source_department_id=repository.department_id,
                source_work_order_id=repository.source_work_order_id,
            )
            session.flush()
            return serialize_work_order(session, order)
        allocated_materials = []
        for repository, input_item in zip(repositories, input_items, strict=True):
            material_quantity = material_quantities.get(repository.id)
            if material_quantity:
                material_row = create_work_order_material(
                    session,
                    work_order_id=order.id,
                    repository_id=repository.id,
                    production_item_id=repository.production_item_id,
                    source_processing_state_id=repository.processing_state_id,
                    quantity=material_quantity,
                    source_flow_node_id=repository.flow_node_id,
                    source_previous_flow_node_id=repository.source_flow_node_id,
                    source_department_id=repository.department_id,
                    source_work_order_id=repository.source_work_order_id,
                )
                allocated_materials.append(
                    (material_row, repository, input_item, material_quantity)
                )
        session.flush()
        for (
            material_row,
            repository,
            input_item,
            material_quantity,
        ) in allocated_materials:
            record_movement(
                session,
                production_item=input_item,
                quantity=material_quantity,
                movement_type="assembly_input",
                source_flow_node_id=repository.flow_node_id,
                target_flow_node_id=None,
                source_department_id=repository.department_id,
                work_order=order,
                work_order_material_id=material_row.id,
            )
            assign_work_order_material_repository(material_row, None)
            session.flush()
            consume_repository(session, repository, material_quantity)
        session.flush()
        return serialize_work_order(session, order)
