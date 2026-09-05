import { service } from '@/api/request'
import type {
  CustomerOrder,
  CustomerOrderProgressDetail,
  CustomerOrderPayload,
  CustomerOrderProduction,
  ProductionPlan,
} from '../domain/types'

export async function queryCustomerOrders(page = 1, pageSize = 50) {
  const response = await service.get<{ data: CustomerOrder[]; total: number }>('/customer-orders', {
    params: { page, page_size: pageSize },
  })
  return { items: response.data.data, total: response.data.total }
}

export async function queryCustomerOrderProgressDetails(
  page = 1,
  pageSize = 50,
  customerId?: number,
) {
  const response = await service.get<{
    data: CustomerOrderProgressDetail[]
    total: number
  }>('/customer-orders/progress-details', {
    params: { page, page_size: pageSize, customer_id: customerId },
  })
  return { items: response.data.data, total: response.data.total }
}

export async function queryProductionPlanOrders(page = 1, pageSize = 50) {
  const response = await service.get<{ data: CustomerOrder[]; total: number }>(
    '/customer-orders/production-plans',
    { params: { page, page_size: pageSize } },
  )
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

export async function queryProductionPlan(orderId: number) {
  const response = await service.get<{ data: ProductionPlan }>(
    `/customer-orders/${orderId}/production-plan`,
  )
  return response.data.data
}

export async function updateProductionPlan(plan: ProductionPlan) {
  const response = await service.put<{ data: ProductionPlan }>(
    `/customer-orders/${plan.customer_order_id}/production-plan`,
    {
      expected_revision: plan.revision,
      items: plan.items.filter(item => item.item_type === 'part').map(item => ({
        id: item.id,
        planned_production_quantity: item.planned_production_quantity,
      })),
    },
  )
  return response.data.data
}

export async function confirmCustomerOrder(
  orderId: number,
  expectedRevision: number,
) {
  const response = await service.post<{ data: CustomerOrder }>(`/customer-orders/${orderId}/confirm`, null, {
    params: { expected_revision: expectedRevision },
  })
  return response.data.data
}

export async function confirmProductionPlan(
  orderId: number,
  expectedRevision: number,
  planExpectedRevision: number,
) {
  const response = await service.post<{ data: CustomerOrder }>(
    `/customer-orders/${orderId}/production-plan/confirm`,
    null,
    {
      params: {
        expected_revision: expectedRevision,
        plan_expected_revision: planExpectedRevision,
      },
    },
  )
  return response.data.data
}

export async function completeProductionPlan(
  orderId: number,
  expectedRevision: number,
) {
  const response = await service.post<{ data: ProductionPlan }>(
    `/customer-orders/${orderId}/production-plan/complete`,
    null,
    { params: { expected_revision: expectedRevision } },
  )
  return response.data.data
}

export async function unconfirmProductionPlan(
  orderId: number,
  expectedRevision: number,
  planExpectedRevision: number,
) {
  const response = await service.post<{ data: CustomerOrder }>(
    `/customer-orders/${orderId}/production-plan/unconfirm`,
    null,
    { params: { expected_revision: expectedRevision, plan_expected_revision: planExpectedRevision } },
  )
  return response.data.data
}

export async function reopenProductionPlan(
  orderId: number,
  expectedRevision: number,
  planExpectedRevision: number,
) {
  const response = await service.post<{ data: CustomerOrder }>(
    `/customer-orders/${orderId}/production-plan/reopen`,
    null,
    { params: { expected_revision: expectedRevision, plan_expected_revision: planExpectedRevision } },
  )
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
