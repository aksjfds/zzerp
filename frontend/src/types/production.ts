export const DEPARTMENTS = ['in', 'laser', 'stamp', 'cnc', 'polish', 'qc', 'out'] as const
export type Department = (typeof DEPARTMENTS)[number]

export const DEPARTMENT_LABELS: Record<Department, string> = {
  in: '入库',
  laser: '激光',
  stamp: '冲压',
  cnc: 'CNC',
  polish: '打磨',
  qc: 'QC',
  out: '完工',
}

export type RepositoryStock = {
  id: number
  orderId: string
  department: Department
  zzCode: string
  productName: string
  quantity: number
}

export type ProductItem = {
  id: number
  orderId: string
  zzCode: string
  productName: string
  deliveryDate: string
  process: Department[]
  quantity: number
  repositories: RepositoryStock[]
  createdAt: string
}

export type CreateProductPayload = {
  orderId: string
  zzCode: string
  productName: string
  deliveryDate: string
  process: Department[]
  quantity: number
}

export type ProductRecord = {
  id: number
  orderId: string
  zzCode: string
  product: string
  fromRepository: Department
  toRepository: Department
  quantity: number
  note?: string | null
  createdAt: string
}

export type TaskItem = {
  id: number
  orderId: string
  zzCode: string
  product: string
  worker: string
  department: Department
  procedure: string
  quantity: number
  ok: number
  status: boolean
  note?: string | null
  createdAt: string
}

export type WorkerItem = {
  id: number
  name: string
  department: Department
}

export type ProcedureItem = {
  id: number
  procedureName: string
  department: Department
}

export type CreateTaskPayload = {
  orderId: string
  zzCode: string
  product: string
  worker: string
  department: Department
  procedure: string
  quantity: number
  note?: string
}

export type CreateProcedurePayload = {
  department: Department
  procedureName: string
}
