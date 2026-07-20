import { service } from '@/api/request'

export type ProcedureTagPriceTag = {
  id: number
  tag_name: string
  unit_price: number | string | null
}

export type ProcedureTagPriceProcedure = {
  procedure_id: number
  procedure_name: string
  available_tags: ProcedureTagPriceTag[]
  configured_tags: ProcedureTagPriceTag[]
}

export type ProcedureTagPricePart = {
  product_id: number
  product_version: number
  product_name: string
  factory_code: string
  product_bom_id: number
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
  productBomId: number,
  procedureId: number,
  tags: Array<{ tag_name: string; unit_price: number | null }>,
) {
  await service.put(
    `/departments/${departmentCode}/procedure-tag-prices/${productBomId}/${procedureId}`,
    { tags },
  )
}
