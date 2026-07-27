import { computed, ref, watch } from 'vue'
import { ElMessage } from 'element-plus'
import { getApiErrorDetail } from '@/api/request'
import type {
  DepartmentWorkerOverview,
  WorkerHistoryItem,
  WorkerOverviewItem,
  WorkerPaySummary,
} from '@/features/workers/domain/types'
import {
  createDepartmentWorker,
  queryDepartmentWorkerHistory,
  queryDepartmentWorkerOverview,
  queryDepartmentWorkerPay,
} from '../api/departmentWorkers'

function currentLocalMonth() {
  const now = new Date()
  return `${now.getFullYear()}-${String(now.getMonth() + 1).padStart(2, '0')}`
}

export function useDepartmentWorkers(departmentCode: string) {
  const overview = ref<DepartmentWorkerOverview>()
  const workersLoading = ref(false)
  const historyLoading = ref(false)
  const payLoading = ref(false)
  const submitting = ref(false)
  const dialogVisible = ref(false)
  const selectedWorker = ref<WorkerOverviewItem>()
  const selectedMonth = ref(currentLocalMonth())
  const workerKeyword = ref('')
  const departmentFilter = ref<number | ''>('')
  const history = ref<WorkerHistoryItem[]>([])
  const paySummary = ref<WorkerPaySummary>()

  const departments = computed(() => overview.value ? [overview.value] : [])
  const filteredWorkers = computed(() => {
    const keyword = workerKeyword.value.trim().toLowerCase()
    return (overview.value?.workers || []).filter(
      worker => !keyword || worker.worker_name.toLowerCase().includes(keyword),
    )
  })
  const selectedWorkerTitle = computed(() => selectedWorker.value
    ? `${selectedWorker.value.workshop_name || '部门直属'} / ${selectedWorker.value.worker_name}`
    : '请选择工人')

  async function loadHistory() {
    if (!selectedWorker.value) {
      history.value = []
      return
    }
    historyLoading.value = true
    try {
      history.value = await queryDepartmentWorkerHistory(
        departmentCode,
        selectedWorker.value.id,
        selectedMonth.value,
      )
    } catch (error) {
      ElMessage.error(getApiErrorDetail(error)?.message || '工人工作情况加载失败')
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
      paySummary.value = await queryDepartmentWorkerPay(
        departmentCode,
        selectedWorker.value.id,
        selectedMonth.value,
      )
    } catch (error) {
      ElMessage.error(getApiErrorDetail(error)?.message || '工人工资加载失败')
    } finally {
      payLoading.value = false
    }
  }

  async function loadWorkerDetails() {
    await Promise.all([loadHistory(), loadPay()])
  }

  async function loadWorkers(preferredWorkerId?: number) {
    workersLoading.value = true
    try {
      overview.value = await queryDepartmentWorkerOverview(departmentCode)
      departmentFilter.value = overview.value.department_id
      selectedWorker.value = overview.value.workers.find(
        worker => worker.id === (preferredWorkerId ?? selectedWorker.value?.id),
      ) || overview.value.workers[0]
      await loadWorkerDetails()
    } catch (error) {
      ElMessage.error(getApiErrorDetail(error)?.message || '工人总览加载失败')
    } finally {
      workersLoading.value = false
    }
  }

  async function selectWorker(worker: WorkerOverviewItem) {
    selectedWorker.value = worker
    await loadWorkerDetails()
  }

  async function saveWorker(payload: { workerName: string; workshopId: number | null }) {
    submitting.value = true
    try {
      const worker = await createDepartmentWorker(
        departmentCode,
        payload.workerName,
        payload.workshopId,
      )
      dialogVisible.value = false
      await loadWorkers(worker.id)
      ElMessage.success('工人录入成功')
    } catch (error) {
      ElMessage.error(getApiErrorDetail(error)?.message || '工人录入失败')
    } finally {
      submitting.value = false
    }
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
    dialogVisible,
    filteredWorkers,
    history,
    historyLoading,
    loadHistory,
    loadWorkerDetails,
    loadWorkers,
    overview,
    saveWorker,
    selectedMonth,
    selectedWorker,
    selectedWorkerTitle,
    selectWorker,
    submitting,
    workerKeyword,
    workersLoading,
    payLoading,
    paySummary,
  }
}
