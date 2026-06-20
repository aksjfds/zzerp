import type {
  CreateProductPayload,
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
    zz_code: payload.zzCode.trim(),
    product_name: payload.productName.trim(),
    process: payload.process,
    quantity: payload.quantity,
  })

  return res.data.data
}

export async function queryProductRecords(zzCode: string, product: string) {
  const res = await service.get<{ data: ProductRecord[] }>('/records', {
    params: {
      zz_code: zzCode,
      product,
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
