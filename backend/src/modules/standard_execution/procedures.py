from modules.organization.context_api import ProcedureContext
from modules.organization.read_api import get_workshop_routes
from modules.errors import DomainError


def procedure_department_id(session, procedure: ProcedureContext) -> int:
    workshop = get_workshop_routes(session, {procedure.workshop_id}).get(
        procedure.workshop_id
    )
    if workshop is None:
        raise DomainError("procedure_department_missing", "工艺所属车间不存在")
    return workshop.department_id


def material_key(production_item) -> str:
    if production_item.product_bom_id is not None:
        return f"part:{production_item.product_bom_id}"
    return f"assembly:{production_item.origin_flow_node_id}"


__all__ = ["material_key", "procedure_department_id"]
