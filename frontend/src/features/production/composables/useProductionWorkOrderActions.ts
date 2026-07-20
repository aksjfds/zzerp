import { ElMessage, ElMessageBox } from 'element-plus'
import { getApiErrorDetail } from '@/api/request'
import {
  completeWorkOrder,
  resubmitReworkBatch,
  submitWorkOrder,
} from '../api/workOrders'
import type { WorkOrder, WorkOrderBatch } from '../domain/types'
import {
  createCancelWorkOrderAction,
  type WorkOrderActions,
} from './workOrderActionSupport'

export function useProductionWorkOrderActions(
  onChanged: () => Promise<void>,
): WorkOrderActions {
  async function submit(item: WorkOrder) {
    try {
      const initialRemaining = Math.max(item.quantity - item.submitted_quantity, 0)
      await ElMessageBox.confirm(
        initialRemaining
          ? `确认将剩余 ${initialRemaining} 件按无需 QC 完成，并结单？`
          : '确认该工单的送检和返工已经处理完毕，并结单？',
        '完成工单',
        { type: 'warning' },
      )
      await completeWorkOrder(item.id)
      await onChanged()
      ElMessage.success('工单已完成并结单')
    } catch (error) {
      if (error !== 'cancel' && error !== 'close') {
        ElMessage.error(getApiErrorDetail(error)?.message || '工艺提交失败')
      }
    }
  }

  async function submitQc(item: WorkOrder) {
    try {
      const initialRemaining = Math.max(item.quantity - item.submitted_quantity, 0)
      const { value } = await ElMessageBox.prompt(
        '请输入本次送检数量',
        `工单 ${item.work_order_no} 送检`,
        {
          inputValue: String(initialRemaining),
          inputPattern: /^[1-9]\d*$/,
          inputErrorMessage: '请输入正整数',
        },
      )
      const quantity = Number(value)
      if (!Number.isInteger(quantity) || quantity < 1 || quantity > initialRemaining) {
        ElMessage.warning('送检数量不能超过工单加工中数量')
        return
      }
      await submitWorkOrder(item.id, quantity, 'qc')
      await onChanged()
      ElMessage.success('已送 QC 检验')
    } catch (error) {
      if (error !== 'cancel' && error !== 'close') {
        ElMessage.error(getApiErrorDetail(error)?.message || '送检失败')
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
      if (
        !Number.isInteger(quantity)
        || quantity < 1
        || quantity > batch.rework_pending_quantity
      ) {
        ElMessage.warning('送检数量不能超过该批次待返工数量')
        return
      }
      await resubmitReworkBatch(batch.id, quantity)
      await onChanged()
      ElMessage.success('返工件已重新送 QC')
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
  }
}
