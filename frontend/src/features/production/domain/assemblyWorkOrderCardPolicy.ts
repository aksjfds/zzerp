import type { WorkOrderCardPolicy } from './workOrderCardPolicy'

export const assemblyWorkOrderCardPolicy: WorkOrderCardPolicy = {
  metricsClass: 'assembly-metrics',
  batchTitle: '',
  completeLabel: () => '完成装配',
  showBatches: false,
  trackRework: false,
  metrics: item => [
    { label: '装配数量', value: item.quantity },
    { label: '装配中', value: item.processing_quantity },
    { label: '已完成', value: item.submitted_quantity },
    { label: '报废 / 遗失', value: `${item.scrap_quantity} / ${item.lost_quantity}` },
  ],
  statusText(item) {
    if (item.status === 'cancelled') return '已取消'
    if (item.status === 'closed') return '已结单'
    return `${item.work_order_name}装配中`
  },
  statusType(item) {
    if (item.status === 'cancelled') return 'info'
    return item.status === 'closed' ? 'success' : 'primary'
  },
  showComplete: item => item.status === 'open' && item.processing_quantity > 0,
  disableComplete: () => false,
  showInitialQc: () => false,
  showReworkQc: () => false,
}
