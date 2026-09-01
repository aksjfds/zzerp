import { service } from '@/api/request'
import type {
  DepartmentProductionProgressItem,
  ProductionProgressItemDetail,
} from '../domain/productionProgress'

export async function queryDepartmentProductionProgress(
  departmentCode: string,
  page: number,
  pageSize: number,
  keyword?: string,
) {
  const response = await service.get<{
    data: DepartmentProductionProgressItem[]
    total: number
  }>(`/departments/${departmentCode}/production-progress`, {
    params: {
      page,
      page_size: pageSize,
      keyword: keyword || undefined,
    },
  })
  return response.data
}

export async function queryProductionProgressItemDetail(
  departmentCode: string,
  productionPlanItemId: number,
  processingWorkshopId?: number,
  flowNodeId?: string | null,
) {
  const response = await service.get<ProductionProgressItemDetail>(
    `/departments/${departmentCode}/production-progress/items/${productionPlanItemId}`,
    {
      params: {
        processing_workshop_id: processingWorkshopId || undefined,
        flow_node_id: flowNodeId || undefined,
      },
    },
  )
  return response.data
}
