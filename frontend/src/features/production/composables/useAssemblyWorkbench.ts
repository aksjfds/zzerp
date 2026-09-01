import { computed, ref } from 'vue'
import { ElMessage } from 'element-plus'
import { getApiErrorDetail } from '@/api/request'
import { queryDepartmentWorkers } from '../api/departmentWorkers'
import { createAssemblyWorkOrder, createWorkOrder } from '../api/workOrders'
import type {
  AssemblyWorkbenchContinuationSource,
  AssemblyWorkbenchPosition,
  ProductionWorkbenchPosition,
  StandardWorkbenchSource,
  WorkbenchInventorySource,
} from '../domain/productionWorkbench'
import type { WorkerItem } from '../domain/types'
import type { DepartmentProductionProgressItem } from '../domain/productionProgress'
import type {
  AssemblyWorkOrderCreationMaterial,
  AssemblyWorkOrderCreationTarget,
  WorkOrderCreationTarget,
} from '../domain/workOrderCreation'
import { useProductionWorkbenchReader } from './useProductionWorkbenchReader'

export function useAssemblyWorkbench() {
  const reader = useProductionWorkbenchReader<ProductionWorkbenchPosition>('assembly')
  const workers = ref<WorkerItem[]>([])
  const selectedStandardSourceId = ref<number>()
  const selectedContinuationSourceId = ref<number>()
  const standardDialogVisible = ref(false)
  const assemblyDialogVisible = ref(false)
  const submitting = ref(false)
  let referenceDataLoaded = false

  const selectedStandardSource = computed(() => {
    const position = reader.selectedPosition.value
    if (position?.position_type !== 'standard') return undefined
    return position.sources.find(item => item.repository_id === selectedStandardSourceId.value)
  })
  const selectedContinuationSource = computed(() => {
    const position = reader.selectedPosition.value
    if (position?.position_type !== 'assembly') return undefined
    return position.continuation_sources.find(
      item => item.repository_id === selectedContinuationSourceId.value,
    )
  })
  const workOrderWorkers = computed(() => workers.value.filter(
    item => item.workshop_id === reader.selectedPosition.value?.workshop_id,
  ))

  function retainSingleSources(position: ProductionWorkbenchPosition) {
    if (position.position_type === 'standard') {
      const current = position.sources.find(
        item => item.repository_id === selectedStandardSourceId.value,
      )
      selectedStandardSourceId.value = current?.repository_id
        ?? (position.sources.length === 1 ? position.sources[0]?.repository_id : undefined)
      selectedContinuationSourceId.value = undefined
      return
    }
    const current = position.continuation_sources.find(
      item => item.repository_id === selectedContinuationSourceId.value,
    )
    selectedContinuationSourceId.value = current?.repository_id
      ?? (position.continuation_sources.length === 1
        ? position.continuation_sources[0]?.repository_id
        : undefined)
    selectedStandardSourceId.value = undefined
  }

  function sourceLabel(index: number, source: WorkbenchInventorySource) {
    return `来源 ${index + 1} · 可用 ${source.available_quantity} · 到达 ${source.arrived_at || '—'}`
  }

  function initialMaterials(
    position: AssemblyWorkbenchPosition,
  ): AssemblyWorkOrderCreationMaterial[] {
    return position.input_materials.map(material => ({
      material_key: material.material_key,
      item_code: material.item_code,
      item_name: material.item_name,
      unit_quantity: material.unit_quantity,
      sources: material.sources.map((source, index) => ({
        repository_id: source.repository_id,
        source_label: sourceLabel(index, source),
        available_quantity: source.available_quantity,
      })),
    }))
  }

  const standardCreationTarget = computed<WorkOrderCreationTarget | undefined>(() => {
    const position = reader.selectedPosition.value
    const source = selectedStandardSource.value
    if (position?.position_type !== 'standard' || !source) return undefined
    return {
      repository_id: source.repository_id,
      part_no: position.item_code,
      part_name: position.item_name,
      workshop_name: position.workshop_name,
      available_quantity: source.available_quantity,
      available_procedures: source.available_procedures,
    }
  })

  const initialAssemblyTarget = computed<AssemblyWorkOrderCreationTarget | undefined>(() => {
    const position = reader.selectedPosition.value
    if (position?.position_type !== 'assembly') return undefined
    return {
      repository_id: null,
      part_no: position.item_code,
      part_name: position.item_name,
      workshop_name: position.workshop_name,
      available_quantity: position.initial_capacity_quantity,
      available_procedures: position.available_procedures,
      materials: initialMaterials(position),
    }
  })

  const continuationTarget = computed<AssemblyWorkOrderCreationTarget | undefined>(() => {
    const position = reader.selectedPosition.value
    const source = selectedContinuationSource.value
    if (position?.position_type !== 'assembly' || !source) return undefined
    return {
      repository_id: source.repository_id,
      part_no: position.item_code,
      part_name: position.item_name,
      workshop_name: position.workshop_name,
      available_quantity: source.available_quantity,
      available_procedures: source.available_procedures,
      materials: [{
        material_key: `assembly:${position.flow_node_id}`,
        item_code: position.item_code,
        item_name: position.item_name,
        unit_quantity: 1,
        sources: [{
          repository_id: source.repository_id,
          source_label: '所选节点在制品',
          available_quantity: source.available_quantity,
        }],
      }],
    }
  })
  const activeAssemblyTarget = ref<AssemblyWorkOrderCreationTarget>()

  function selectStandardSource(source: StandardWorkbenchSource) {
    selectedStandardSourceId.value = source.repository_id
  }

  function selectContinuationSource(source: AssemblyWorkbenchContinuationSource) {
    selectedContinuationSourceId.value = source.repository_id
  }

  function validateConfiguredSource(source: {
    procedure_configuration_confirmed: boolean
    can_create_work_order: boolean
    available_quantity: number
  } | undefined) {
    if (!source) {
      ElMessage.warning('请选择开单物料来源')
      return false
    }
    if (!source.procedure_configuration_confirmed) {
      ElMessage.warning('当前物料和车间尚未确认工艺配置')
      return false
    }
    if (!source.can_create_work_order || source.available_quantity < 1) {
      ElMessage.warning('当前来源没有可开工数量')
      return false
    }
    return true
  }

  function openStandardWorkOrder() {
    if (!validateConfiguredSource(selectedStandardSource.value)) return
    standardDialogVisible.value = true
  }

  function openInitialAssemblyWorkOrder() {
    const position = reader.selectedPosition.value
    if (position?.position_type !== 'assembly') return
    if (!position.procedure_configuration_confirmed) {
      ElMessage.warning('当前装配节点尚未确认工艺配置')
      return
    }
    if (!position.can_create_initial_work_order || !initialAssemblyTarget.value) {
      ElMessage.warning('首次多路输入尚不具备开单条件')
      return
    }
    activeAssemblyTarget.value = initialAssemblyTarget.value
    assemblyDialogVisible.value = true
  }

  function openContinuationWorkOrder() {
    if (!validateConfiguredSource(selectedContinuationSource.value)) return
    if (!continuationTarget.value) return
    activeAssemblyTarget.value = continuationTarget.value
    assemblyDialogVisible.value = true
  }

  async function saveStandardWorkOrder(payload: {
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
      standardDialogVisible.value = false
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

  async function saveAssemblyWorkOrder(payload: {
    quantity: number
    materials: Array<{ repository_id: number; quantity: number }>
    procedureId: number | null
    procedureName: string | null
    isTemporary: boolean
    workerId: number | null
    remark: string
  }) {
    submitting.value = true
    try {
      await createAssemblyWorkOrder(
        payload.materials,
        payload.procedureId,
        payload.procedureName,
        payload.isTemporary,
        payload.quantity,
        payload.workerId,
        payload.remark,
      )
      assemblyDialogVisible.value = false
      activeAssemblyTarget.value = undefined
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
    if (reader.selectedPosition.value) retainSingleSources(reader.selectedPosition.value)
  }

  async function loadReferenceData() {
    if (referenceDataLoaded) return
    try {
      workers.value = await queryDepartmentWorkers('assembly')
      referenceDataLoaded = true
    } catch {
      ElMessage.warning('工人列表加载失败')
    }
  }

  async function focusTask(task: DepartmentProductionProgressItem) {
    selectedStandardSourceId.value = undefined
    selectedContinuationSourceId.value = undefined
    await Promise.all([
      loadReferenceData(),
      reader.focusTask({
        customerOrderItemId: task.customer_order_item_id,
        flowNodeId: task.flow_node_id,
        workshopId: task.processing_workshop_id,
      }),
    ])
    if (reader.selectedPosition.value) retainSingleSources(reader.selectedPosition.value)
  }

  return {
    ...reader,
    activeAssemblyTarget,
    assemblyDialogVisible,
    focusTask,
    openContinuationWorkOrder,
    openInitialAssemblyWorkOrder,
    openStandardWorkOrder,
    refresh: reloadWorkspace,
    reloadWorkspace,
    saveAssemblyWorkOrder,
    saveStandardWorkOrder,
    selectContinuationSource,
    selectStandardSource,
    selectedContinuationSource,
    selectedStandardSource,
    standardCreationTarget,
    standardDialogVisible,
    submitting,
    workOrderWorkers,
  }
}
