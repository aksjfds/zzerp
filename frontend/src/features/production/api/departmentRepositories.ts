import { service } from '@/api/request'
import type {
  RepositoryFilters,
  RepositoryItem,
  SubstepCard,
  WorkerItem,
} from '../domain/types'

export type DepartmentRepositoryQuery = RepositoryFilters & {
  page: number
  page_size: number
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

export async function queryProductionSubstepCards(
  departmentCode: string,
  productionItemId: number,
  flowNodeId: string,
  sourceFlowNodeId: string,
) {
  const response = await service.get<{ data: SubstepCard[] }>(
    `/departments/${departmentCode}/production-items/${productionItemId}/substep-cards`,
    {
      params: {
        flow_node_id: flowNodeId,
        source_flow_node_id: sourceFlowNodeId,
      },
    },
  )
  return response.data.data
}

export async function dispatchProcedureStageStock(
  procedureStageStockId: number,
  quantity: number,
) {
  await service.post(
    `/procedure-stage-stocks/${procedureStageStockId}/dispatches`,
    { quantity },
  )
}
