import { service } from '@/api/request'

export type DepartmentProductionProgressItem = {
  production_item_id: number | null
  part_no: string
  part_name: string
  customer_order_no: string
  order_date: string
  order_quantity: number
  shipped_quantity: number
  outstanding_quantity: number
  completion_date: string | null
  remark: string
}

export async function queryDepartmentProductionProgress(
  departmentCode: string,
  page: number,
  pageSize: number,
  keyword?: string,
) {
  const response = await service.get<{
    data: DepartmentProductionProgressItem[]
    total: number
  }>(`/departments/${departmentCode}/production-progress`, {
    params: {
      page,
      page_size: pageSize,
      keyword: keyword || undefined,
    },
  })
  return response.data
}
