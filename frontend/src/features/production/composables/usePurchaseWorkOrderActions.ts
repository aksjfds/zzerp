import { ElMessage, ElMessageBox } from 'element-plus'
import { getApiErrorDetail } from '@/api/request'
import { registerPurchaseArrival, submitWorkOrder } from '../api/workOrders'
import type { WorkOrder } from '../domain/types'
import {
  createCancelWorkOrderAction,
  createUndoProductionOperationAction,
  ignoreWorkOrderAction,
  type WorkOrderActions,
} from './workOrderActionSupport'

export function usePurchaseWorkOrderActions(
  onChanged: () => Promise<void>,
): WorkOrderActions {
  async function registerArrival(item: WorkOrder) {
    try {
      const remaining = Math.max(item.quantity - item.processed_quantity, 0)
      const { value } = await ElMessageBox.prompt(
        '请输入本次实际到货数量',
        '登记到货',
        {
          inputValue: String(remaining),
          inputPattern: /^[1-9]\d*$/,
          inputErrorMessage: '请输入正整数',
        },
      )
      const quantity = Number(value)
      if (!Number.isInteger(quantity) || quantity < 1 || quantity > remaining) {
        ElMessage.warning('到货数量不能超过待到货数量')
        return
      }
      if (item.qc_required) {
        await registerPurchaseArrival(item.id, quantity)
      } else {
        await submitWorkOrder(item.id, quantity, 'direct')
      }
      await onChanged()
      ElMessage.success(
        item.qc_required
          ? '到货数量已登记'
          : '到货数量已入库',
      )
    } catch (error) {
      if (error !== 'cancel' && error !== 'close') {
        ElMessage.error(getApiErrorDetail(error)?.message || '到货登记失败')
      }
    }
  }

  async function submitQc(item: WorkOrder) {
    try {
      const quantity = item.ready_for_qc_quantity
      await ElMessageBox.confirm(
        `确认将整张外购工单的 ${quantity} 件全部送检？`,
        '外购工单 · 整单送检',
        { confirmButtonText: '全部送检', cancelButtonText: '取消' },
      )
      await submitWorkOrder(item.id, quantity, 'qc')
      await onChanged()
      ElMessage.success('已送 QC 检验')
    } catch (error) {
      if (error !== 'cancel' && error !== 'close') {
        ElMessage.error(getApiErrorDetail(error)?.message || '送检失败')
      }
    }
  }

  return {
    cancel: createCancelWorkOrderAction(onChanged),
    resubmitQc: ignoreWorkOrderAction,
    registerArrival,
    submitQc,
    submitDirectResult: ignoreWorkOrderAction,
    undo: createUndoProductionOperationAction(onChanged),
  }
}
