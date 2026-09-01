import { service } from '@/api/request'
import type {
  ProductionWorkbenchPositionQuery,
  ProductionWorkbenchPosition,
} from '../domain/productionWorkbench'

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
