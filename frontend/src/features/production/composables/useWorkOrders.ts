import { ref, type Ref } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { getApiErrorDetail } from '@/api/request'
import {
  cancelWorkOrder, queryDepartmentWorkOrders, submitWorkOrder,
} from '../api/repositories'
import type { WorkOrder } from '../domain/types'

export function useWorkOrderList(
  departmentCode: string,
  productionItemId: Ref<number | null>,
  pageSize: number,
) {
  const items = ref<WorkOrder[]>([])
  const loading = ref(false)
  const page = ref(1)
  const total = ref(0)

  async function load() {
    items.value = []
    total.value = 0
    if (!productionItemId.value) return
    loading.value = true
    try {
      const result = await queryDepartmentWorkOrders(
        departmentCode, page.value, pageSize, productionItemId.value,
      )
      items.value = result.items
      total.value = result.total
    } catch { ElMessage.warning('关联生产记录加载失败') }
    finally { loading.value = false }
  }

  function reset() { page.value = 1 }
  return { items, load, loading, page, reset, total }
}

export function useWorkOrderActions(onChanged: () => Promise<void>) {
  async function submit(item: WorkOrder) {
    try {
      const { value } = await ElMessageBox.prompt('请输入本次完成或送检数量', '工艺完成', {
        inputValue: String(item.quantity - item.submitted_quantity),
        inputPattern: /^[1-9]\d*$/,
        inputErrorMessage: '请输入正整数',
      })
      await submitWorkOrder(item.id, Number(value))
      await onChanged()
      ElMessage.success('工艺结果已提交')
    } catch (error) {
      if (error !== 'cancel' && error !== 'close') {
        ElMessage.error(getApiErrorDetail(error)?.message || '工艺提交失败')
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
  return { cancel, submit }
}
