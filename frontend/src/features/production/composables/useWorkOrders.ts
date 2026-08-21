import { ref, type Ref } from 'vue'
import { ElMessage } from 'element-plus'
import { queryDepartmentWorkOrders } from '../api/workOrders'
import type { WorkOrder, WorkOrderQueryScope } from '../domain/types'

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
    if (!requestedProductionItemId || (scope && !requestedScope)) {
      items.value = []
      total.value = 0
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
