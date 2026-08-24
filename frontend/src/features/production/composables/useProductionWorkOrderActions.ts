import { ElMessage, ElMessageBox } from 'element-plus'
import { getApiErrorDetail } from '@/api/request'
import { resubmitReworkBatch, submitWorkOrder } from '../api/workOrders'
import type { WorkOrder, WorkOrderBatch } from '../domain/types'
import {
  createCancelWorkOrderAction,
  createDirectResultAction,
  createUndoProductionOperationAction,
  ignoreWorkOrderAction,
  type WorkOrderActions,
} from './workOrderActionSupport'

export function useProductionWorkOrderActions(
  onChanged: () => Promise<void>,
): WorkOrderActions {
  function batchSequence(item: WorkOrder, batch: WorkOrderBatch) {
    const index = item.batches.findIndex(candidate => candidate.id === batch.id)
    return index >= 0 ? index + 1 : '—'
  }

  async function submitQc(item: WorkOrder) {
    try {
      const quantity = item.quantity
      await ElMessageBox.confirm(
        `确认将整张工单的 ${quantity} 件全部送检？`,
        `工单 ${item.work_order_no} · 整单送检`,
        { confirmButtonText: '全部送检', cancelButtonText: '取消' },
      )
      await submitWorkOrder(item.id, 'qc')
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
      const quantity = batch.rework_pending_quantity
      await ElMessageBox.confirm(
        `确认将该批 ${quantity} 件返工件全部重新送检？`,
        `工单 ${item.work_order_no} · 第 ${batchSequence(item, batch)} 批`,
        { confirmButtonText: '全部送检', cancelButtonText: '取消' },
      )
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
    registerArrival: ignoreWorkOrderAction,
    submitQc,
    submitDirectResult: createDirectResultAction(onChanged),
    undo: createUndoProductionOperationAction(onChanged),
  }
}
