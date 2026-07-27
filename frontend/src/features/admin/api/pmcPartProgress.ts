import { service } from '@/api/request'
import type { PmcPartProgressResult } from '../domain/pmcPartProgress'

export type PmcPartProgressQuery = {
  page: number
  page_size: number
  keyword?: string
  customer_order_id?: number
  focus_order_id?: number
  order_status?: string
  department_code?: string
  only_exception?: boolean
  only_unfinished?: boolean
}

export async function queryPmcPartProgress(params: PmcPartProgressQuery) {
  const response = await service.get<PmcPartProgressResult>(
    '/pmc/part-production-progress',
    { params },
  )
  return response.data
}
