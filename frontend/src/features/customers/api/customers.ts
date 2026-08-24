import { service } from '@/api/request'
import type { Customer } from '../domain/types'

export async function queryCustomers(keyword?: string) {
  const response = await service.get<{ data: Customer[] }>('/customers', {
    params: { keyword: keyword || undefined },
  })
  return response.data.data
}
