import { ElMessage, ElMessageBox } from 'element-plus'
import { getApiErrorDetail } from '@/api/request'
import { cancelWorkOrder, undoProductionOperation } from '../api/workOrders'
import type { WorkOrder, WorkOrderBatch } from '../domain/types'

export interface WorkOrderActions {
  submit: (item: WorkOrder) => Promise<void>
  submitQc: (item: WorkOrder) => Promise<void>
  resubmitQc: (item: WorkOrder, batch: WorkOrderBatch) => Promise<void>
  cancel: (item: WorkOrder) => Promise<void>
  undo: (item: WorkOrder) => Promise<void>
}

export function createUndoProductionOperationAction(onChanged: () => Promise<void>) {
  return async function undo(item: WorkOrder) {
    const operation = item.undo_operation
    if (!operation) return
    try {
      await ElMessageBox.confirm(
        `确认${operation.operation_label}？只有尚未发生后续流转的操作可以撤回。`,
        operation.operation_label,
        { type: 'warning' },
      )
      await undoProductionOperation(operation.id)
      await onChanged()
      ElMessage.success('生产操作已撤回')
    } catch (error) {
      if (error !== 'cancel' && error !== 'close') {
        ElMessage.error(getApiErrorDetail(error)?.message || '撤回失败')
      }
    }
  }
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
