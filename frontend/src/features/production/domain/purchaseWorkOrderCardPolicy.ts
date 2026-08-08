import type { WorkOrderCardPolicy } from './workOrderCardPolicy'
import { commonStatusType } from './workOrderCardPolicy'

export const purchaseWorkOrderCardPolicy: WorkOrderCardPolicy = {
  metricsClass: 'purchase-metrics',
  batchTitle: '到货与 QC 记录',
  completeLabel: () => '登记到货',
  showBatches: true,
  trackRework: false,
  metrics: item => [
    { label: '外购数量', value: item.quantity },
    { label: '已到货', value: item.processed_quantity },
    { label: '待送检', value: item.ready_for_qc_quantity },
    { label: '质检中', value: item.pending_qc_quantity },
    { label: '已合格入库', value: item.qualified_quantity },
    { label: '待到货', value: item.processing_quantity },
  ],
  statusText(item) {
    if (item.status === 'cancelled') return '已取消'
    if (item.pending_qc_quantity) return `${item.work_order_name}质检中`
    if (item.ready_for_qc_quantity) return '已到货，待送检'
    if (item.status === 'closed') return '已全部到货'
    return '采购 / 到货中'
  },
  statusType: commonStatusType,
  showComplete: item => (
    item.status === 'open'
    && item.ready_for_qc_quantity === 0
    && item.processing_quantity > 0
  ),
  disableComplete: () => false,
  showInitialQc: item => item.status === 'open' && item.qc_required && item.ready_for_qc_quantity > 0,
  showDirectResult: () => false,
  showReworkQc: () => false,
}
