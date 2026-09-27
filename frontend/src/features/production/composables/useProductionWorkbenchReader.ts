import { computed, onScopeDispose, ref, shallowRef } from 'vue'
import { getApiErrorDetail } from '@/api/request'
import { queryProductionWorkbenchPositions } from '../api/productionWorkbench'
import type { ProductionWorkbenchPosition } from '../domain/productionWorkbench'

type PositionType = ProductionWorkbenchPosition['position_type']

export function useProductionWorkbenchReader<Position extends ProductionWorkbenchPosition>(
  departmentCode: string,
  positionType?: PositionType,
) {
  const positions = shallowRef<Position[]>([])
  const positionsLoading = ref(false)
  const positionsError = ref('')
  const workshopId = ref<number>()
  const taskCustomerOrderItemId = ref<number>()
  const taskProductionItemId = ref<number>()
  const taskFlowNodeId = ref<string>()
  const selectedPositionKey = ref<string>()
  let positionSequence = 0
  let positionController: AbortController | undefined

  const selectedPosition = computed(() => positions.value.find(
    item => item.position_key === selectedPositionKey.value,
  ))

  async function loadPositions(preserveSelection = true) {
    const sequence = ++positionSequence
    positionController?.abort()
    positionController = undefined
    positionsLoading.value = false
    positionsError.value = ''
    const previousSelection = preserveSelection ? selectedPositionKey.value : undefined
    positions.value = []
    const customerOrderItemId = taskCustomerOrderItemId.value
    const scopedWorkshopId = workshopId.value
    const flowNodeId = taskFlowNodeId.value
    if (!customerOrderItemId || !scopedWorkshopId || !flowNodeId) {
      positions.value = []
      clearSelection()
      return
    }
    const controller = new AbortController()
    positionController = controller
    positionsLoading.value = true
    try {
      const result = await queryProductionWorkbenchPositions<Position>(departmentCode, {
        page: 1,
        page_size: 200,
        customer_order_item_id: customerOrderItemId,
        workshop_id: scopedWorkshopId,
        flow_node_id: flowNodeId,
        production_item_id: taskProductionItemId.value,
      }, controller.signal)
      if (sequence !== positionSequence) return
      positions.value = positionType
        ? result.items.filter(item => item.position_type === positionType) as Position[]
        : result.items
      selectedPositionKey.value = positions.value.some(item => item.position_key === previousSelection)
        ? previousSelection
        : undefined
      return true
    } catch (error) {
      if (sequence === positionSequence && !controller.signal.aborted) {
        positionsError.value = getApiErrorDetail(error)?.message || '在位物料加载失败'
        clearSelection()
      }
    } finally {
      if (sequence === positionSequence) {
        positionsLoading.value = false
        positionController = undefined
      }
    }
  }

  function clearSelection() {
    selectedPositionKey.value = undefined
  }

  function selectPositionForCreation(position: Position) {
    selectedPositionKey.value = position.position_key
  }

  async function focusTask(next: {
    customerOrderItemId: number
    productionItemId?: number
    flowNodeId?: string
    workshopId: number
  }) {
    taskCustomerOrderItemId.value = next.customerOrderItemId
    taskProductionItemId.value = next.productionItemId
    taskFlowNodeId.value = next.flowNodeId
    workshopId.value = next.workshopId
    clearSelection()
    if (!await loadPositions(false)) return
    const first = positions.value[0]
    if (positions.value.length === 1 && first) selectPositionForCreation(first)
  }

  async function reload() {
    await loadPositions(true)
  }

  onScopeDispose(() => {
    positionSequence += 1
    positionController?.abort()
  })

  return {
    focusTask,
    positions,
    positionsError,
    positionsLoading,
    reload,
    selectPositionForCreation,
    selectedPosition,
    selectedPositionKey,
  }
}
