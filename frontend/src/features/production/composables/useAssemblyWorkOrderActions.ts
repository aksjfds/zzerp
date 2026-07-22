import { ElMessage, ElMessageBox } from 'element-plus'
import { getApiErrorDetail } from '@/api/request'
import { resubmitReworkBatch, submitWorkOrder } from '../api/workOrders'
import type { WorkOrder, WorkOrderBatch } from '../domain/types'
import {
  createCancelWorkOrderAction,
  createUndoProductionOperationAction,
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

  async function submitQc(item: WorkOrder) {
    try {
      const quantity = Math.max(item.quantity - item.submitted_quantity, 0)
      await ElMessageBox.confirm(
        `确认完成剩余 ${quantity} 件装配并送 QC？`,
        '装配送检',
        { type: 'warning' },
      )
      await submitWorkOrder(item.id, quantity, 'qc')
      await onChanged()
      ElMessage.success('装配产出已送 QC')
    } catch (error) {
      if (error !== 'cancel' && error !== 'close') {
        ElMessage.error(getApiErrorDetail(error)?.message || '装配送检失败')
      }
    }
  }

  async function resubmitQc(item: WorkOrder, batch: WorkOrderBatch) {
    if (batch.rework_pending_quantity < 1) return
    try {
      const { value } = await ElMessageBox.prompt(
        '请输入本次返工送检数量',
        `工单 ${item.work_order_no} · 批次 ${batch.id}`,
        {
          inputValue: String(batch.rework_pending_quantity),
          inputPattern: /^[1-9]\d*$/,
          inputErrorMessage: '请输入正整数',
        },
      )
      const quantity = Number(value)
      if (!Number.isInteger(quantity) || quantity < 1 || quantity > batch.rework_pending_quantity) {
        ElMessage.warning('送检数量不能超过该批次待返工数量')
        return
      }
      await resubmitReworkBatch(batch.id, quantity)
      await onChanged()
      ElMessage.success('装配返工件已重新送 QC')
    } catch (error) {
      if (error !== 'cancel' && error !== 'close') {
        ElMessage.error(getApiErrorDetail(error)?.message || '返工送检失败')
      }
    }
  }

  return {
    cancel: createCancelWorkOrderAction(onChanged),
    resubmitQc,
    submit,
    submitQc,
    undo: createUndoProductionOperationAction(onChanged),
  }
}
