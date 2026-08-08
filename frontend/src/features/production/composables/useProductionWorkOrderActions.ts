import { ElMessage, ElMessageBox } from 'element-plus'
import { getApiErrorDetail } from '@/api/request'
import {
  completeWorkOrderProcessing,
  resubmitReworkBatch,
  submitWorkOrder,
} from '../api/workOrders'
import type { WorkOrder, WorkOrderBatch } from '../domain/types'
import {
  createCancelWorkOrderAction,
  createDirectResultAction,
  createUndoProductionOperationAction,
  type WorkOrderActions,
} from './workOrderActionSupport'

export function useProductionWorkOrderActions(
  onChanged: () => Promise<void>,
): WorkOrderActions {
  function batchSequence(item: WorkOrder, batch: WorkOrderBatch) {
    const index = item.batches.findIndex(candidate => candidate.id === batch.id)
    return index >= 0 ? index + 1 : '—'
  }

  async function submit(item: WorkOrder) {
    const remaining = Math.max(item.quantity - item.processed_quantity, 0)
    try {
      const { value } = await ElMessageBox.prompt(
        `加工中 ${remaining} 件，请输入本次加工完成数量`,
        `工单 ${item.work_order_no} 加工完成`,
        {
          inputValue: String(remaining),
          inputPattern: /^[1-9]\d*$/,
          inputErrorMessage: '请输入正整数',
        },
      )
      const quantity = Number(value)
      if (!Number.isInteger(quantity) || quantity < 1 || quantity > remaining) {
        ElMessage.warning('加工完成数量不能超过加工中数量')
        return
      }
      await completeWorkOrderProcessing(item.id, quantity)
      await onChanged()
      ElMessage.success(
        item.qc_required
          ? '已登记加工完成，等待送检'
          : '已登记加工完成，等待填写加工结果',
      )
    } catch (error) {
      if (error !== 'cancel' && error !== 'close') {
        ElMessage.error(getApiErrorDetail(error)?.message || '加工完成登记失败')
      }
    }
  }

  async function submitQc(item: WorkOrder) {
    try {
      const initialRemaining = item.ready_for_qc_quantity
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
        ElMessage.warning('送检数量不能超过待送检数量')
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
        `工单 ${item.work_order_no} · 第 ${batchSequence(item, batch)} 批`,
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
    submitDirectResult: createDirectResultAction(onChanged),
    undo: createUndoProductionOperationAction(onChanged),
  }
}
