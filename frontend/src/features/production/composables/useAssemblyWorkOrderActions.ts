import { ElMessage, ElMessageBox } from 'element-plus'
import { getApiErrorDetail } from '@/api/request'
import { submitWorkOrder } from '../api/workOrders'
import type { WorkOrder } from '../domain/types'
import {
  createCancelWorkOrderAction,
  ignoreWorkOrderAction,
  type WorkOrderActions,
} from './workOrderActionSupport'

export function useAssemblyWorkOrderActions(
  onChanged: () => Promise<void>,
): WorkOrderActions {
  async function submit(item: WorkOrder) {
    try {
      await ElMessageBox.confirm(
        `确认完成剩余 ${item.processing_quantity} 件并结单？`,
        '装配完成',
        { type: 'warning' },
      )
      await submitWorkOrder(item.id, item.processing_quantity, 'direct')
      await onChanged()
      ElMessage.success('装配结果已结单')
    } catch (error) {
      if (error !== 'cancel' && error !== 'close') {
        ElMessage.error(getApiErrorDetail(error)?.message || '装配提交失败')
      }
    }
  }

  return {
    cancel: createCancelWorkOrderAction(onChanged),
    resubmitQc: ignoreWorkOrderAction,
    submit,
    submitQc: ignoreWorkOrderAction,
  }
}
