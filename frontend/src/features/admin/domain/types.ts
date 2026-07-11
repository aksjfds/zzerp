export type AdminWorker = {
  id: number
  worker_name: string
  department_id: number
  department_name: string
  department_code: string
  workshop_id: number | null
  workshop_name: string | null
}

export type AdminWorkerDepartment = {
  department_id: number
  department_name: string
  department_code: string
  workers: AdminWorker[]
}

export type AdminWorkerHistoryItem = {
  work_order_id: number
  work_order_no: string | null
  item_name: string
  procedure_name: string
  planned_quantity: number
  completed_quantity: number
  processing_quantity: number
  completion_rate: number
  lost_quantity: number
  scrap_quantity: number
  status: string
  completed_at: string | null
}
