import { ref } from 'vue'
import { defineStore } from 'pinia'
import {
  assignQcSubmission,
  completeCleaningSubmission,
  configurePolishProcesses,
  createDepartmentWorker,
  createCleaningSubmission,
  createDirectReport,
  createWorkOrder,
  createWorkOrderSubmission,
  inspectQcSubmission,
  queryDepartmentReworkRequests,
  queryDepartmentWorkers,
  queryDepartmentWorkOrders,
  queryPendingQcSubmissions,
  queryPolishProcesses,
  queryPolishProcessPresets,
  savePolishProcessPreset,
} from '@/api/production'
import type {
  CreateWorkOrderPayload,
  Department,
  DirectReportPayload,
  InspectionPayload,
  PendingQcBatch,
  PolishProcessPreset,
  PolishProcessStep,
  ProcessStepPayload,
  ReworkRequestItem,
  WorkerItem,
  WorkOrderItem,
} from '@/types/production'

export const useWorkOrdersStore = defineStore('workOrders', () => {
  const loading = ref(false)
  const processes = ref<PolishProcessStep[]>([])
  const workers = ref<WorkerItem[]>([])
  const workOrders = ref<WorkOrderItem[]>([])
  const pendingQc = ref<PendingQcBatch[]>([])
  const presets = ref<PolishProcessPreset[]>([])
  const reworkRequests = ref<ReworkRequestItem[]>([])

  async function loadDepartment(department: Department) {
    loading.value = true
    try {
      const [processList, workerList, orderList, reworkList] = await Promise.all([
        queryPolishProcesses(department),
        queryDepartmentWorkers(department),
        queryDepartmentWorkOrders(department),
        queryDepartmentReworkRequests(department),
      ])
      processes.value = processList
      workers.value = workerList
      workOrders.value = orderList
      reworkRequests.value = reworkList
    } finally {
      loading.value = false
    }
  }

  async function configureProcesses(
    department: Department,
    productId: number,
    steps: ProcessStepPayload[],
    presetId?: number,
  ) {
    await configurePolishProcesses(department, productId, steps, presetId)
    await loadDepartment(department)
  }

  async function addWorker(department: Department, name: string) {
    await createDepartmentWorker(department, name)
    workers.value = await queryDepartmentWorkers(department)
  }

  async function addWorkOrder(department: Department, payload: CreateWorkOrderPayload) {
    await createWorkOrder(payload)
    await loadDepartment(department)
  }

  async function submitToQc(department: Department, workOrderId: number, quantity: number) {
    await createWorkOrderSubmission(workOrderId, quantity)
    await loadDepartment(department)
  }

  async function reportDirect(
    department: Department,
    workOrderId: number,
    payload: DirectReportPayload,
  ) {
    await createDirectReport(workOrderId, payload)
    await loadDepartment(department)
  }

  async function loadPendingQc() {
    loading.value = true
    try {
      pendingQc.value = await queryPendingQcSubmissions()
      workers.value = await queryDepartmentWorkers('qc')
    } finally {
      loading.value = false
    }
  }

  async function inspect(batchId: number, payload: InspectionPayload) {
    await inspectQcSubmission(batchId, payload)
    await loadPendingQc()
  }

  async function assignQcWorker(batchId: number, qcWorkerId: number) {
    await assignQcSubmission(batchId, { qcWorkerId })
    await loadPendingQc()
  }

  async function loadPresets() {
    presets.value = await queryPolishProcessPresets()
  }

  async function savePreset(
    presetName: string,
    steps: ProcessStepPayload[],
    active: boolean,
    presetId?: number,
  ) {
    await savePolishProcessPreset(presetName, steps, active, presetId)
    await loadPresets()
  }

  async function submitToCleaning(department: Department, workOrderId: number, quantity: number) {
    await createCleaningSubmission(workOrderId, quantity)
    await loadDepartment(department)
  }

  async function completeCleaning(department: Department, cleaningBatchId: number) {
    await completeCleaningSubmission(cleaningBatchId)
    await loadDepartment(department)
  }

  return {
    addWorker,
    addWorkOrder,
    assignQcWorker,
    configureProcesses,
    inspect,
    loadDepartment,
    loadPendingQc,
    loading,
    pendingQc,
    presets,
    reworkRequests,
    processes,
    reportDirect,
    loadPresets,
    savePreset,
    submitToCleaning,
    completeCleaning,
    submitToQc,
    workers,
    workOrders,
  }
})
