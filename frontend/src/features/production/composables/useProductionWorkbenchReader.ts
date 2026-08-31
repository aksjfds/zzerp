import { computed, ref } from 'vue'
import { ElMessage } from 'element-plus'
import { getApiErrorDetail } from '@/api/request'
import {
  queryProductionWorkbenchPositions,
  queryProductionWorkbenchWorkOrders,
} from '../api/productionWorkbench'
import type {
  AssemblyWorkbenchPosition,
  ProductionWorkbenchAttention,
  ProductionWorkbenchPosition,
  ProductionWorkbenchProcedureSummary,
  ProductionWorkbenchWorkOrderQuery,
  ProductionWorkbenchWorkOrder,
  StandardWorkbenchPosition,
} from '../domain/productionWorkbench'

type ProcedureFilter = Pick<ProductionWorkbenchProcedureSummary, 'procedure_id' | 'is_temporary'>
type PositionType = ProductionWorkbenchPosition['position_type']

export function useProductionWorkbenchReader<Position extends ProductionWorkbenchPosition>(
  departmentCode: string,
  positionType?: PositionType,
) {
  const positions = ref<Position[]>([])
  const positionsLoading = ref(false)
  const positionPage = ref(1)
  const positionTotal = ref(0)
  const pageSize = 50
  const keyword = ref('')
  const workshopName = ref<string>()
  const attention = ref<ProductionWorkbenchAttention>('all')
  const selectedPositionKey = ref<string>()
  const workOrders = ref<ProductionWorkbenchWorkOrder[]>([])
  const workOrdersLoading = ref(false)
  const workOrderPage = ref(1)
  const workOrderTotal = ref(0)
  const procedureSummaries = ref<ProductionWorkbenchProcedureSummary[]>([])
  const procedureFilter = ref<ProcedureFilter>()
  let positionSequence = 0
  let positionController: AbortController | undefined
  let workOrderSequence = 0
  let workOrderController: AbortController | undefined

  const selectedPosition = computed(() => positions.value.find(
    item => item.position_key === selectedPositionKey.value,
  ))

  function buildWorkOrderQuery(position: Position): ProductionWorkbenchWorkOrderQuery {
    const procedure = procedureFilter.value ? {
      procedure_id: procedureFilter.value.procedure_id,
      is_temporary: procedureFilter.value.is_temporary,
    } : {}
    if (position.position_type === 'standard') {
      const standard = position as StandardWorkbenchPosition
      return {
        position_type: 'standard',
        page: workOrderPage.value,
        page_size: pageSize,
        production_item_id: standard.production_item_id,
        flow_node_id: standard.flow_node_id,
        source_flow_node_id: standard.source_flow_node_id,
        ...procedure,
      }
    }
    const assembly = position as AssemblyWorkbenchPosition
    return {
      position_type: 'assembly',
      page: workOrderPage.value,
      page_size: pageSize,
      customer_order_item_id: assembly.customer_order_item_id,
      flow_node_id: assembly.flow_node_id,
      ...procedure,
    }
  }

  async function loadPositions(preserveSelection = true) {
    const sequence = ++positionSequence
    positionController?.abort()
    if (!preserveSelection) {
      positions.value = []
      positionTotal.value = 0
    }
    const controller = new AbortController()
    positionController = controller
    positionsLoading.value = true
    try {
      const result = await queryProductionWorkbenchPositions<Position>(departmentCode, {
        page: positionPage.value,
        page_size: pageSize,
        keyword: keyword.value || undefined,
        workshop_name: workshopName.value,
        attention: attention.value,
      }, controller.signal)
      if (sequence !== positionSequence) return
      positions.value = positionType
        ? result.items.filter(item => item.position_type === positionType) as Position[]
        : result.items
      positionTotal.value = result.total
      if (preserveSelection && selectedPosition.value) return
      clearSelection()
    } catch (error) {
      if (sequence === positionSequence && !controller.signal.aborted) {
        ElMessage.error(getApiErrorDetail(error)?.message || '在位物料加载失败')
      }
    } finally {
      if (sequence === positionSequence) {
        positionsLoading.value = false
        positionController = undefined
      }
    }
  }

  async function loadWorkOrders() {
    const position = selectedPosition.value
    const sequence = ++workOrderSequence
    workOrderController?.abort()
    if (!position) {
      clearWorkOrders()
      return
    }
    const controller = new AbortController()
    workOrderController = controller
    workOrdersLoading.value = true
    try {
      const result = await queryProductionWorkbenchWorkOrders(
        departmentCode,
        buildWorkOrderQuery(position),
        controller.signal,
      )
      if (sequence !== workOrderSequence) return
      workOrders.value = result.items
      workOrderTotal.value = result.total
      procedureSummaries.value = result.procedureSummaries
    } catch (error) {
      if (sequence === workOrderSequence && !controller.signal.aborted) {
        ElMessage.error(getApiErrorDetail(error)?.message || '关联工单加载失败')
      }
    } finally {
      if (sequence === workOrderSequence) {
        workOrdersLoading.value = false
        workOrderController = undefined
      }
    }
  }

  function clearWorkOrders() {
    workOrderSequence += 1
    workOrderController?.abort()
    workOrderController = undefined
    workOrders.value = []
    workOrderTotal.value = 0
    procedureSummaries.value = []
    workOrdersLoading.value = false
  }

  function clearWorkOrderPage() {
    workOrders.value = []
    workOrderTotal.value = 0
  }

  function clearSelection() {
    selectedPositionKey.value = undefined
    procedureFilter.value = undefined
    workOrderPage.value = 1
    clearWorkOrders()
  }

  async function selectPosition(position: Position) {
    selectedPositionKey.value = position.position_key
    procedureFilter.value = undefined
    workOrderPage.value = 1
    clearWorkOrders()
    await loadWorkOrders()
  }

  async function selectProcedure(summary?: ProductionWorkbenchProcedureSummary) {
    procedureFilter.value = summary ? {
      procedure_id: summary.procedure_id,
      is_temporary: summary.is_temporary,
    } : undefined
    workOrderPage.value = 1
    clearWorkOrderPage()
    await loadWorkOrders()
  }

  function isProcedureSelected(summary: ProductionWorkbenchProcedureSummary) {
    return procedureFilter.value?.procedure_id === summary.procedure_id
      && procedureFilter.value.is_temporary === summary.is_temporary
  }

  async function applyFilters(next: {
    keyword: string
    workshopName?: string
    attention: ProductionWorkbenchAttention
  }) {
    keyword.value = next.keyword
    workshopName.value = next.workshopName
    attention.value = next.attention
    positionPage.value = 1
    clearSelection()
    await loadPositions(false)
  }

  async function changePositionPage(page: number) {
    positionPage.value = page
    clearSelection()
    await loadPositions(false)
  }

  async function changeWorkOrderPage(page: number) {
    workOrderPage.value = page
    clearWorkOrderPage()
    await loadWorkOrders()
  }

  async function reload() {
    await loadPositions(true)
    if (selectedPosition.value) await loadWorkOrders()
  }

  return {
    applyFilters,
    changePositionPage,
    changeWorkOrderPage,
    isProcedureSelected,
    loadPositions,
    loadWorkOrders,
    pageSize,
    positionPage,
    positions,
    positionsLoading,
    positionTotal,
    procedureSummaries,
    reload,
    selectPosition,
    selectProcedure,
    selectedPosition,
    selectedPositionKey,
    workOrderPage,
    workOrders,
    workOrdersLoading,
    workOrderTotal,
  }
}
