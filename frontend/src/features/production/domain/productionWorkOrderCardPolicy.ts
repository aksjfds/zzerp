import type { WorkOrderCardPolicy } from './workOrderCardPolicy'
import {
  commonStatusType,
  initialProcessingQuantity,
} from './workOrderCardPolicy'

export const productionWorkOrderCardPolicy: WorkOrderCardPolicy = {
  batchTitle: '送检与 QC 记录',
  completeLabel: () => '加工完成',
  showBatches: true,
  trackRework: true,
  metrics: item => [
    { label: '领料数', value: item.quantity },
    { label: '加工中', value: item.processing_quantity },
    { label: item.qc_required ? '待送检' : '待填结果', value: item.ready_for_qc_quantity },
    { label: '质检中', value: item.pending_qc_quantity },
    { label: '累计合格', value: item.qualified_quantity },
    { label: '累计返工', value: item.rework_quantity },
    { label: '报废 / 遗失', value: `${item.scrap_quantity} / ${item.lost_quantity}` },
  ],
  statusText(item) {
    if (item.status === 'cancelled') return '已取消'
    if (item.pending_qc_quantity) return `${item.work_order_name}质检中`
    if (item.ready_for_qc_quantity) {
      return item.qc_required ? '加工完成，待送检' : '加工完成，待填结果'
    }
    if (item.status === 'closed') return '已结单'
    return `${item.work_order_name}加工中`
  },
  statusType: commonStatusType,
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
