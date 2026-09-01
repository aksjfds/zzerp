import type { WorkOrderBatch, WorkOrderStatus } from './types'

export type WorkOrderRecordView = {
  id: number
  work_order_no: string
  work_order_type: 'standard' | 'assembly' | 'supplier_processing'
  is_temporary: boolean
  workshop_name: string
  procedure_name: string
  worker_name: string | null
  quantity: number
  processed_quantity: number
  submitted_quantity: number
  pending_qc_quantity: number
  completed_quantity: number
  rework_quantity: number
  scrap_quantity: number
  lost_quantity: number
  status: WorkOrderStatus
  created_at: string
  closed_at: string | null
  work_order: {
    batches: WorkOrderBatch[]
  }
}
