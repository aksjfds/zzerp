import { service } from '@/api/request'
import type { CustomerOrder, CustomerOrderPayload, CustomerOrderProduction } from '../domain/types'

export async function queryCustomerOrders(page = 1, pageSize = 50, includeProgress = false) {
  const response = await service.get<{ data: CustomerOrder[]; total: number }>('/customer-orders', {
    params: { page, page_size: pageSize, include_progress: includeProgress || undefined },
  })
  return { items: response.data.data, total: response.data.total }
}

export async function queryCustomerOrder(orderId: number) {
  const response = await service.get<{ data: CustomerOrder }>(`/customer-orders/${orderId}`)
  return response.data.data
}

export async function queryCustomerOrderProduction(orderId: number) {
  const response = await service.get<{ data: CustomerOrderProduction }>(
    `/customer-orders/${orderId}/production-status`,
  )
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

export async function confirmCustomerOrder(orderId: number, expectedRevision: number) {
  const response = await service.post<{ data: CustomerOrder }>(`/customer-orders/${orderId}/confirm`, null, {
    params: { expected_revision: expectedRevision },
  })
  return response.data.data
}

export async function cancelCustomerOrder(orderId: number, expectedRevision: number) {
  const response = await service.post<{ data: CustomerOrder }>(`/customer-orders/${orderId}/cancel`, null, {
    params: { expected_revision: expectedRevision },
  })
  return response.data.data
}

export async function deleteCustomerOrder(orderId: number, expectedRevision: number) {
  await service.delete(`/customer-orders/${orderId}`, { params: { expected_revision: expectedRevision } })
}
