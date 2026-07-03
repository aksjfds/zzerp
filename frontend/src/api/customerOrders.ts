import { service } from './request'
import type {
  CustomerOrder,
  CustomerOrderCreateInput,
  CustomerOrderStatus,
  CustomerOrderUpdateInput,
} from '@/types/sales'

export async function queryV2CustomerOrders(params?: {
  keyword?: string
  status?: CustomerOrderStatus
}) {
  const response = await service.get<CustomerOrder[]>('/v2/customer-orders', { params })
  return response.data
}

export async function createV2CustomerOrder(payload: CustomerOrderCreateInput) {
  const response = await service.post<CustomerOrder>('/v2/customer-orders', payload)
  return response.data
}

export async function updateV2CustomerOrder(
  orderId: number,
  payload: CustomerOrderUpdateInput,
) {
  const response = await service.put<CustomerOrder>(
    `/v2/customer-orders/${orderId}`,
    payload,
  )
  return response.data
}

export async function confirmV2CustomerOrder(orderId: number) {
  const response = await service.post<CustomerOrder>(
    `/v2/customer-orders/${orderId}/confirm`,
  )
  return response.data
}

export async function createV2CustomerOrderChange(orderId: number) {
  const response = await service.post<CustomerOrder>(
    `/v2/customer-orders/${orderId}/changes`,
  )
  return response.data
}

export async function cancelV2CustomerOrder(orderId: number) {
  const response = await service.post<CustomerOrder>(
    `/v2/customer-orders/${orderId}/cancel`,
  )
  return response.data
}
