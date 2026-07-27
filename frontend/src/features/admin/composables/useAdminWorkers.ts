import { computed, ref, watch } from 'vue'
import { ElMessage } from 'element-plus'
import {
  queryAdminWorkerHistory,
  queryAdminWorkerOverview,
  queryAdminWorkerPay,
} from '../api/admin'
import type {
  AdminWorker,
  AdminWorkerDepartment,
  AdminWorkerHistoryItem,
  AdminWorkerPaySummary,
} from '../domain/types'

function currentLocalMonth() {
  const now = new Date()
  return `${now.getFullYear()}-${String(now.getMonth() + 1).padStart(2, '0')}`
}

export function useAdminWorkers() {
  const departments = ref<AdminWorkerDepartment[]>([])
  const workersLoading = ref(false)
  const historyLoading = ref(false)
  const payLoading = ref(false)
  const selectedWorker = ref<AdminWorker>()
  const selectedMonth = ref(currentLocalMonth())
  const workerKeyword = ref('')
  const departmentFilter = ref<number | ''>('')
  const history = ref<AdminWorkerHistoryItem[]>([])
  const paySummary = ref<AdminWorkerPaySummary>()

  const allWorkers = computed(() => departments.value.flatMap(item => item.workers))
  const filteredWorkers = computed(() => {
    const keyword = workerKeyword.value.trim().toLowerCase()
    return allWorkers.value.filter((worker) => (
      (!keyword || worker.worker_name.toLowerCase().includes(keyword))
      && (!departmentFilter.value || worker.department_id === departmentFilter.value)
    ))
  })
  const selectedWorkerTitle = computed(() => selectedWorker.value
    ? `${selectedWorker.value.department_name} / ${selectedWorker.value.worker_name}`
    : '请选择工人')

  async function loadHistory() {
    if (!selectedWorker.value) {
      history.value = []
      return
    }
    historyLoading.value = true
    try {
      history.value = await queryAdminWorkerHistory(
        selectedWorker.value.id,
        selectedMonth.value,
      )
    } catch {
      ElMessage.error('工人工作情况加载失败')
    } finally {
      historyLoading.value = false
    }
  }

  async function loadPay() {
    if (!selectedWorker.value) {
      paySummary.value = undefined
      return
    }
    payLoading.value = true
    try {
      paySummary.value = await queryAdminWorkerPay(
        selectedWorker.value.id,
        selectedMonth.value,
      )
    } catch {
      ElMessage.error('工人工资加载失败')
    } finally {
      payLoading.value = false
    }
  }

  async function loadWorkerDetails() {
    await Promise.all([loadHistory(), loadPay()])
  }

  async function loadWorkers() {
    workersLoading.value = true
    try {
      departments.value = await queryAdminWorkerOverview()
      if (!selectedWorker.value) selectedWorker.value = filteredWorkers.value[0]
      await loadWorkerDetails()
    } catch {
      ElMessage.error('工人总览加载失败')
    } finally {
      workersLoading.value = false
    }
  }

  async function selectWorker(worker: AdminWorker) {
    selectedWorker.value = worker
    await loadWorkerDetails()
  }

  watch(filteredWorkers, async (workers) => {
    if (!selectedWorker.value || !workers.some(worker => worker.id === selectedWorker.value?.id)) {
      selectedWorker.value = workers[0]
      await loadWorkerDetails()
    }
  })

  return {
    departmentFilter,
    departments,
    filteredWorkers,
    history,
    historyLoading,
    loadHistory,
    loadWorkerDetails,
    loadWorkers,
    selectedMonth,
    selectedWorker,
    selectedWorkerTitle,
    selectWorker,
    workerKeyword,
    workersLoading,
    payLoading,
    paySummary,
  }
}
