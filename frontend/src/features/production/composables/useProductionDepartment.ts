import { ref } from 'vue'
import { ElMessage } from 'element-plus'
import { getApiErrorDetail } from '@/api/request'
import { createWorkOrder } from '../api/workOrders'
import type { RepositoryFilters, RepositoryItem } from '../domain/types'
import { useDepartmentWorkspace } from './useDepartmentWorkspace'
import { useWorkOrderActions, useWorkOrderList } from './useWorkOrders'

export function useProductionDepartment(departmentCode: string) {
  const workspace = useDepartmentWorkspace(departmentCode, true)
  const workOrderList = useWorkOrderList(
    departmentCode,
    workspace.selectedProductionItemId,
    workspace.pageSize,
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

  function openWorkOrder(item: RepositoryItem) {
    selectRepository(item)
    activeRepository.value = item
    dialogVisible.value = true
  }

  async function saveWorkOrder(payload: { quantity: number; workerId: number | null }) {
    if (!activeRepository.value?.repository_id) return
    submitting.value = true
    try {
      await createWorkOrder(
        activeRepository.value.repository_id,
        payload.quantity,
        payload.workerId,
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

  async function applyFilters(filters: RepositoryFilters) {
    workOrderList.reset()
    workspace.search(filters)
    await loadDetails()
  }

  async function load() {
    await workspace.load()
    await loadDetails()
  }

  return {
    activeRepository,
    applyFilters,
    dialogVisible,
    load,
    loadDetails,
    openWorkOrder,
    refresh,
    saveWorkOrder,
    selectRepository,
    submitting,
    workOrderActions: useWorkOrderActions(reloadWorkspace),
    workOrderList,
    workspace,
  }
}
