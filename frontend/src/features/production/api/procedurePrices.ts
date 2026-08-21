import { service } from '@/api/request'

export type ProcedurePriceItem = {
  procedure_id: number
  procedure_name: string
  unit_price: number | string | null
  referenced: boolean
}

export type ProcedurePriceScope = {
  product_id: number
  product_version: number
  product_name: string
  factory_code: string
  product_bom_id: number | null
  origin_flow_node_id: string
  flow_node_id: string
  workshop_id: number
  workshop_name: string
  part_name: string
  part_no: string
  procedures: ProcedurePriceItem[]
}

export async function queryProcedurePrices(
  departmentCode: string, page: number, pageSize: number, keyword: string,
) {
  const response = await service.get<{ data: ProcedurePriceScope[]; total: number }>(
    `/departments/${departmentCode}/procedure-prices`,
    { params: { page, page_size: pageSize, keyword: keyword.trim() || undefined } },
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
