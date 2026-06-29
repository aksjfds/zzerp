import { ref } from 'vue'
import { defineStore } from 'pinia'
import {
  assignQcSubmission,
  configureDepartmentProcesses,
  createDepartmentWorker,
  createDirectReport,
  createWorkOrder,
  createWorkOrderSubmission,
  inspectQcSubmission,
  queryDepartmentProcesses,
  queryDepartmentWorkers,
  queryDepartmentWorkOrders,
  queryPendingQcSubmissions,
} from '@/api/production'
import type {
  CreateWorkOrderPayload,
  Department,
  DepartmentProcessItem,
  DirectReportPayload,
  InspectionPayload,
  PendingQcBatch,
  ProcessStepPayload,
  WorkerItem,
  WorkOrderItem,
} from '@/types/production'

export const useWorkOrdersStore = defineStore('workOrders', () => {
  const loading = ref(false)
  const processes = ref<DepartmentProcessItem[]>([])
  const workers = ref<WorkerItem[]>([])
  const workOrders = ref<WorkOrderItem[]>([])
  const pendingQc = ref<PendingQcBatch[]>([])

  async function loadDepartment(department: Department) {
    loading.value = true
    try {
      const [processList, workerList, orderList] = await Promise.all([
        queryDepartmentProcesses(department),
        queryDepartmentWorkers(department),
        queryDepartmentWorkOrders(department),
      ])
      processes.value = processList
      workers.value = workerList
      workOrders.value = orderList
    } finally {
      loading.value = false
    }
  }

  async function configureProcesses(
    department: Department,
    productId: number,
    steps: ProcessStepPayload[],
  ) {
    await configureDepartmentProcesses(department, productId, steps)
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
    processes,
    reportDirect,
    submitToQc,
    workers,
    workOrders,
  }
})
