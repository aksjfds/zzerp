import { ref } from 'vue'
import { ElMessage } from 'element-plus'
import { getApiErrorDetail } from '@/api/request'
import { queryDepartmentWorkers } from '../api/departmentRepositories'
import { inspectQcBatch, queryPendingQcBatches } from '../api/qc'
import type {
  PendingQcBatch,
  QcInspectionPayload,
  WorkerItem,
} from '../domain/types'

export function useQcDepartment() {
  const batches = ref<PendingQcBatch[]>([])
  const workers = ref<WorkerItem[]>([])
  const activeBatch = ref<PendingQcBatch>()
  const loading = ref(false)
  const page = ref(1)
  const total = ref(0)
  const pageSize = 50
  const dialogVisible = ref(false)
  const submitting = ref(false)
  let loadSequence = 0

  async function loadBatches() {
    const sequence = ++loadSequence
    const requestedPage = page.value
    batches.value = []
    total.value = 0
    loading.value = true
    try {
      let result = await queryPendingQcBatches(requestedPage, pageSize)
      if (sequence !== loadSequence) return
      const lastPage = Math.max(1, Math.ceil(result.total / pageSize))
      if (requestedPage > lastPage) {
        page.value = lastPage
        result = await queryPendingQcBatches(lastPage, pageSize)
        if (sequence !== loadSequence) return
      }
      batches.value = result.items
      total.value = result.total
    } catch {
      if (sequence === loadSequence) ElMessage.warning('待检批次加载失败')
    } finally {
      if (sequence === loadSequence) loading.value = false
    }
  }

  async function loadWorkers() {
    try {
      workers.value = await queryDepartmentWorkers('qc')
    } catch {
      ElMessage.warning('QC 工人列表加载失败')
    }
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
      activeBatch.value = undefined
      await loadBatches()
      ElMessage.success('QC 结果已录入')
    } catch (error) {
      ElMessage.error(getApiErrorDetail(error)?.message || 'QC 结果录入失败')
    } finally {
      submitting.value = false
    }
  }

  async function refresh() {
    page.value = 1
    await Promise.all([loadBatches(), loadWorkers()])
  }

  async function changePage(nextPage: number) {
    page.value = nextPage
    await loadBatches()
  }

  async function load() {
    await Promise.all([loadBatches(), loadWorkers()])
  }

  return {
    activeBatch,
    batches,
    changePage,
    dialogVisible,
    load,
    loadBatches,
    loading,
    openInspection,
    page,
    pageSize,
    refresh,
    saveInspection,
    submitting,
    total,
    workers,
  }
}
