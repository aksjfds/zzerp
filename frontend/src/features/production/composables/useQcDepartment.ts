import { ref } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { getApiErrorDetail } from '@/api/request'
import { queryDepartmentWorkers } from '../api/departmentRepositories'
import { dispatchQcBatch, inspectQcBatch, queryPendingQcBatches } from '../api/qc'
import type {
  PendingQcBatch,
  QcInspectionPayload,
  WorkerItem,
} from '../domain/types'

export function useQcDepartment() {
  const activeView = ref<'active' | 'history'>('active')
  const batches = ref<PendingQcBatch[]>([])
  const workers = ref<WorkerItem[]>([])
  const activeBatch = ref<PendingQcBatch>()
  const loading = ref(false)
  const page = ref(1)
  const total = ref(0)
  const pageSize = 50
  const dialogVisible = ref(false)
  const submitting = ref(false)
  const keyword = ref('')
  let loadSequence = 0

  async function loadBatches() {
    const sequence = ++loadSequence
    const requestedPage = page.value
    loading.value = true
    try {
      let result = await queryPendingQcBatches(
        requestedPage,
        pageSize,
        undefined,
        activeView.value === 'history',
        keyword.value,
      )
      if (sequence !== loadSequence) return
      const lastPage = Math.max(1, Math.ceil(result.total / pageSize))
      if (requestedPage > lastPage) {
        page.value = lastPage
        result = await queryPendingQcBatches(
          lastPage,
          pageSize,
          undefined,
          activeView.value === 'history',
          keyword.value,
        )
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

  async function dispatch(batch: PendingQcBatch) {
    try {
      const { value } = await ElMessageBox.prompt(
        `请输入放行到${batch.target_node_label || '下一节点'}的数量`,
        `工单 ${batch.work_order_no} QC 放行`,
        {
          inputValue: String(batch.dispatchable_quantity),
          inputPattern: /^[1-9]\d*$/,
          inputErrorMessage: '请输入正整数',
        },
      )
      const quantity = Number(value)
      if (quantity < 1 || quantity > batch.dispatchable_quantity) {
        ElMessage.warning('放行数量不能超过合格待放行数量')
        return
      }
      submitting.value = true
      await dispatchQcBatch(batch.id, quantity)
      await loadBatches()
      ElMessage.success(`已向${batch.target_node_label || '下一节点'}放行 ${quantity} 件`)
    } catch (error) {
      if (error !== 'cancel' && error !== 'close') {
        ElMessage.error(getApiErrorDetail(error)?.message || 'QC放行失败')
      }
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

  async function changeView(view: 'active' | 'history') {
    activeView.value = view
    page.value = 1
    await loadBatches()
  }

  async function search(value: string) {
    keyword.value = value.trim()
    page.value = 1
    await loadBatches()
  }

  async function load() {
    await Promise.all([loadBatches(), loadWorkers()])
  }

  return {
    activeView,
    activeBatch,
    batches,
    changePage,
    changeView,
    dialogVisible,
    dispatch,
    load,
    loadBatches,
    loading,
    openInspection,
    page,
    pageSize,
    refresh,
    saveInspection,
    search,
    submitting,
    total,
    workers,
  }
}
