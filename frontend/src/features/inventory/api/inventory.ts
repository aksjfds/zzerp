import { service } from '@/api/request'
import type {
  FinishedStock,
  FinishedStockTransaction,
  FinishedReceipt,
  FinishedInboundItem,
  FinishedShipmentCandidate,
  WarehouseOperation,
  WarehouseOperationStatus,
  WarehouseStock,
} from '../domain/types'

export async function queryFinishedInboundItems(page: number, pageSize: number) {
  const response = await service.get<{
    data: FinishedInboundItem[]
    total: number
    page: number
    page_size: number
  }>('/inventory/finished-inbound-items', {
    params: { page, page_size: pageSize },
  })
  return response.data
}

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

export async function reverseProductionStorage(operationGroupNo: string) {
  await service.post('/inventory/warehouse-operations/reverse-production-storage', {
    operation_group_no: operationGroupNo,
  })
}

export async function queryFinishedStocks() {
  const response = await service.get<{ data: FinishedStock[] }>(
    '/inventory/finished-stocks',
  )
  return response.data.data
}

export async function queryFinishedStockTransactions() {
  const response = await service.get<{ data: FinishedStockTransaction[] }>(
    '/inventory/finished-transactions',
  )
  return response.data.data
}

export async function receiveFinishedReceipt(receiptId: number) {
  const response = await service.post<{ data: FinishedReceipt }>(
    `/inventory/finished-receipts/${receiptId}/receive`,
  )
  return response.data.data
}

export async function reverseFinishedReceipt(receiptId: number) {
  await service.post(`/inventory/finished-receipts/${receiptId}/reverse`, {})
}

export async function reverseFinishedShipment(transactionId: number) {
  await service.post(`/inventory/finished-shipment-transactions/${transactionId}/reverse`, {})
}

export async function queryFinishedShipmentCandidates() {
  const response = await service.get<{ data: FinishedShipmentCandidate[] }>(
    '/inventory/finished-shipments',
  )
  return response.data.data
}

export async function confirmFinishedShipment(customerOrderItemId: number, quantity: number) {
  const response = await service.post<{ data: FinishedShipmentCandidate }>(
    `/inventory/finished-shipments/${customerOrderItemId}`,
    { quantity },
  )
  return response.data.data
}
