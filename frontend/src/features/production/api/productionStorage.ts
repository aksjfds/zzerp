import { service } from '@/api/request'
import type { DepartmentMaterialPosition } from '../domain/types'

export async function queryDepartmentMaterials(
  departmentCode: string,
) {
  const response = await service.get<{ data: DepartmentMaterialPosition[] }>(
    `/departments/${departmentCode}/materials`,
  )
  return response.data.data
}

export async function storeProductionPosition(
  departmentCode: string,
  item: DepartmentMaterialPosition,
  quantity: number,
) {
  const response = await service.post<{
    operation_group_no: string
    warehouse_stock_id: number
    quantity: number
    processing_status: string
  }>(`/departments/${departmentCode}/materials/storage`, {
    production_item_id: item.production_item_id,
    processing_state_id: item.processing_state_id,
    flow_node_id: item.flow_node_id,
    source_flow_node_id: item.source_flow_node_id,
    position_version: item.position_version,
    quantity,
  })
  return response.data
}
