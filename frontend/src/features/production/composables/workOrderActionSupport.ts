import { ElMessage, ElMessageBox } from 'element-plus'
import { getApiErrorDetail } from '@/api/request'
import { cancelWorkOrder } from '../api/workOrders'
import type { WorkOrder, WorkOrderBatch } from '../domain/types'

export interface WorkOrderActions {
  submit: (item: WorkOrder) => Promise<void>
  submitQc: (item: WorkOrder) => Promise<void>
  resubmitQc: (item: WorkOrder, batch: WorkOrderBatch) => Promise<void>
  cancel: (item: WorkOrder) => Promise<void>
}

export function createCancelWorkOrderAction(onChanged: () => Promise<void>) {
  return async function cancel(item: WorkOrder) {
    try {
      await ElMessageBox.confirm(`确认取消工单 ${item.work_order_no}？`, '取消工单')
      await cancelWorkOrder(item.id)
      await onChanged()
      ElMessage.success('工单已取消')
    } catch (error) {
      if (error !== 'cancel' && error !== 'close') {
        ElMessage.error(getApiErrorDetail(error)?.message || '取消工单失败')
      }
    }
  }
}

export async function ignoreWorkOrderAction() {}
