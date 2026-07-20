import { computed, ref } from 'vue'
import { ElMessage } from 'element-plus'
import { getApiErrorDetail } from '@/api/request'
import { createAssemblyWorkOrder } from '../api/workOrders'
import type { RepositoryFilters, RepositoryItem } from '../domain/types'
import { useAssemblyGroups, type AssemblyGroup } from './useAssemblyGroups'
import { useDepartmentWorkspace } from './useDepartmentWorkspace'
import { useWorkOrderList } from './useWorkOrders'
import { useAssemblyWorkOrderActions } from './useAssemblyWorkOrderActions'

export function useAssemblyDepartment() {
  const workspace = useDepartmentWorkspace('assembly', true)
  const assembly = useAssemblyGroups(workspace.items)
  const workOrderList = useWorkOrderList(
    'assembly',
    workspace.selectedProductionItemId,
    workspace.pageSize,
  )
  const activeRepository = ref<RepositoryItem>()
  const dialogVisible = ref(false)
  const submitting = ref(false)
  const selectedGroupKey = computed(() => workspace.selectedRepository.value
    ? `${workspace.selectedRepository.value.customer_order_item_id}:${workspace.selectedRepository.value.flow_node_id}`
    : null)
  const selectedGroup = computed(() => assembly.groups.value.find(
    group => group.key === selectedGroupKey.value,
  ))

  async function loadDetails() {
    await workOrderList.load()
  }

  async function reloadWorkspace() {
    await workspace.loadRepositories()
    await loadDetails()
  }

  function selectGroup(group: AssemblyGroup) {
    const firstItem = group.items[0]
    if (!firstItem) return
    workspace.selectRepository(firstItem)
    workOrderList.reset()
    void loadDetails()
  }

  function openGroup(group: AssemblyGroup) {
    const firstItem = group.items[0]
    if (!firstItem) return
    selectGroup(group)
    assembly.selectGroup(group)
    const maximum = group.capacity
    if (maximum < 1) {
      ElMessage.warning('所选物料的可装配数量不足')
      return
    }
    activeRepository.value = {
      ...firstItem,
      quantity: maximum,
      available_quantity: maximum,
    }
    dialogVisible.value = true
  }

  async function saveWorkOrder(payload: { quantity: number; workerId: number | null }) {
    submitting.value = true
    try {
      await createAssemblyWorkOrder(
        assembly.selectedIds.value,
        payload.quantity,
        payload.workerId,
      )
      dialogVisible.value = false
      assembly.clear()
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
    assembly.clear()
    const refreshRequest = workspace.refresh()
    await loadDetails()
    await refreshRequest
  }

  async function changeRepositoryPage(page: number) {
    workOrderList.reset()
    assembly.clear()
    const pageRequest = workspace.changePage(page)
    await loadDetails()
    await pageRequest
  }

  async function applyFilters(filters: RepositoryFilters) {
    workOrderList.reset()
    assembly.clear()
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
    assembly,
    changeRepositoryPage,
    dialogVisible,
    load,
    loadDetails,
    openGroup,
    refresh,
    saveWorkOrder,
    selectGroup,
    selectedGroup,
    selectedGroupKey,
    submitting,
    workOrderActions: useAssemblyWorkOrderActions(reloadWorkspace),
    workOrderList,
    workspace,
  }
}
