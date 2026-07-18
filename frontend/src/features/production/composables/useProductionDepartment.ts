import { computed, ref } from 'vue'
import { ElMessage } from 'element-plus'
import { getApiErrorDetail } from '@/api/request'
import {
  dispatchProcedureTagStock,
  queryProductionTagCards,
} from '../api/departmentRepositories'
import { createWorkOrder } from '../api/workOrders'
import type {
  RepositoryFilters,
  RepositoryItem,
  TagCard,
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
  const dialogVisible = ref(false)
  const dispatchDialogVisible = ref(false)
  const submitting = ref(false)
  const dispatchSubmitting = ref(false)
  const tagItems = ref<TagCard[]>([])
  const tagLoading = ref(false)
  const selectedTagKey = ref<string | null>(null)
  const selectedTag = computed(() => tagItems.value.find(
    item => item.card_key === selectedTagKey.value,
  ))
  let tagSequence = 0

  async function loadDetails() {
    await workOrderList.load()
  }

  function clearTagState() {
    tagSequence += 1
    tagItems.value = []
    selectedTagKey.value = null
    workOrderScope.value = null
    tagLoading.value = false
  }

  function applyTagSelection(item: TagCard) {
    const repository = workspace.selectedRepository.value
    selectedTagKey.value = item.card_key
    workOrderScope.value = item.tag_set_id === null || !repository
      ? null
      : {
          flowNodeId: repository.flow_node_id,
          sourceFlowNodeId: repository.source_flow_node_id,
          targetTagSetId: item.tag_set_id,
        }
  }

  async function loadTags(item = workspace.selectedRepository.value) {
    const sequence = ++tagSequence
    tagItems.value = []
    if (mode !== 'production' || !item) {
      tagLoading.value = false
      return
    }
    tagLoading.value = true
    try {
      const result = await queryProductionTagCards(
        departmentCode,
        item.production_item_id,
        item.flow_node_id,
        item.source_flow_node_id,
      )
      if (
        sequence !== tagSequence
        || workspace.selectedCardKey.value !== item.card_key
      ) return
      tagItems.value = result
      const current = result.find(card => card.card_key === selectedTagKey.value)
      if (current) {
        applyTagSelection(current)
      } else {
        selectedTagKey.value = null
        workOrderScope.value = null
        workOrderList.reset()
      }
    } catch {
      if (sequence === tagSequence) {
        selectedTagKey.value = null
        workOrderScope.value = null
        workOrderList.reset()
        ElMessage.warning('标记组合加载失败')
      }
    } finally {
      if (sequence === tagSequence) tagLoading.value = false
    }
  }

  async function reloadWorkspace() {
    await workspace.loadRepositories()
    if (mode === 'production') {
      if (!workspace.selectedRepository.value) {
        clearTagState()
        workOrderList.reset()
        return
      }
      await loadTags()
    }
    await loadDetails()
  }

  function selectRepository(item: RepositoryItem) {
    workspace.selectRepository(item)
    clearTagState()
    workOrderList.reset()
    if (mode === 'production') void loadTags(item)
    else void loadDetails()
  }

  function selectTag(item: TagCard) {
    applyTagSelection(item)
    workOrderList.reset()
    void loadDetails()
  }

  function openTagWorkOrder(item: TagCard) {
    const repository = workspace.selectedRepository.value
    if (!repository) return
    if (
      item.available_quantity < 1
      || ((item.repository_id === null) === (item.tag_stock_id === null))
    ) {
      ElMessage.warning('当前标记组合没有可用的开单数量')
      return
    }
    activeRepository.value = repository
    applyTagSelection(item)
    workOrderList.reset()
    void loadDetails()
    dialogVisible.value = true
  }

  async function openWorkOrder(item: RepositoryItem) {
    const preferredSourceKey = workspace.selectedCardKey.value === item.card_key
      ? selectedTagKey.value
      : null
    workspace.selectRepository(item)
    clearTagState()
    selectedTagKey.value = preferredSourceKey
    workOrderList.reset()
    activeRepository.value = item
    if (mode === 'production') {
      await loadTags(item)
      if (workspace.selectedCardKey.value !== item.card_key) return
      if (!tagItems.value.some(source => (
        source.available_quantity > 0
        && ((source.repository_id === null) !== (source.tag_stock_id === null))
      ))) {
        ElMessage.warning('当前配件没有可用的开单来源')
        return
      }
    }
    dialogVisible.value = true
  }

  async function saveWorkOrder(payload: {
    repositoryId: number | null
    tagStockId: number | null
    quantity: number
    workerId: number | null
    tagNames: string[]
  }) {
    if (!activeRepository.value) return
    if ((payload.repositoryId === null) === (payload.tagStockId === null)) return
    if (mode === 'production' && payload.tagNames.length === 0) return
    submitting.value = true
    try {
      const created = await createWorkOrder(
        payload.repositoryId,
        payload.tagStockId,
        payload.tagNames,
        payload.quantity,
        payload.workerId,
      )
      dialogVisible.value = false
      await reloadWorkspace()
      if (mode === 'production' && created.target_tag_set_id !== null) {
        const target = tagItems.value.find(
          item => item.tag_set_id === created.target_tag_set_id,
        )
        if (target) {
          applyTagSelection(target)
          workOrderList.reset()
          await loadDetails()
        }
      }
      ElMessage.success(mode === 'purchase' ? '外购入库单已创建' : '标记工单已创建')
    } catch (error) {
      ElMessage.error(getApiErrorDetail(error)?.message || '创建工单失败')
    } finally {
      submitting.value = false
    }
  }

  async function openDispatch(item: RepositoryItem) {
    workspace.selectRepository(item)
    clearTagState()
    workOrderList.reset()
    activeRepository.value = item
    await loadTags(item)
    if (workspace.selectedCardKey.value !== item.card_key) return
    if (!tagItems.value.some(
      source => source.tag_stock_id !== null && source.available_quantity > 0,
    )) {
      ElMessage.warning('当前配件暂无可出货的已完成标记组合')
      return
    }
    dispatchDialogVisible.value = true
  }

  async function saveDispatch(payload: { tagStockId: number; quantity: number }) {
    dispatchSubmitting.value = true
    try {
      await dispatchProcedureTagStock(payload.tagStockId, payload.quantity)
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
    clearTagState()
    workOrderList.reset()
    await workspace.refresh()
  }

  async function changeRepositoryPage(page: number) {
    clearTagState()
    workOrderList.reset()
    await workspace.changePage(page)
  }

  async function applyFilters(filters: RepositoryFilters) {
    clearTagState()
    workOrderList.reset()
    await workspace.search(filters)
  }

  async function load() {
    await workspace.load()
  }

  return {
    activeRepository,
    applyFilters,
    changeRepositoryPage,
    dialogVisible,
    dispatchDialogVisible,
    dispatchSubmitting,
    load,
    loadDetails,
    openDispatch,
    openTagWorkOrder,
    openWorkOrder,
    refresh,
    saveDispatch,
    saveWorkOrder,
    selectRepository,
    selectedTag,
    selectedTagKey,
    selectTag,
    tagItems,
    tagLoading,
    submitting,
    workOrderActions: useWorkOrderActions(reloadWorkspace, mode),
    workOrderList,
    workspace,
  }
}
