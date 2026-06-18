import { computed, reactive, ref } from 'vue'
import { defineStore } from 'pinia'
import {
  createWorkOrder as createWorkOrderApi,
  queryWorkOrders,
} from '@/api/workorder'
import type {
  CreateWorkOrderPayload,
  WorkOrderItem,
  WorkOrderQuery,
} from '@/types/workorder'

export const useWorkOrdersStore = defineStore('workOrders', () => {
  const loading = ref(false)
  const workOrders = ref<WorkOrderItem[]>([])
  const queryForm = reactive<WorkOrderQuery>({
    orderId: '',
    item: '',
    status: '',
    procedure: '',
  })

  const totalQuantity = computed(() =>
    workOrders.value.reduce((total, order) => total + order.quantity, 0),
  )

  const activeQuantity = computed(() =>
    workOrders.value.reduce(
      (total, order) => total + order.steps.reduce((sum, step) => sum + step.quantity, 0),
      0,
    ),
  )

  async function loadWorkOrders() {
    loading.value = true

    try {
      workOrders.value = await queryWorkOrders(queryForm)
    } finally {
      loading.value = false
    }
  }

  async function createWorkOrder(payload: CreateWorkOrderPayload) {
    await createWorkOrderApi(payload)
    await loadWorkOrders()
  }

  async function resetQuery() {
    queryForm.orderId = ''
    queryForm.item = ''
    queryForm.status = ''
    queryForm.procedure = ''
    await loadWorkOrders()
  }

  return {
    activeQuantity,
    createWorkOrder,
    loadWorkOrders,
    loading,
    queryForm,
    resetQuery,
    totalQuantity,
    workOrders,
  }
})
