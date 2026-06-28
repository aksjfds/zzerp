import type {
  CreateProductPayload,
  CreateProcedurePayload,
  CreateTaskPayload,
  Department,
  ProcedureItem,
  ProductItem,
  ProductRecord,
  TaskItem,
  WorkerItem,
} from '@/types/production'
import { service } from './request'

export async function queryProducts() {
  const res = await service.get<{ data: ProductItem[] }>('/products')
  return res.data.data
}

export async function createProduct(payload: CreateProductPayload) {
  const res = await service.post<{ data: ProductItem }>('/products', {
    order_id: payload.orderId.trim(),
    zz_code: payload.zzCode.trim(),
    product_name: payload.productName.trim(),
    delivery_date: payload.deliveryDate,
    process: payload.process,
    quantity: payload.quantity,
  })

  return res.data.data
}

export async function queryProductRecords(
  orderId: string,
  zzCode: string,
  product: string,
  department?: Department,
) {
  const res = await service.get<{ data: ProductRecord[] }>('/records', {
    params: {
      order_id: orderId,
      zz_code: zzCode,
      product,
      department,
    },
  })

  return res.data.data
}

export async function queryDepartmentTasks(department: Department) {
  const res = await service.get<{ data: TaskItem[] }>(`/tasks/${department}`)
  return res.data.data
}

export async function createTask(payload: CreateTaskPayload) {
  const res = await service.post<{ data: TaskItem }>('/tasks', {
    order_id: payload.orderId.trim(),
    zz_code: payload.zzCode.trim(),
    product: payload.product.trim(),
    worker: payload.worker.trim(),
    department: payload.department,
    procedure: payload.procedure.trim(),
    quantity: payload.quantity,
    note: payload.note?.trim() || undefined,
  })

  return res.data.data
}

export async function completeTask(taskId: number) {
  const res = await service.patch<{ data: TaskItem }>(`/tasks/${taskId}/complete`)
  return res.data.data
}

export async function queryDepartmentWorkers(department: Department) {
  const res = await service.get<{ data: WorkerItem[] }>(`/tasks/${department}/workers`)
  return res.data.data
}

export async function queryDepartmentProcedures(department: Department) {
  const res = await service.get<{ data: ProcedureItem[] }>(`/tasks/${department}/procedures`)
  return res.data.data
}

export async function createDepartmentProcedure(payload: CreateProcedurePayload) {
  const res = await service.post<{ data: ProcedureItem }>(`/tasks/${payload.department}/procedures`, {
    department: payload.department,
    procedure_name: payload.procedureName.trim(),
  })

  return res.data.data
}
