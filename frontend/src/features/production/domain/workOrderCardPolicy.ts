import type { WorkOrder, WorkOrderBatch } from './types'

export type WorkOrderMode = 'production' | 'assembly'
export type WorkOrderStatusType = 'primary' | 'success' | 'info' | 'warning'

export interface WorkOrderMetric {
  label: string
  value: string | number
}

export interface WorkOrderCardPolicy {
  metrics: (item: WorkOrder) => WorkOrderMetric[]
  statusText: (item: WorkOrder) => string
  statusType: (item: WorkOrder) => WorkOrderStatusType
  showInitialQc: (item: WorkOrder) => boolean
  showDirectResult: (item: WorkOrder) => boolean
  showReworkQc: (item: WorkOrder, batch: WorkOrderBatch) => boolean
  showUndo: (item: WorkOrder) => boolean
  showCancel: (item: WorkOrder) => boolean
}

export type WorkOrderSubmissionEligibility = Pick<
  WorkOrder,
  | 'status'
  | 'qc_available'
  | 'direct_result_allowed'
  | 'submitted_quantity'
>

export function canSubmitInitialQc(item: WorkOrderSubmissionEligibility) {
  return (
    item.status === 'open'
    && item.qc_available
    && item.submitted_quantity === 0
  )
}

export function canSubmitDirectResult(item: WorkOrderSubmissionEligibility) {
  return (
    item.status === 'open'
    && item.direct_result_allowed
    && item.submitted_quantity === 0
  )
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

export function commonWorkOrderStatusText(item: WorkOrder) {
  if (item.status === 'cancelled') return '已取消'
  if (item.status === 'closed') return '已结单'
  if (item.pending_qc_quantity) return '质检中'
  return '进行中'
}

export const commonWorkOrderActions: Pick<
  WorkOrderCardPolicy,
  | 'showInitialQc'
  | 'showDirectResult'
  | 'showReworkQc'
  | 'showUndo'
  | 'showCancel'
> = {
  showInitialQc: canSubmitInitialQc,
  showDirectResult: canSubmitDirectResult,
  showReworkQc: (item, batch) => (
    item.status === 'open'
    && Boolean(batch.recorded_at)
    && batch.rework_pending_quantity > 0
  ),
  showUndo: item => Boolean(item.undo_operation),
  showCancel: item => (
    item.status === 'open'
    && item.processed_quantity === 0
    && item.submitted_quantity === 0
  ),
}
