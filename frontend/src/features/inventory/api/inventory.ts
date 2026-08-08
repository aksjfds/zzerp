import { service } from '@/api/request'
import type {
  InventoryDepartment,
  InventoryOutboundPlan,
  InventoryStock,
  InventoryTransaction,
  FinishedOrderStock,
} from '../domain/types'

export async function queryStocks(departmentCode: InventoryDepartment) {
  const response = await service.get<{ data: InventoryStock[] }>('/inventory/stocks', {
    params: { department_code: departmentCode },
  })
  return response.data.data
}

export async function queryOutboundPlans(departmentCode: InventoryDepartment) {
  const response = await service.get<{ data: InventoryOutboundPlan[] }>('/inventory/outbound-plans', {
    params: { department_code: departmentCode },
  })
  return response.data.data.map(plan => ({
    ...plan,
    items: plan.items.map(item => ({ ...item, issue_quantity: 0 })),
  }))
}

export async function issueOutboundPlan(plan: InventoryOutboundPlan) {
  const response = await service.post<InventoryOutboundPlan>(
    `/inventory/outbound-plans/${plan.production_plan_id}/issue`,
    {
      department_code: plan.department_code,
      items: plan.items.map(item => ({
        reservation_id: item.reservation_id,
        quantity: item.issue_quantity || 0,
      })),
    },
  )
  return response.data
}

export async function queryTransactions(departmentCode: InventoryDepartment) {
  const response = await service.get<{ data: InventoryTransaction[] }>('/inventory/transactions', {
    params: { department_code: departmentCode },
  })
  return response.data.data
}

export async function queryFinishedOrderStocks(operation: 'all' | 'receipt' | 'shipment') {
  const response = await service.get<{ data: FinishedOrderStock[] }>('/inventory/finished-order-stocks', {
    params: { operation },
  })
  return response.data.data
}

export async function receiveFinishedOrderStock(customerOrderItemId: number) {
  const response = await service.post<{ data: FinishedOrderStock }>(
    `/inventory/finished-order-stocks/${customerOrderItemId}/receive`,
  )
  return response.data.data
}

export async function shipFinishedOrderStock(customerOrderItemId: number, quantity: number) {
  const response = await service.post<{ data: FinishedOrderStock }>(
    `/inventory/finished-order-stocks/${customerOrderItemId}/ship`,
    { quantity },
  )
  return response.data.data
}
