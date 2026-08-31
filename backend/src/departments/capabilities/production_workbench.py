from departments.contracts import CAP_PRODUCTION_WORKBENCH
from domain.production_workbench import (
    ProductionWorkbenchAttention,
    ProductionWorkbenchPositionType,
)
from modules.planning import api as planning


class ProductionWorkbenchCapability:
    def list_production_workbench_positions(
        self,
        page: int,
        page_size: int,
        keyword: str | None,
        workshop_name: str | None,
        attention: ProductionWorkbenchAttention,
    ) -> tuple[list[dict], int]:
        self.require_capability(CAP_PRODUCTION_WORKBENCH)
        return planning.list_production_workbench_positions(
            self.descriptor.code,
            page,
            page_size,
            keyword,
            workshop_name,
            attention,
        )

    def list_production_workbench_work_orders(
        self,
        position_type: ProductionWorkbenchPositionType,
        page: int,
        page_size: int,
        *,
        production_item_id: int | None,
        customer_order_item_id: int | None,
        flow_node_id: str,
        source_flow_node_id: str | None,
        procedure_id: int | None,
        is_temporary: bool | None,
    ) -> dict:
        self.require_capability(CAP_PRODUCTION_WORKBENCH)
        return planning.list_production_workbench_work_orders(
            self.descriptor.code,
            position_type,
            page,
            page_size,
            production_item_id=production_item_id,
            customer_order_item_id=customer_order_item_id,
            flow_node_id=flow_node_id,
            source_flow_node_id=source_flow_node_id,
            procedure_id=procedure_id,
            is_temporary=is_temporary,
        )
