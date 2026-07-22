import { service } from '@/api/request'

export type Customer = {
  id: number
  customer_name: string
  created_at: string
  updated_at: string
}

export async function queryCustomers(keyword?: string) {
  const response = await service.get<{ data: Customer[] }>('/customers', {
    params: { keyword: keyword || undefined },
  })
  return response.data.data
}
