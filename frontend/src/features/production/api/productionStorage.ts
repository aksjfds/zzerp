import { service } from '@/api/request'
import type { ProductionPositionStorageCandidate } from '../domain/types'

export async function queryProductionPositionStorageCandidates(
  departmentCode: string,
) {
  const response = await service.get<{ data: ProductionPositionStorageCandidate[] }>(
    `/departments/${departmentCode}/warehouse-candidates`,
  )
  return response.data.data
}

export async function storeProductionPosition(
  departmentCode: string,
  item: ProductionPositionStorageCandidate,
  quantity: number,
) {
  const response = await service.post<{
    operation_group_no: string
    warehouse_stock_id: number
    quantity: number
    completion_status: string
  }>(`/departments/${departmentCode}/warehouse-candidates/storage`, {
    production_item_id: item.production_item_id,
    flow_node_id: item.flow_node_id,
    source_flow_node_id: item.source_flow_node_id,
    position_version: item.position_version,
    quantity,
  })
  return response.data
}
