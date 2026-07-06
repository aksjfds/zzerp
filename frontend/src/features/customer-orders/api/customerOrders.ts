import { service } from '@/api/request'
import type { CustomerOrder, CustomerOrderPayload } from '../domain/types'

export async function queryCustomerOrders() {
  const response = await service.get<{ data: CustomerOrder[] }>('/customer-orders')
  return response.data.data
}

export async function queryCustomerOrder(orderId: number) {
  const response = await service.get<{ data: CustomerOrder }>(`/customer-orders/${orderId}`)
  return response.data.data
}

export async function createCustomerOrder(payload: CustomerOrderPayload) {
  const response = await service.post<{ data: CustomerOrder }>('/customer-orders', payload)
  return response.data.data
}

export async function updateCustomerOrder(orderId: number, payload: CustomerOrderPayload) {
  const response = await service.put<{ data: CustomerOrder }>(`/customer-orders/${orderId}`, payload)
  return response.data.data
}

export async function confirmCustomerOrder(orderId: number) {
  const response = await service.post<{ data: CustomerOrder }>(`/customer-orders/${orderId}/confirm`)
  return response.data.data
}

export async function cancelCustomerOrder(orderId: number) {
  const response = await service.post<{ data: CustomerOrder }>(`/customer-orders/${orderId}/cancel`)
  return response.data.data
}

export async function deleteCustomerOrder(orderId: number) {
  await service.delete(`/customer-orders/${orderId}`)
}
