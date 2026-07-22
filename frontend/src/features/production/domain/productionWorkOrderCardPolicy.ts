import type { WorkOrderCardPolicy } from './workOrderCardPolicy'
import {
  commonStatusType,
  initialProcessingQuantity,
} from './workOrderCardPolicy'

export const productionWorkOrderCardPolicy: WorkOrderCardPolicy = {
  batchTitle: '送检与 QC 记录',
  completeLabel: () => '完成',
  showBatches: true,
  trackRework: true,
  metrics: item => [
    { label: '领料数', value: item.quantity },
    { label: '加工中', value: item.processing_quantity },
    { label: '质检中', value: item.pending_qc_quantity },
    { label: '累计合格', value: item.qualified_quantity },
    { label: '累计返工', value: item.rework_quantity },
    { label: '报废 / 遗失', value: `${item.scrap_quantity} / ${item.lost_quantity}` },
  ],
  statusText(item) {
    if (item.status === 'cancelled') return '已取消'
    if (item.pending_qc_quantity) return `${item.work_order_name}质检中`
    if (item.status === 'closed') return '已结单'
    return `${item.work_order_name}加工中`
  },
  statusType: commonStatusType,
  showComplete: () => false,
  disableComplete: () => false,
  showInitialQc: item => (
    item.status === 'open'
    && initialProcessingQuantity(item) > 0
  ),
  showReworkQc: (item, batch) => (
    item.status === 'open'
    && Boolean(batch.recorded_at)
    && batch.rework_pending_quantity > 0
  ),
}
