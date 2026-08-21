from departments.contracts import CAP_WORK_ORDERS
from modules.production_core import api as production


class WorkOrderCapability:
    def list_work_orders(
        self,
        *,
        page: int,
        page_size: int,
        production_item_id: int | None = None,
        flow_node_id: str | None = None,
        source_flow_node_id: str | None = None,
    ) -> tuple[list[dict], int]:
        self.require_capability(CAP_WORK_ORDERS)
        return production.list_department_work_orders(
            department_code=self.descriptor.code,
            page=page,
            page_size=page_size,
            production_item_id=production_item_id,
            flow_node_id=flow_node_id,
            source_flow_node_id=source_flow_node_id,
        )
