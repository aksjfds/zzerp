import { service } from '@/api/request'

export type ProcedureTagPriceTag = {
  id: number
  tag_name: string
  unit_price: number | string | null
}

export type ProcedureTagPriceProcedure = {
  procedure_id: number
  procedure_name: string
  tags_locked: boolean
  available_tags: ProcedureTagPriceTag[]
  configured_tags: ProcedureTagPriceTag[]
}

export type ProcedureTagPricePart = {
  product_id: number
  product_version: number
  product_name: string
  factory_code: string
  product_bom_id: number | null
  origin_flow_node_id: string
  part_name: string
  part_no: string
  procedures: ProcedureTagPriceProcedure[]
}

export async function queryProcedureTagPrices(
  departmentCode: string,
  page: number,
  pageSize: number,
  keyword: string,
) {
  const response = await service.get<{
    data: ProcedureTagPricePart[]
    total: number
  }>(`/departments/${departmentCode}/procedure-tag-prices`, {
    params: {
      page,
      page_size: pageSize,
      keyword: keyword.trim() || undefined,
    },
  })
  return response.data
}

export async function saveProcedureTagPrices(
  departmentCode: string,
  productId: number,
  productVersion: number,
  originFlowNodeId: string,
  procedureId: number,
  tags: Array<{ tag_name: string; unit_price: number | null }>,
) {
  await service.put(
    `/departments/${departmentCode}/procedure-tag-prices/${productId}/${productVersion}/${encodeURIComponent(originFlowNodeId)}/${procedureId}`,
    { tags },
  )
}
