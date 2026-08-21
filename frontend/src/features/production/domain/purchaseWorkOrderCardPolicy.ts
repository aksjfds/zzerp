import type { WorkOrderCardPolicy } from './workOrderCardPolicy'
import { commonStatusType } from './workOrderCardPolicy'

export const purchaseWorkOrderCardPolicy: WorkOrderCardPolicy = {
  batchTitle: '到货与质检记录',
  showBatches: true,
  trackRework: false,
  metrics: item => [
    { label: '外购数量', value: item.quantity },
    { label: '已到货', value: item.processed_quantity },
    { label: '待到货', value: item.processing_quantity },
    { label: '合格数量', value: item.qualified_quantity },
    ...(item.pending_qc_quantity ? [{ label: '质检中', value: item.pending_qc_quantity }] : []),
  ],
  statusText(item) {
    if (item.status === 'cancelled') return '已取消'
    if (item.pending_qc_quantity) return '质检中'
    if (item.processing_quantity > 0) return '待到货'
    if (item.ready_for_qc_quantity) return '待处理'
    if (item.status === 'closed') return '已完成'
    return '进行中'
  },
  statusType: commonStatusType,
  showInitialQc: item => (
    item.status === 'open'
    && item.qc_available
    && item.processing_quantity === 0
    && item.ready_for_qc_quantity > 0
  ),
  showDirectResult: item => (
    item.status === 'open'
    && item.direct_result_allowed
    && item.processing_quantity === 0
    && item.ready_for_qc_quantity > 0
  ),
  showReworkQc: () => false,
}
