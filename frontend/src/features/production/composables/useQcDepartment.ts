import { ref } from 'vue'
import { ElMessage } from 'element-plus'
import { getApiErrorDetail } from '@/api/request'
import { inspectQcBatch, queryPendingQcBatches } from '../api/qc'
import type {
  PendingQcBatch,
  QcInspectionPayload,
  RepositoryFilters,
  RepositoryItem,
} from '../domain/types'
import { useDepartmentWorkspace } from './useDepartmentWorkspace'

export function useQcDepartment() {
  const workspace = useDepartmentWorkspace('qc', true)
  const batches = ref<PendingQcBatch[]>([])
  const activeBatch = ref<PendingQcBatch>()
  const detailLoading = ref(false)
  const historyPage = ref(1)
  const historyTotal = ref(0)
  const dialogVisible = ref(false)
  const submitting = ref(false)
  let detailSequence = 0

  async function loadDetails() {
    const sequence = ++detailSequence
    const requestedProductionItemId = workspace.selectedProductionItemId.value
    const requestedPage = historyPage.value
    batches.value = []
    historyTotal.value = 0
    if (!requestedProductionItemId) {
      detailLoading.value = false
      return
    }
    detailLoading.value = true
    try {
      const result = await queryPendingQcBatches(
        requestedPage,
        workspace.pageSize,
        requestedProductionItemId,
      )
      if (
        sequence !== detailSequence
        || workspace.selectedProductionItemId.value !== requestedProductionItemId
        || historyPage.value !== requestedPage
      ) return
      batches.value = result.items
      historyTotal.value = result.total
    } catch {
      if (sequence === detailSequence) ElMessage.warning('关联质检记录加载失败')
    } finally {
      if (sequence === detailSequence) detailLoading.value = false
    }
  }

  async function reloadWorkspace() {
    await workspace.loadRepositories()
    await loadDetails()
  }

  function selectRepository(item: RepositoryItem) {
    workspace.selectRepository(item)
    historyPage.value = 1
    void loadDetails()
  }

  function openInspection(batch: PendingQcBatch) {
    activeBatch.value = batch
    dialogVisible.value = true
  }

  async function saveInspection(payload: QcInspectionPayload) {
    if (!activeBatch.value) return
    submitting.value = true
    try {
      await inspectQcBatch(activeBatch.value.id, payload)
      dialogVisible.value = false
      await reloadWorkspace()
      ElMessage.success('QC 结果已录入')
    } catch (error) {
      ElMessage.error(getApiErrorDetail(error)?.message || 'QC 结果录入失败')
    } finally {
      submitting.value = false
    }
  }

  async function refresh() {
    historyPage.value = 1
    const refreshRequest = workspace.refresh()
    await loadDetails()
    await refreshRequest
  }

  async function changeRepositoryPage(page: number) {
    historyPage.value = 1
    const pageRequest = workspace.changePage(page)
    await loadDetails()
    await pageRequest
  }

  async function applyFilters(filters: RepositoryFilters) {
    historyPage.value = 1
    const searchRequest = workspace.search(filters)
    await loadDetails()
    await searchRequest
  }

  async function load() {
    await workspace.load()
    await loadDetails()
  }

  return {
    activeBatch,
    applyFilters,
    batches,
    changeRepositoryPage,
    detailLoading,
    dialogVisible,
    historyPage,
    historyTotal,
    load,
    loadDetails,
    openInspection,
    refresh,
    saveInspection,
    selectRepository,
    submitting,
    workspace,
  }
}
