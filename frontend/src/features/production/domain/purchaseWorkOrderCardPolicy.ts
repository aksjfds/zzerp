import type { WorkOrderCardPolicy } from './workOrderCardPolicy'
import { commonStatusType } from './workOrderCardPolicy'

export const purchaseWorkOrderCardPolicy: WorkOrderCardPolicy = {
  metricsClass: 'purchase-metrics',
  batchTitle: '到货与 QC 记录',
  completeLabel: item => item.qc_required ? '登记到货并送检' : '登记到货',
  showBatches: true,
  trackRework: false,
  metrics: item => [
    { label: '外购数量', value: item.quantity },
    { label: '已登记', value: item.submitted_quantity },
    { label: '质检中', value: item.pending_qc_quantity },
    { label: '已合格入库', value: item.qualified_quantity },
    { label: '待到货', value: item.processing_quantity },
  ],
  statusText(item) {
    if (item.status === 'cancelled') return '已取消'
    if (item.pending_qc_quantity) return `${item.work_order_name}质检中`
    if (item.status === 'closed') return '已全部到货'
    return '采购 / 到货中'
  },
  statusType: commonStatusType,
  showComplete: item => item.status === 'open' && item.processing_quantity > 0,
  disableComplete: () => false,
  showInitialQc: () => false,
  showReworkQc: () => false,
}
