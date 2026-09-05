import { service } from '@/api/request'
import type {
  ProcedurePriceListItem,
  ProcedurePriceScope,
  ProcedurePriceRevision,
} from '../domain/procedurePrices'

export async function queryProcedurePrices(
  departmentCode: string, page: number, pageSize: number, keyword: string,
) {
  const response = await service.get<{ data: ProcedurePriceListItem[]; total: number }>(
    `/departments/${departmentCode}/procedure-prices`,
    { params: { page, page_size: pageSize, keyword: keyword.trim() || undefined } },
  )
  return response.data
}

export async function queryProcedurePriceRevisions(
  departmentCode: string,
  page = 1,
  pageSize = 50,
) {
  const response = await service.get<{ data: ProcedurePriceRevision[]; total: number }>(
    `/departments/${departmentCode}/procedure-price-revisions`,
    { params: { page, page_size: pageSize } },
  )
  return response.data
}

export async function saveProcedurePrices(
  departmentCode: string,
  scope: ProcedurePriceScope,
  procedures: Array<{
    procedure_id: number | null
    procedure_name: string
    unit_price: number | null
  }>,
) {
  await service.put(
    `/departments/${departmentCode}/procedure-prices/${scope.product_id}/${scope.product_version}/${encodeURIComponent(scope.origin_flow_node_id)}/${encodeURIComponent(scope.flow_node_id)}`,
    { procedures },
  )
}

export async function confirmProcedurePrices(
  departmentCode: string,
  scope: ProcedurePriceScope,
  procedures: Array<{
    procedure_id: number | null
    procedure_name: string
    unit_price: number | null
  }>,
) {
  await service.post(
    `/departments/${departmentCode}/procedure-prices/${scope.product_id}/${scope.product_version}/${encodeURIComponent(scope.origin_flow_node_id)}/${encodeURIComponent(scope.flow_node_id)}/confirm`,
    { procedures },
  )
}

export async function cancelProcedurePriceConfirmation(
  departmentCode: string,
  scope: ProcedurePriceScope,
) {
  await service.delete(
    `/departments/${departmentCode}/procedure-prices/${scope.product_id}/${scope.product_version}/${encodeURIComponent(scope.origin_flow_node_id)}/${encodeURIComponent(scope.flow_node_id)}/confirm`,
  )
}

export async function saveTemporaryWorkOrderPrice(
  departmentCode: string,
  workOrderId: number,
  unitPrice: number | null,
) {
  await service.put(
    `/departments/${departmentCode}/procedure-prices/temporary-work-orders/${workOrderId}`,
    { unit_price: unitPrice },
  )
}
