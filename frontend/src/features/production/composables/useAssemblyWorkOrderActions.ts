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

export function useAssemblyWorkOrderActions(
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
        `确认将整张工单全部送检？共 ${quantity} 件产品，对应 ${quantity * item.output_unit_quantity} 个装配体。`,
        '装配工单 · 整单送检',
        { confirmButtonText: '全部送检', cancelButtonText: '取消' },
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
      const quantity = batch.rework_pending_quantity
      await ElMessageBox.confirm(
        `确认将该批 ${quantity} 个返工装配体全部重新送检？`,
        `工单 ${item.work_order_no} · 第 ${batchSequence(item, batch)} 批`,
        { confirmButtonText: '全部送检', cancelButtonText: '取消' },
      )
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
    registerArrival: ignoreWorkOrderAction,
    submitQc,
    submitDirectResult: createDirectResultAction(onChanged, '装配'),
    undo: createUndoProductionOperationAction(onChanged),
  }
}
