import { ref } from 'vue'
import { defineStore } from 'pinia'
import {
  completeTask as completeTaskApi,
  createTask as createTaskApi,
  queryDepartmentProcedures,
  queryDepartmentTasks,
  queryDepartmentWorkers,
} from '@/api/production'
import type { CreateTaskPayload, Department, ProcedureItem, TaskItem, WorkerItem } from '@/types/production'

export const useTasksStore = defineStore('tasks', () => {
  const loading = ref(false)
  const tasks = ref<TaskItem[]>([])
  const workers = ref<WorkerItem[]>([])
  const procedures = ref<ProcedureItem[]>([])

  async function loadDepartmentData(department: Department) {
    loading.value = true

    try {
      const [taskList, workerList, procedureList] = await Promise.all([
        queryDepartmentTasks(department),
        queryDepartmentWorkers(department),
        queryDepartmentProcedures(department),
      ])
      tasks.value = taskList
      workers.value = workerList
      procedures.value = procedureList
    } finally {
      loading.value = false
    }
  }

  async function createTask(payload: CreateTaskPayload) {
    await createTaskApi(payload)
    await loadDepartmentData(payload.department)
  }

  async function completeTask(taskId: number, department: Department) {
    await completeTaskApi(taskId)
    await loadDepartmentData(department)
  }

  return {
    completeTask,
    createTask,
    loadDepartmentData,
    loading,
    procedures,
    tasks,
    workers,
  }
})
