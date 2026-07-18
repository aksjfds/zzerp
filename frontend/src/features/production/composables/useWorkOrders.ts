import { ref, type Ref } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { getApiErrorDetail } from '@/api/request'
import {
  cancelWorkOrder, queryDepartmentWorkOrders, submitWorkOrder,
} from '../api/workOrders'
import type { CompletionAction, WorkOrder, WorkOrderQueryScope } from '../domain/types'

export function useWorkOrderList(
  departmentCode: string,
  productionItemId: Ref<number | null>,
  pageSize: number,
  scope?: Ref<WorkOrderQueryScope | null>,
) {
  const items = ref<WorkOrder[]>([])
  const loading = ref(false)
  const page = ref(1)
  const total = ref(0)
  let loadSequence = 0

  async function load() {
    const sequence = ++loadSequence
    const requestedProductionItemId = productionItemId.value
    const requestedPage = page.value
    const requestedScope = scope?.value ? { ...scope.value } : null
    items.value = []
    total.value = 0
    if (!requestedProductionItemId || (scope && !requestedScope)) {
      loading.value = false
      return
    }
    loading.value = true
    try {
      const result = await queryDepartmentWorkOrders(
        departmentCode,
        requestedPage,
        pageSize,
        requestedProductionItemId,
        requestedScope?.flowNodeId,
        requestedScope?.sourceFlowNodeId,
        requestedScope?.substepId,
      )
      const currentScope = scope?.value
      if (
        sequence !== loadSequence
        || productionItemId.value !== requestedProductionItemId
        || page.value !== requestedPage
        || (scope && (
          !currentScope
          || currentScope.flowNodeId !== requestedScope?.flowNodeId
          || currentScope.sourceFlowNodeId !== requestedScope?.sourceFlowNodeId
          || currentScope.substepId !== requestedScope?.substepId
        ))
      ) return
      items.value = result.items
      total.value = result.total
    } catch {
      if (sequence === loadSequence) ElMessage.warning('关联生产记录加载失败')
    } finally {
      if (sequence === loadSequence) loading.value = false
    }
  }

  function reset() {
    loadSequence += 1
    page.value = 1
    items.value = []
    total.value = 0
    loading.value = false
  }
  return { items, load, loading, page, reset, total }
}

export function useWorkOrderActions(
  onChanged: () => Promise<void>,
  mode: 'production' | 'purchase' | 'assembly' = 'production',
) {
  async function chooseCompletionAction(): Promise<CompletionAction | null> {
    if (mode !== 'purchase') return 'direct'
    try {
      await ElMessageBox.confirm(
        '本次到货是否送 QC 检验？',
        '选择完成方式',
        {
          confirmButtonText: '送 QC',
          cancelButtonText: '直接入库',
          distinguishCancelAndClose: true,
          type: 'warning',
        },
      )
      return 'qc'
    } catch (action) {
      if (action === 'cancel') return 'direct'
      if (action === 'close') return null
      throw action
    }
  }

  async function submit(item: WorkOrder) {
    try {
      const completionAction = await chooseCompletionAction()
      if (!completionAction) return
      let quantity = item.processing_quantity
      if (mode === 'purchase' || completionAction === 'qc') {
        const { value } = await ElMessageBox.prompt(
          mode === 'purchase' ? '请输入本次实际到货数量' : '请输入本次送检数量',
          mode === 'purchase' ? '登记到货' : '工艺送检', {
            inputValue: String(item.processing_quantity),
            inputPattern: /^[1-9]\d*$/,
            inputErrorMessage: '请输入正整数',
          },
        )
        quantity = Number(value)
      } else {
        await ElMessageBox.confirm(
          mode === 'assembly'
            ? `确认完成剩余 ${item.processing_quantity} 件并结单？`
            : `确认完成剩余 ${item.processing_quantity} 件？`,
          mode === 'assembly' ? '装配完成' : '完成细分',
          { type: 'warning' },
        )
      }
      await submitWorkOrder(
        item.id,
        quantity,
        completionAction,
      )
      await onChanged()
      ElMessage.success(
        completionAction === 'qc'
          ? '已送 QC 检验'
          : mode === 'purchase' ? '到货数量已入库'
            : mode === 'assembly' ? '装配结果已结单'
              : '细分已完成',
      )
    } catch (error) {
      if (error !== 'cancel' && error !== 'close') {
        ElMessage.error(
          getApiErrorDetail(error)?.message
          || (mode === 'purchase' ? '到货登记失败' : mode === 'assembly' ? '装配提交失败' : '工艺提交失败'),
        )
      }
    }
  }

  async function submitQc(item: WorkOrder) {
    if (mode !== 'production') return
    try {
      const { value } = await ElMessageBox.prompt(
        '请输入本次送检数量',
        `工单 ${item.work_order_no} 送检`,
        {
          inputValue: String(item.processing_quantity),
          inputPattern: /^[1-9]\d*$/,
          inputErrorMessage: '请输入正整数',
        },
      )
      const quantity = Number(value)
      if (!Number.isInteger(quantity) || quantity < 1 || quantity > item.processing_quantity) {
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

  async function cancel(item: WorkOrder) {
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
  return { cancel, submit, submitQc }
}
