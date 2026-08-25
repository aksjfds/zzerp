import { computed, ref } from 'vue'
import { ElMessage } from 'element-plus'
import { getApiErrorDetail } from '@/api/request'
import { createWorkOrder } from '../api/workOrders'
import type { RepositoryFilters, RepositoryItem, WorkOrderQueryScope } from '../domain/types'
import { useDepartmentWorkspace } from './useDepartmentWorkspace'
import { useWorkOrderList } from './useWorkOrders'
import { useProductionWorkOrderActions } from './useProductionWorkOrderActions'

export function useProductionDepartment(departmentCode: string) {
  const workspace = useDepartmentWorkspace(departmentCode, true)
  const workOrderScope = computed<WorkOrderQueryScope | null>(() => {
    const item = workspace.selectedRepository.value
    return item ? {
      flowNodeId: item.flow_node_id,
      sourceFlowNodeId: item.source_flow_node_id,
    } : null
  })
  const workOrderList = useWorkOrderList(
    departmentCode,
    workspace.selectedProductionItemId,
    workspace.pageSize,
    workOrderScope,
  )
  const activeRepository = ref<RepositoryItem>()
  const dialogVisible = ref(false)
  const submitting = ref(false)

  async function loadDetails() {
    await workOrderList.load()
  }
  async function reloadWorkspace() {
    await workspace.loadRepositories()
    await loadDetails()
  }
  function selectRepository(item: RepositoryItem) {
    workspace.selectRepository(item)
    workOrderList.reset()
    void loadDetails()
  }
  async function openWorkOrder(item: RepositoryItem) {
    workspace.selectRepository(item)
    activeRepository.value = item
    if (!item.repository_id || item.available_quantity < 1) {
      ElMessage.warning('当前物料没有可用数量')
      return
    }
    await loadDetails()
    dialogVisible.value = true
  }
  async function saveWorkOrder(payload: {
    repositoryId: number
    procedureId: number | null
    procedureName: string | null
    quantity: number
    workerId: number | null
    remark: string
  }) {
    submitting.value = true
    try {
      await createWorkOrder(
        payload.repositoryId,
        payload.procedureId,
        payload.procedureName,
        payload.quantity,
        payload.workerId,
        payload.remark,
      )
      dialogVisible.value = false
      await reloadWorkspace()
      ElMessage.success('工单已创建')
    } catch (error) {
      ElMessage.error(getApiErrorDetail(error)?.message || '创建工单失败')
    } finally {
      submitting.value = false
    }
  }
  async function refresh() {
    workOrderList.reset()
    await workspace.refresh()
    await loadDetails()
  }
  async function changeRepositoryPage(page: number) {
    workOrderList.reset()
    await workspace.changePage(page)
    await loadDetails()
  }
  async function applyFilters(filters: RepositoryFilters) {
    workOrderList.reset()
    await workspace.search(filters)
    await loadDetails()
  }
  async function load() {
    await workspace.load()
    await loadDetails()
  }

  return {
    activeRepository, applyFilters, changeRepositoryPage, dialogVisible,
    load, loadDetails, openWorkOrder, reloadWorkspace, refresh,
    saveWorkOrder, selectRepository, submitting,
    workOrderActions: useProductionWorkOrderActions(reloadWorkspace),
    workOrderList, workspace,
  }
}
