"""Department production-workbench position read-model orchestration."""

from sqlalchemy import select

from database import SessionLocal
from modules.errors import DomainError
from modules.organization.model_api import Department
from modules.planning.production_workbench_candidates import (
    _candidate_sort_key,
    _candidate_views,
    _filter_candidates,
    _group_candidates,
)
from modules.planning.production_workbench_queries import (
    _department_repositories,
    _load_display_data,
)
from modules.planning.production_workbench_serializers import _serialize_page
from modules.production_core.workbench_read_api import (
    load_workbench_activity,
    reserved_quantities,
)


def list_production_workbench_positions(
    department_code: str,
    page: int,
    page_size: int,
    customer_order_item_id: int,
    workshop_id: int,
    flow_node_id: str,
    production_item_id: int | None = None,
) -> tuple[list[dict], int]:
    with SessionLocal() as session:
        department = session.scalar(
            select(Department).where(Department.department_code == department_code)
        )
        if department is None:
            raise DomainError("department_not_found", "部门不存在", status_code=404)
        if department_code == "qc":
            return [], 0

        repositories = _department_repositories(
            session,
            department.id,
            customer_order_item_id=customer_order_item_id,
            production_item_id=production_item_id,
            flow_node_id=flow_node_id,
        )
        activity = load_workbench_activity(
            session,
            department.id,
            department_code,
            customer_order_item_id=customer_order_item_id,
            production_item_id=production_item_id,
            flow_node_id=flow_node_id,
        )
        item_ids = {repository.production_item_id for repository in repositories}
        item_ids.update(
            item_id
            for item in activity.standard.values()
            for item_id in item.production_item_ids
        )
        item_ids.update(
            item_id
            for item in activity.assembly.values()
            for item_id in item.production_item_ids
        )
        item_ids.update(
            allocation.production_item_id
            for allocation in activity.assembly_allocations
        )
        display = _load_display_data(
            session,
            item_ids,
            expand_order_items=production_item_id is None,
        )
        standard, assembly = _group_candidates(
            repositories,
            activity.standard,
            activity.assembly,
            activity.assembly_allocations,
            display,
        )
        reservation_by_id = reserved_quantities(
            session,
            [repository.id for repository in repositories],
        )
        candidates = _candidate_views(
            standard,
            assembly,
            display,
            department,
            reservation_by_id,
        )
        candidates = _filter_candidates(
            candidates,
            workshop_id,
            customer_order_item_id,
            production_item_id,
            flow_node_id,
        )
        candidates.sort(key=_candidate_sort_key, reverse=True)
        total = len(candidates)
        selected = candidates[(page - 1) * page_size:page * page_size]
        return _serialize_page(
            session,
            selected,
            display,
            department,
            reservation_by_id,
        ), total


__all__ = ["list_production_workbench_positions"]
