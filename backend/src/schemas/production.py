"""Stable production schema import surface.

Contracts are owned by focused modules; this facade preserves existing imports.
"""

from schemas.production_inventory import (
    DepartmentSurplusInventoryEnvelope,
    DepartmentSurplusInventoryItem,
    RepositoryListEnvelope,
    RepositoryResponse,
    WarehouseStorageInput,
    WarehouseStorageResponse,
)
from schemas.production_progress import (
    AssemblyMaterialArrivalResponse,
    DepartmentProductionProgressEnvelope,
    DepartmentProductionProgressResponse,
    ProductionProgressItemDetailResponse,
    ProductionProgressProcedureCardResponse,
    ProductionProgressWorkOrderResponse,
)
from schemas.production_quality import (
    PendingQcListEnvelope,
    PendingQcResponse,
    QcInspection,
    WorkOrderBatchEnvelope,
    WorkOrderBatchResponse,
)
from schemas.production_work_orders import (
    AssemblyMaterialInput,
    AssemblyWorkOrderCreate,
    ProductionUndoOperationResponse,
    PurchaseArrival,
    ReworkSubmission,
    WorkOrderCreate,
    WorkOrderEnvelope,
    WorkOrderListEnvelope,
    WorkOrderResponse,
    WorkOrderSubmission,
)
from schemas.production_workforce import (
    DepartmentWorkerCreate,
    DepartmentWorkerEnvelope,
    DepartmentWorkerHistoryEnvelope,
    DepartmentWorkerHistoryItem,
    DepartmentWorkerOverviewEnvelope,
    DepartmentWorkerOverviewResponse,
    DepartmentWorkerPayEnvelope,
    DepartmentWorkerPayItem,
    DepartmentWorkerPaySummary,
    DepartmentWorkerResponse,
    DepartmentWorkerWorkshopResponse,
    WorkerListEnvelope,
    WorkerResponse,
)
