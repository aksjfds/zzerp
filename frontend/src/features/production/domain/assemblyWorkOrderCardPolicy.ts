import type { WorkOrderCardPolicy } from './workOrderCardPolicy'
import { commonStatusType } from './workOrderCardPolicy'

export const assemblyWorkOrderCardPolicy: WorkOrderCardPolicy = {
  batchTitle: '质检记录',
  showBatches: true,
  trackRework: true,
  metrics: item => [
    { label: '对应产品', value: item.quantity },
    { label: '装配体数量', value: item.output_quantity },
    { label: '合格', value: item.qualified_output_quantity },
    ...(item.pending_qc_quantity ? [{ label: '质检中', value: item.pending_qc_quantity }] : []),
    ...(item.scrap_quantity ? [{ label: '报废', value: item.scrap_quantity }] : []),
    ...(item.lost_quantity ? [{ label: '遗失', value: item.lost_quantity }] : []),
  ],
  statusText(item) {
    if (item.status === 'cancelled') return '已取消'
    if (item.status === 'closed') return '已结单'
    if (item.pending_qc_quantity) return '质检中'
    return '进行中'
  },
  statusType(item) {
    return commonStatusType(item)
  },
  showInitialQc: item => (
    item.status === 'open'
    && item.qc_available
    && item.submitted_quantity === 0
  ),
  showDirectResult: item => (
    item.status === 'open'
    && item.direct_result_allowed
    && item.submitted_quantity === 0
  ),
  showReworkQc: (item, batch) => (
    item.status === 'open'
    && Boolean(batch.recorded_at)
    && batch.rework_pending_quantity > 0
  ),
}
