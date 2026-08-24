import { service } from '@/api/request'
import type {
  RepositoryItem,
  DepartmentSurplusInventoryItem,
  WorkerItem,
} from '../domain/types'
import type { DepartmentRepositoryQuery, RepositoryWorkshop } from '../domain/repositories'

export async function queryDepartmentRepositoryWorkshops(
  departmentCode: string,
) {
  const response = await service.get<RepositoryWorkshop[]>(
    `/departments/${departmentCode}/repository-workshops`,
  )
  return response.data
}

export async function queryDepartmentRepositories(
  departmentCode: string,
  params: DepartmentRepositoryQuery,
  signal?: AbortSignal,
) {
  const response = await service.get<{ data: RepositoryItem[]; total: number }>(
    `/departments/${departmentCode}/repositories`,
    { params, signal },
  )
  return { items: response.data.data, total: response.data.total }
}

export async function queryDepartmentWorkers(departmentCode: string) {
  const response = await service.get<{ data: WorkerItem[] }>(
    `/departments/${departmentCode}/workers`,
  )
  return response.data.data
}

export async function queryDepartmentSurplusInventory(departmentCode: string) {
  const response = await service.get<{ data: DepartmentSurplusInventoryItem[] }>(
    `/departments/${departmentCode}/surplus-inventory`,
  )
  return response.data.data
}

export async function storePositionInWarehouse(
  departmentCode: string,
  item: DepartmentSurplusInventoryItem,
  quantity: number,
) {
  const response = await service.post<{
    inventory_stock_id: number
    quantity: number
    completed_flow_node_id: string
    completed_node_label: string
  }>(`/departments/${departmentCode}/warehouse-storage`, {
    production_item_id: item.production_item_id,
    flow_node_id: item.flow_node_id,
    source_flow_node_id: item.source_flow_node_id,
    quantity,
  })
  return response.data
}
