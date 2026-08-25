import type { WorkOrder, WorkOrderBatch } from './types'

export type WorkOrderMode = 'production' | 'assembly'
export type WorkOrderStatusType = 'primary' | 'success' | 'info' | 'warning'

export interface WorkOrderMetric {
  label: string
  value: string | number
}

export interface WorkOrderCardPolicy {
  batchTitle: string
  showBatches: boolean
  trackRework: boolean
  metrics: (item: WorkOrder) => WorkOrderMetric[]
  statusText: (item: WorkOrder) => string
  statusType: (item: WorkOrder) => WorkOrderStatusType
  showInitialQc: (item: WorkOrder) => boolean
  showDirectResult: (item: WorkOrder) => boolean
  showReworkQc: (item: WorkOrder, batch: WorkOrderBatch) => boolean
}

export function initialProcessingQuantity(item: WorkOrder) {
  return Math.max(item.quantity - item.processed_quantity, 0)
}

export function commonStatusType(item: WorkOrder): WorkOrderStatusType {
  if (item.status === 'cancelled') return 'info'
  if (item.pending_qc_quantity) return 'warning'
  if (
    item.ready_for_qc_quantity
    && initialProcessingQuantity(item) === 0
  ) return 'warning'
  return item.status === 'closed' ? 'success' : 'primary'
}
