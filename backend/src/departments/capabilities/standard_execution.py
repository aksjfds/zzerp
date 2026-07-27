from departments.contracts import CAP_STANDARD_EXECUTION
from modules.production_core import api as production


class StandardExecutionCapability:
    def list_tag_cards(
        self,
        production_item_id: int,
        flow_node_id: str,
        source_flow_node_id: str,
    ) -> list[dict]:
        self.require_capability(CAP_STANDARD_EXECUTION)
        return production.list_tag_cards(
            self.descriptor.code,
            production_item_id,
            flow_node_id,
            source_flow_node_id,
        )

    def create_source_work_order(
        self,
        repository_id: int | None,
        procedure_tag_stock_id: int | None,
        tag_names: list[str],
        quantity: int,
        worker_id: int | None,
        remark: str | None,
    ) -> dict:
        self.require_capability(CAP_STANDARD_EXECUTION)
        return production.create_work_order(
            repository_id,
            procedure_tag_stock_id,
            tag_names,
            quantity,
            worker_id,
            remark,
            self.descriptor.code,
        )
