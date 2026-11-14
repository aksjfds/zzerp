import { service } from '@/api/request'
import type { Customer } from '../domain/types'

export async function queryCustomers(keyword?: string, signal?: AbortSignal) {
  const response = await service.get<{ data: Customer[] }>('/customers', {
    params: { keyword: keyword || undefined },
    signal,
  })
  return response.data.data
}
