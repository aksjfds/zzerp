import { service } from '@/api/request'
import type {
  RepositoryItem,
  ProductionPositionStorageCandidate,
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

export async function queryProductionPositionStorageCandidates(departmentCode: string) {
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
