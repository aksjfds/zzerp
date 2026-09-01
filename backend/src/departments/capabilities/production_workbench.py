from departments.contracts import CAP_PRODUCTION_WORKBENCH
from modules.planning import api as planning


class ProductionWorkbenchCapability:
    def list_production_workbench_positions(
        self,
        page: int,
        page_size: int,
        customer_order_item_id: int,
        workshop_id: int,
        flow_node_id: str,
        production_item_id: int | None,
    ) -> tuple[list[dict], int]:
        self.require_capability(CAP_PRODUCTION_WORKBENCH)
        return planning.list_production_workbench_positions(
            self.descriptor.code,
            page,
            page_size,
            customer_order_item_id,
            workshop_id,
            flow_node_id,
            production_item_id,
        )
