import { ref } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { getApiErrorDetail } from '@/api/request'
import {
  decideQcDestination,
  inspectQcBatch,
  queryQcInspectionBatches,
  undoQcInspection,
} from '../api/qc'
import type {
  QcBatchRow,
  QcInspectionBatchRow,
  QcDestination,
  QcInspectionPayload,
} from '../domain/types'

export function useQcDepartment() {
  const activeView = ref<'active' | 'history'>('active')
  const batches = ref<QcInspectionBatchRow[]>([])
  const activeBatch = ref<QcBatchRow>()
  const loading = ref(false)
  const page = ref(1)
  const total = ref(0)
  const pageSize = 50
  const dialogVisible = ref(false)
  const submitting = ref(false)
  const decidingBatchId = ref<number | null>(null)
  const undoingBatchId = ref<number | null>(null)
  const keyword = ref('')
  let loadSequence = 0

  async function loadInspectionBatches() {
    const sequence = ++loadSequence
    const requestedPage = page.value
    loading.value = true
    try {
      let result = await queryQcInspectionBatches(
        requestedPage,
        pageSize,
        activeView.value === 'history',
        keyword.value,
      )
      if (sequence !== loadSequence) return
      const lastPage = Math.max(1, Math.ceil(result.total / pageSize))
      if (requestedPage > lastPage) {
        page.value = lastPage
        result = await queryQcInspectionBatches(
          lastPage,
          pageSize,
          activeView.value === 'history',
          keyword.value,
        )
        if (sequence !== loadSequence) return
      }
      batches.value = result.items
      total.value = result.total
    } catch {
      if (sequence === loadSequence) ElMessage.warning('QC 质检列表加载失败')
    } finally {
      if (sequence === loadSequence) loading.value = false
    }
  }

  function openInspection(batch: QcBatchRow) {
    activeBatch.value = batch
    dialogVisible.value = true
  }

  async function saveInspection(payload: QcInspectionPayload) {
    if (!activeBatch.value) return
    submitting.value = true
    try {
      await inspectQcBatch(activeBatch.value.id, payload)
      dialogVisible.value = false
      activeBatch.value = undefined
      await loadInspectionBatches()
      ElMessage.success('QC 结果已录入')
    } catch (error) {
      ElMessage.error(getApiErrorDetail(error)?.message || 'QC 结果录入失败')
    } finally {
      submitting.value = false
    }
  }

  async function decideDestination(batch: QcBatchRow, destination: QcDestination) {
    const labels: Record<QcDestination, string> = {
      return: '返回当前车间',
      release: '放行下一节点',
      inventory: '存入仓库',
    }
    try {
      await ElMessageBox.confirm(
        `确认将 ${batch.qualified_quantity || 0} 件合格品${labels[destination]}？确认后不能更改。`,
        '确认合格品去向',
        { type: 'warning', confirmButtonText: '确认', cancelButtonText: '取消' },
      )
    } catch {
      return
    }
    decidingBatchId.value = batch.id
    try {
      await decideQcDestination(batch.id, destination)
      await loadInspectionBatches()
      ElMessage.success('合格品去向已确认')
    } catch (error) {
      ElMessage.error(getApiErrorDetail(error)?.message || '合格品去向确认失败')
    } finally {
      decidingBatchId.value = null
    }
  }

  async function undoInspection(batch: QcBatchRow) {
    try {
      await ElMessageBox.confirm(
        '确认撤回本次 QC 结果？撤回后该批次将恢复为待质检。',
        '撤回质检',
        { type: 'warning', confirmButtonText: '确认撤回', cancelButtonText: '取消' },
      )
    } catch {
      return
    }
    undoingBatchId.value = batch.id
    try {
      await undoQcInspection(batch.id)
      await loadInspectionBatches()
      ElMessage.success('QC 结果已撤回')
    } catch (error) {
      ElMessage.error(getApiErrorDetail(error)?.message || 'QC 结果撤回失败')
    } finally {
      undoingBatchId.value = null
    }
  }

  async function refresh() {
    page.value = 1
    await loadInspectionBatches()
  }

  async function changePage(nextPage: number) {
    page.value = nextPage
    await loadInspectionBatches()
  }

  async function changeView(view: 'active' | 'history') {
    activeView.value = view
    page.value = 1
    await loadInspectionBatches()
  }

  async function search(value: string) {
    keyword.value = value.trim()
    page.value = 1
    await loadInspectionBatches()
  }

  async function load() {
    await loadInspectionBatches()
  }

  return {
    activeView,
    activeBatch,
    changePage,
    changeView,
    decideDestination,
    decidingBatchId,
    dialogVisible,
    load,
    loading,
    batches,
    openInspection,
    page,
    pageSize,
    refresh,
    saveInspection,
    search,
    submitting,
    total,
    undoInspection,
    undoingBatchId,
  }
}
