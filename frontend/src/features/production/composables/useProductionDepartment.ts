import { computed, ref } from 'vue'
import { ElMessage } from 'element-plus'
import { getApiErrorDetail } from '@/api/request'
import {
  dispatchProcedureStageStock,
  queryProductionSubstepCards,
} from '../api/departmentRepositories'
import { createWorkOrder } from '../api/workOrders'
import type {
  RepositoryFilters,
  RepositoryItem,
  SubstepCard,
  WorkOrderQueryScope,
} from '../domain/types'
import { useDepartmentWorkspace } from './useDepartmentWorkspace'
import { useWorkOrderActions, useWorkOrderList } from './useWorkOrders'

export function useProductionDepartment(
  departmentCode: string,
  mode: 'production' | 'purchase' = 'production',
) {
  const workspace = useDepartmentWorkspace(departmentCode, true)
  const workOrderScope = ref<WorkOrderQueryScope | null>(null)
  const workOrderList = useWorkOrderList(
    departmentCode,
    workspace.selectedProductionItemId,
    workspace.pageSize,
    mode === 'production' ? workOrderScope : undefined,
  )
  const activeRepository = ref<RepositoryItem>()
  const activeSubstepSource = ref<SubstepCard>()
  const dialogVisible = ref(false)
  const dispatchDialogVisible = ref(false)
  const submitting = ref(false)
  const dispatchSubmitting = ref(false)
  const substepItems = ref<SubstepCard[]>([])
  const substepLoading = ref(false)
  const selectedSubstepKey = ref<string | null>(null)
  const selectedSubstep = computed(() => substepItems.value.find(
    item => item.card_key === selectedSubstepKey.value,
  ))
  let substepSequence = 0

  async function loadDetails() {
    await workOrderList.load()
  }

  function clearSubstepState() {
    substepSequence += 1
    substepItems.value = []
    selectedSubstepKey.value = null
    workOrderScope.value = null
    activeSubstepSource.value = undefined
    substepLoading.value = false
  }

  function applySubstepSelection(item: SubstepCard) {
    const repository = workspace.selectedRepository.value
    selectedSubstepKey.value = item.card_key
    workOrderScope.value = item.substep_id === null || !repository
      ? null
      : {
          flowNodeId: repository.flow_node_id,
          sourceFlowNodeId: repository.source_flow_node_id,
          substepId: item.substep_id,
        }
  }

  async function loadSubsteps(item = workspace.selectedRepository.value) {
    const sequence = ++substepSequence
    substepItems.value = []
    if (mode !== 'production' || !item) {
      substepLoading.value = false
      return
    }
    substepLoading.value = true
    try {
      const result = await queryProductionSubstepCards(
        departmentCode,
        item.production_item_id,
        item.flow_node_id,
        item.source_flow_node_id,
      )
      if (
        sequence !== substepSequence
        || workspace.selectedCardKey.value !== item.card_key
      ) return
      substepItems.value = result
      const current = result.find(card => card.card_key === selectedSubstepKey.value)
      if (current) {
        applySubstepSelection(current)
      } else {
        selectedSubstepKey.value = null
        workOrderScope.value = null
        workOrderList.reset()
      }
    } catch {
      if (sequence === substepSequence) {
        selectedSubstepKey.value = null
        workOrderScope.value = null
        workOrderList.reset()
        ElMessage.warning('细分状态加载失败')
      }
    } finally {
      if (sequence === substepSequence) substepLoading.value = false
    }
  }

  async function reloadWorkspace() {
    await workspace.loadRepositories()
    if (mode === 'production') {
      if (!workspace.selectedRepository.value) {
        clearSubstepState()
        workOrderList.reset()
        return
      }
      await loadSubsteps()
    }
    await loadDetails()
  }

  function selectRepository(item: RepositoryItem) {
    workspace.selectRepository(item)
    clearSubstepState()
    workOrderList.reset()
    if (mode === 'production') void loadSubsteps(item)
    else void loadDetails()
  }

  function selectSubstep(item: SubstepCard) {
    applySubstepSelection(item)
    workOrderList.reset()
    void loadDetails()
  }

  function openWorkOrder(item: RepositoryItem) {
    selectRepository(item)
    activeRepository.value = item
    activeSubstepSource.value = undefined
    dialogVisible.value = true
  }

  function openSubstepWorkOrder(item: SubstepCard) {
    const repository = workspace.selectedRepository.value
    if (!repository) return
    if ((item.repository_id === null) === (item.stage_stock_id === null)) {
      ElMessage.warning('当前细分没有可用的开单来源')
      return
    }
    applySubstepSelection(item)
    workOrderList.reset()
    void loadDetails()
    activeRepository.value = repository
    activeSubstepSource.value = item
    dialogVisible.value = true
  }

  async function saveWorkOrder(payload: {
    quantity: number
    workerId: number | null
    substepName: string | null
  }) {
    const repository = activeRepository.value
    const substepSource = activeSubstepSource.value
    if (!repository || payload.substepName === null) return
    const repositoryId = mode === 'production'
      ? substepSource?.repository_id ?? null
      : repository.repository_id
    const stageStockId = mode === 'production'
      ? substepSource?.stage_stock_id ?? null
      : repository.stage_stock_id
    if ((repositoryId === null) === (stageStockId === null)) return
    submitting.value = true
    try {
      const created = await createWorkOrder(
        repositoryId,
        stageStockId,
        payload.substepName,
        payload.quantity,
        payload.workerId,
      )
      dialogVisible.value = false
      await reloadWorkspace()
      if (mode === 'production' && created.substep_id !== null) {
        const createdSubstep = substepItems.value.find(
          item => item.substep_id === created.substep_id,
        )
        if (createdSubstep) {
          applySubstepSelection(createdSubstep)
          workOrderList.reset()
          await loadDetails()
        }
      }
      ElMessage.success(mode === 'purchase' ? '外购入库单已创建' : '工单已创建')
    } catch (error) {
      ElMessage.error(getApiErrorDetail(error)?.message || '创建工单失败')
    } finally {
      submitting.value = false
    }
  }

  async function openDispatch(item: RepositoryItem) {
    workspace.selectRepository(item)
    clearSubstepState()
    workOrderList.reset()
    activeRepository.value = item
    await loadSubsteps(item)
    if (workspace.selectedCardKey.value !== item.card_key) return
    const hasDispatchableStock = substepItems.value.some(
      substep => substep.stage_stock_id !== null && substep.available_quantity > 0,
    )
    if (!hasDispatchableStock) {
      ElMessage.warning('当前配件暂无可出货的已完细分')
      return
    }
    dispatchDialogVisible.value = true
  }

  async function saveDispatch(payload: { stageStockId: number; quantity: number }) {
    dispatchSubmitting.value = true
    try {
      await dispatchProcedureStageStock(payload.stageStockId, payload.quantity)
      dispatchDialogVisible.value = false
      await reloadWorkspace()
      ElMessage.success('出货完成')
    } catch (error) {
      ElMessage.error(getApiErrorDetail(error)?.message || '出货失败')
    } finally {
      dispatchSubmitting.value = false
    }
  }

  async function refresh() {
    clearSubstepState()
    workOrderList.reset()
    await workspace.refresh()
  }

  async function changeRepositoryPage(page: number) {
    clearSubstepState()
    workOrderList.reset()
    await workspace.changePage(page)
  }

  async function applyFilters(filters: RepositoryFilters) {
    clearSubstepState()
    workOrderList.reset()
    await workspace.search(filters)
  }

  async function load() {
    await workspace.load()
  }

  return {
    activeRepository,
    activeSubstepSource,
    applyFilters,
    changeRepositoryPage,
    dialogVisible,
    dispatchDialogVisible,
    dispatchSubmitting,
    load,
    loadDetails,
    openDispatch,
    openSubstepWorkOrder,
    openWorkOrder,
    refresh,
    saveDispatch,
    saveWorkOrder,
    selectRepository,
    selectedSubstep,
    selectedSubstepKey,
    selectSubstep,
    substepItems,
    substepLoading,
    submitting,
    workOrderActions: useWorkOrderActions(reloadWorkspace, mode),
    workOrderList,
    workspace,
  }
}
