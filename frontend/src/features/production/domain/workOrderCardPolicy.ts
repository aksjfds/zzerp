import type { WorkOrder, WorkOrderBatch } from './types'

export type WorkOrderMode = 'production' | 'purchase' | 'assembly'
export type WorkOrderStatusType = 'primary' | 'success' | 'info' | 'warning'

export interface WorkOrderMetric {
  label: string
  value: string | number
}

export interface WorkOrderCardPolicy {
  metricsClass?: string
  batchTitle: string
  completeLabel: (item: WorkOrder) => string
  showBatches: boolean
  trackRework: boolean
  metrics: (item: WorkOrder) => WorkOrderMetric[]
  statusText: (item: WorkOrder) => string
  statusType: (item: WorkOrder) => WorkOrderStatusType
  showComplete: (item: WorkOrder) => boolean
  disableComplete: (item: WorkOrder) => boolean
  showInitialQc: (item: WorkOrder) => boolean
  showDirectResult: (item: WorkOrder) => boolean
  showReworkQc: (item: WorkOrder, batch: WorkOrderBatch) => boolean
}

export function initialProcessingQuantity(item: WorkOrder) {
  return Math.max(item.quantity - item.processed_quantity, 0)
}

export function reworkPendingQuantity(item: WorkOrder) {
  return item.batches.reduce(
    (total, batch) => total + batch.rework_pending_quantity,
    0,
  )
}

export function commonStatusType(item: WorkOrder): WorkOrderStatusType {
  if (item.status === 'cancelled') return 'info'
  if (item.pending_qc_quantity || item.ready_for_qc_quantity) return 'warning'
  return item.status === 'closed' ? 'success' : 'primary'
}
