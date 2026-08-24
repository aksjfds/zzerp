import { computed, ref } from 'vue'
import { ElMessage } from 'element-plus'
import { getApiErrorDetail } from '@/api/request'
import { createAssemblyWorkOrder, createWorkOrder } from '../api/workOrders'
import type { RepositoryFilters, RepositoryItem, WorkOrderQueryScope } from '../domain/types'
import { assemblyGroupKey, useAssemblyGroups, type AssemblyGroup } from './useAssemblyGroups'
import { useDepartmentWorkspace } from './useDepartmentWorkspace'
import { useWorkOrderList } from './useWorkOrders'
import { useAssemblyWorkOrderActions } from './useAssemblyWorkOrderActions'
import { useProductionWorkOrderActions } from './useProductionWorkOrderActions'

export function useAssemblyDepartment() {
  const workspace = useDepartmentWorkspace('assembly', true, true)
  const assembly = useAssemblyGroups(workspace.items)
  const workOrderScope = computed<WorkOrderQueryScope | null>(() => {
    const item = workspace.selectedRepository.value
    return item
      ? {
          flowNodeId: item.flow_node_id,
          sourceFlowNodeId: item.node_type === 'assembly' ? '' : item.source_flow_node_id,
        }
      : null
  })
  const workOrderList = useWorkOrderList(
    'assembly',
    workspace.selectedProductionItemId,
    workspace.pageSize,
    workOrderScope,
  )
  const activeRepository = ref<RepositoryItem>()
  const dialogVisible = ref(false)
  const processDialogVisible = ref(false)
  const submitting = ref(false)
  const processItems = computed(() => workspace.items.value.filter(
    item => item.node_type !== 'assembly',
  ))
  const selectedMode = computed(() => (
    workspace.selectedRepository.value?.node_type === 'assembly'
      ? 'assembly'
      : 'production'
  ))
  const selectedGroupKey = computed(() => workspace.selectedRepository.value
    ? assemblyGroupKey(workspace.selectedRepository.value)
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

  function selectProcess(item: RepositoryItem) {
    workspace.selectRepository(item)
    workOrderList.reset()
    void loadDetails()
  }

  async function openProcess(item: RepositoryItem) {
    const sameItem = workspace.selectedCardKey.value === item.card_key
    workspace.selectRepository(item)
    if (!sameItem) workOrderList.reset()
    activeRepository.value = item
    if (!item.repository_id || item.available_quantity < 1) {
      ElMessage.warning('当前物料没有可用的开单来源')
      return
    }
    await loadDetails()
    processDialogVisible.value = true
  }

  function openGroup(group: AssemblyGroup) {
    const firstItem = group.items[0]
    if (!firstItem) return
    selectGroup(group)
    const maximum = group.capacity
    if (maximum < 1) {
      ElMessage.warning('所选物料的可生产数量不足')
      return
    }
    activeRepository.value = {
      ...firstItem,
      part_no: group.name,
      part_name: group.name,
      quantity: maximum,
      available_quantity: maximum,
    }
    dialogVisible.value = true
  }

  async function saveWorkOrder(payload: {
    quantity: number
    materials: Array<{ repository_id: number; quantity: number }>
    procedureId: number | null
    procedureName: string | null
    workerId: number | null
    remark: string
  }) {
    submitting.value = true
    try {
      await createAssemblyWorkOrder(
        payload.materials,
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

  async function saveProcessWorkOrder(payload: {
    repositoryId: number
    procedureId: number | null
    procedureName: string | null
    quantity: number
    workerId: number | null
    remark: string
  }) {
    if (!activeRepository.value) return
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
      processDialogVisible.value = false
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
    assembly,
    changeRepositoryPage,
    dialogVisible,
    load,
    loadDetails,
    openGroup,
    openProcess,
    processDialogVisible,
    processItems,
    refresh,
    saveWorkOrder,
    saveProcessWorkOrder,
    selectGroup,
    selectProcess,
    selectedMode,
    selectedGroup,
    selectedGroupKey,
    submitting,
    assemblyWorkOrderActions: useAssemblyWorkOrderActions(reloadWorkspace),
    productionWorkOrderActions: useProductionWorkOrderActions(reloadWorkspace),
    workOrderList,
    workspace,
  }
}
