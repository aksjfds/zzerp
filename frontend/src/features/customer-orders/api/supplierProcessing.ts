import { service } from '@/api/request'
import type {
  SupplierProcessingTask,
  SupplierProcessingWorkOrderInput,
} from '../domain/supplierProcessing'

export async function querySupplierProcessingTasks() {
  const response = await service.get<{ data: SupplierProcessingTask[]; total: number }>(
    '/supplier-processing/tasks',
  )
  return { items: response.data.data, total: response.data.total }
}

export async function createSupplierProcessingWorkOrder(
  payload: SupplierProcessingWorkOrderInput,
) {
  await service.post('/supplier-processing/work-orders', payload)
}

export async function cancelSupplierProcessingWorkOrder(workOrderId: number) {
  await service.post(`/supplier-processing/work-orders/${workOrderId}/cancel`)
}
