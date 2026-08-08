import type { WorkOrderCardPolicy } from './workOrderCardPolicy'
import { commonStatusType, initialProcessingQuantity } from './workOrderCardPolicy'

export const assemblyWorkOrderCardPolicy: WorkOrderCardPolicy = {
  metricsClass: 'assembly-metrics',
  batchTitle: '送检与 QC 记录',
  completeLabel: () => '完成装配',
  showBatches: true,
  trackRework: true,
  metrics: item => [
    { label: '装配数量', value: item.quantity },
    { label: '装配/返工中', value: item.processing_quantity },
    { label: item.qc_required ? '待送检' : '待填结果', value: item.ready_for_qc_quantity },
    { label: '质检中', value: item.pending_qc_quantity },
    { label: '累计合格', value: item.qualified_quantity },
    { label: '报废 / 遗失', value: `${item.scrap_quantity} / ${item.lost_quantity}` },
  ],
  statusText(item) {
    if (item.status === 'cancelled') return '已取消'
    if (item.status === 'closed') return '已结单'
    if (item.pending_qc_quantity) return `${item.work_order_name}质检中`
    if (item.ready_for_qc_quantity) {
      return item.qc_required ? '装配完成，待送检' : '装配完成，待填结果'
    }
    return `${item.work_order_name}装配中`
  },
  statusType(item) {
    return commonStatusType(item)
  },
  showComplete: item => (
    item.status === 'open'
    && item.ready_for_qc_quantity === 0
    && initialProcessingQuantity(item) > 0
  ),
  disableComplete: () => false,
  showInitialQc: item => (
    item.status === 'open'
    && item.qc_required
    && item.ready_for_qc_quantity > 0
  ),
  showDirectResult: item => (
    item.status === 'open'
    && !item.qc_required
    && item.ready_for_qc_quantity > 0
  ),
  showReworkQc: (item, batch) => (
    item.status === 'open'
    && Boolean(batch.recorded_at)
    && batch.rework_pending_quantity > 0
  ),
}
