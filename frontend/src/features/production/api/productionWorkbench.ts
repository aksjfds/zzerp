import { service } from '@/api/request'
import type {
  ProductionWorkbenchPositionQuery,
  ProductionWorkbenchPosition,
  ProductionWorkbenchWorkOrderQuery,
  ProductionWorkbenchWorkOrders,
  ProductionWorkbenchWorkshop,
} from '../domain/productionWorkbench'

export async function queryProductionWorkbenchWorkshops(
  departmentCode: string,
) {
  const response = await service.get<ProductionWorkbenchWorkshop[]>(
    `/departments/${departmentCode}/production-workbench/workshops`,
  )
  return response.data
}

export async function queryProductionWorkbenchPositions<
  Position extends ProductionWorkbenchPosition,
>(
  departmentCode: string,
  params: ProductionWorkbenchPositionQuery,
  signal?: AbortSignal,
) {
  const response = await service.get<{
    data: Position[]
    total: number
  }>(`/departments/${departmentCode}/production-workbench/positions`, {
    params,
    signal,
  })
  return { items: response.data.data, total: response.data.total }
}

export async function queryProductionWorkbenchWorkOrders(
  departmentCode: string,
  params: ProductionWorkbenchWorkOrderQuery,
  signal?: AbortSignal,
): Promise<ProductionWorkbenchWorkOrders> {
  const response = await service.get<{
    data: ProductionWorkbenchWorkOrders['items']
    total: number
    procedure_summaries: ProductionWorkbenchWorkOrders['procedureSummaries']
  }>(`/departments/${departmentCode}/production-workbench/work-orders`, {
    params,
    signal,
  })
  return {
    items: response.data.data,
    total: response.data.total,
    procedureSummaries: response.data.procedure_summaries,
  }
}
