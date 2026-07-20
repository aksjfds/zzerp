import { ElMessage, ElMessageBox } from 'element-plus'
import { getApiErrorDetail } from '@/api/request'
import { submitWorkOrder } from '../api/workOrders'
import type { WorkOrder } from '../domain/types'
import {
  createCancelWorkOrderAction,
  ignoreWorkOrderAction,
  type WorkOrderActions,
} from './workOrderActionSupport'

export function usePurchaseWorkOrderActions(
  onChanged: () => Promise<void>,
): WorkOrderActions {
  async function submit(item: WorkOrder) {
    try {
      const completionAction = item.qc_required ? 'qc' : 'direct'
      const { value } = await ElMessageBox.prompt(
        '请输入本次实际到货数量',
        item.qc_required ? '登记到货并送检' : '登记到货',
        {
          inputValue: String(item.processing_quantity),
          inputPattern: /^[1-9]\d*$/,
          inputErrorMessage: '请输入正整数',
        },
      )
      await submitWorkOrder(item.id, Number(value), completionAction)
      await onChanged()
      ElMessage.success(
        completionAction === 'qc' ? '已送 QC 检验' : '到货数量已入库',
      )
    } catch (error) {
      if (error !== 'cancel' && error !== 'close') {
        ElMessage.error(getApiErrorDetail(error)?.message || '到货登记失败')
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
