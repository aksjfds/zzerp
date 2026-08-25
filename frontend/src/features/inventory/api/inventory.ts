import { service } from '@/api/request'
import type {
  FinishedInventoryStock,
  FinishedInventoryTransaction,
  FinishedOrderStock,
  WarehouseOperation,
  WarehouseOperationStatus,
  WarehouseStock,
} from '../domain/types'

export async function queryWarehouseStocks() {
  const response = await service.get<{ data: WarehouseStock[] }>(
    '/inventory/warehouse-stocks',
  )
  return response.data.data
}

export async function queryWarehouseOperations(status?: WarehouseOperationStatus) {
  const response = await service.get<{ data: WarehouseOperation[] }>(
    '/inventory/warehouse-operations',
    { params: { status } },
  )
  return response.data.data
}

export async function reviewWarehouseOperation(
  operationGroupNo: string,
  reviewNote: string,
) {
  const response = await service.post<{ data: WarehouseOperation[] }>(
    '/inventory/warehouse-operations/review',
    { operation_group_no: operationGroupNo, review_note: reviewNote },
  )
  return response.data.data
}

export async function queryFinishedInventoryStocks() {
  const response = await service.get<{ data: FinishedInventoryStock[] }>(
    '/inventory/finished-stocks',
  )
  return response.data.data
}

export async function queryFinishedInventoryTransactions() {
  const response = await service.get<{ data: FinishedInventoryTransaction[] }>(
    '/inventory/finished-transactions',
  )
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
