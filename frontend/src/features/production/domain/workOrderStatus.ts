import type { WorkOrderStatus } from './types'

export const workOrderStatusLabels: Record<WorkOrderStatus, string> = {
  open: '进行中',
  closed: '已完成',
  cancelled: '已取消',
}

export function workOrderStatusLabel(status: WorkOrderStatus) {
  return workOrderStatusLabels[status]
}
