import { computed, ref } from 'vue'
import { ElMessage } from 'element-plus'
import { getApiErrorDetail } from '@/api/request'
import { queryDepartmentWorkers } from '../api/departmentWorkers'
import { createWorkOrder } from '../api/workOrders'
import type {
  StandardWorkbenchPosition,
  StandardWorkbenchSource,
} from '../domain/productionWorkbench'
import type { WorkerItem } from '../domain/types'
import type { DepartmentProductionProgressItem } from '../domain/productionProgress'
import type { WorkOrderCreationTarget } from '../domain/workOrderCreation'
import { useProductionWorkbenchReader } from './useProductionWorkbenchReader'

export function useProductionWorkbench(departmentCode: string) {
  const reader = useProductionWorkbenchReader<StandardWorkbenchPosition>(
    departmentCode,
    'standard',
  )
  const selectedSourceId = ref<number>()
  const workers = ref<WorkerItem[]>([])
  const dialogVisible = ref(false)
  const submitting = ref(false)
  let referenceDataLoaded = false

  const selectedSource = computed(() => reader.selectedPosition.value?.sources.find(
    item => item.repository_id === selectedSourceId.value,
  ))
  const workOrderWorkers = computed(() => workers.value.filter(
    item => item.workshop_id === reader.selectedPosition.value?.workshop_id,
  ))
  const creationTarget = computed<WorkOrderCreationTarget | undefined>(() => {
    const position = reader.selectedPosition.value
    const source = selectedSource.value
    if (!position || !source) return undefined
    return {
      repository_id: source.repository_id,
      part_no: position.item_code,
      part_name: position.item_name,
      workshop_name: position.workshop_name,
      available_quantity: source.available_quantity,
      available_procedures: source.available_procedures,
    }
  })

  function retainSingleSource(position: StandardWorkbenchPosition) {
    const current = position.sources.find(item => item.repository_id === selectedSourceId.value)
    if (current) return
    selectedSourceId.value = position.sources.length === 1
      ? position.sources[0]?.repository_id
      : undefined
  }

  function selectSource(source: StandardWorkbenchSource) {
    selectedSourceId.value = source.repository_id
  }

  function openWorkOrder() {
    const source = selectedSource.value
    if (!source) {
      ElMessage.warning('请选择开单物料来源')
      return
    }
    if (!source.procedure_configuration_confirmed) {
      ElMessage.warning('当前物料和车间尚未确认工艺配置')
      return
    }
    if (!source.can_create_work_order || source.available_quantity < 1) {
      ElMessage.warning('当前来源没有可开工数量')
      return
    }
    dialogVisible.value = true
  }

  async function saveWorkOrder(payload: {
    repositoryId: number
    procedureId: number | null
    procedureName: string | null
    isTemporary: boolean
    quantity: number
    workerId: number | null
    remark: string
  }) {
    submitting.value = true
    try {
      await createWorkOrder(
        payload.repositoryId,
        payload.procedureId,
        payload.procedureName,
        payload.isTemporary,
        payload.quantity,
        payload.workerId,
        payload.remark,
      )
      dialogVisible.value = false
      await reloadWorkspace()
      ElMessage.success('工单已创建')
      return true
    } catch (error) {
      ElMessage.error(getApiErrorDetail(error)?.message || '创建工单失败')
      return false
    } finally {
      submitting.value = false
    }
  }

  async function reloadWorkspace() {
    await reader.reload()
    if (reader.selectedPosition.value) retainSingleSource(reader.selectedPosition.value)
  }

  async function loadReferenceData() {
    if (referenceDataLoaded) return
    try {
      workers.value = await queryDepartmentWorkers(departmentCode)
      referenceDataLoaded = true
    } catch {
      ElMessage.warning('工人列表加载失败')
    }
  }

  async function focusTask(task: DepartmentProductionProgressItem) {
    selectedSourceId.value = undefined
    await Promise.all([
      loadReferenceData(),
      reader.focusTask({
        customerOrderItemId: task.customer_order_item_id,
        productionItemId: task.production_item_id || undefined,
        flowNodeId: task.flow_node_id,
        workshopId: task.processing_workshop_id,
      }),
    ])
    if (reader.selectedPosition.value) retainSingleSource(reader.selectedPosition.value)
  }

  return {
    ...reader,
    creationTarget,
    dialogVisible,
    focusTask,
    openWorkOrder,
    refresh: reloadWorkspace,
    reloadWorkspace,
    saveWorkOrder,
    selectSource,
    selectedSource,
    submitting,
    workOrderWorkers,
  }
}
