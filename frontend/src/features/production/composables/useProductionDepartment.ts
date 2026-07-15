import { ref } from 'vue'
import { ElMessage } from 'element-plus'
import { getApiErrorDetail } from '@/api/request'
import { createWorkOrder } from '../api/workOrders'
import type { RepositoryFilters, RepositoryItem } from '../domain/types'
import { useDepartmentWorkspace } from './useDepartmentWorkspace'
import { useWorkOrderActions, useWorkOrderList } from './useWorkOrders'

export function useProductionDepartment(
  departmentCode: string,
  mode: 'production' | 'purchase' = 'production',
) {
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
      ElMessage.success(mode === 'purchase' ? '外购入库单已创建' : '工单已创建')
    } catch (error) {
      ElMessage.error(getApiErrorDetail(error)?.message || '创建工单失败')
    } finally {
      submitting.value = false
    }
  }

  async function refresh() {
    workOrderList.reset()
    const refreshRequest = workspace.refresh()
    await loadDetails()
    await refreshRequest
  }

  async function changeRepositoryPage(page: number) {
    workOrderList.reset()
    const pageRequest = workspace.changePage(page)
    await loadDetails()
    await pageRequest
  }

  async function applyFilters(filters: RepositoryFilters) {
    workOrderList.reset()
    const searchRequest = workspace.search(filters)
    await loadDetails()
    await searchRequest
  }

  async function load() {
    await workspace.load()
    await loadDetails()
  }

  return {
    activeRepository,
    applyFilters,
    changeRepositoryPage,
    dialogVisible,
    load,
    loadDetails,
    openWorkOrder,
    refresh,
    saveWorkOrder,
    selectRepository,
    submitting,
    workOrderActions: useWorkOrderActions(reloadWorkspace, mode),
    workOrderList,
    workspace,
  }
}
