<script setup lang="ts">
import { ref } from 'vue'
import { ElMessage } from 'element-plus'
import DepartmentPageHeader from '@/shared/layout/DepartmentPageHeader.vue'
import AssemblyWorkOrderDialog from '../components/AssemblyWorkOrderDialog.vue'
import CreateWorkOrderDialog from '../components/CreateWorkOrderDialog.vue'
import DepartmentSectionTabs from '../components/DepartmentSectionTabs.vue'
import TaskWorkOrderChoiceDialog from '../components/TaskWorkOrderChoiceDialog.vue'
import DepartmentProductionProgressView from './DepartmentProductionProgressView.vue'
import { useAssemblyWorkbench } from '../composables/useAssemblyWorkbench'
import type {
  DepartmentProductionProgressItem,
  ProductionTaskProcessingStatus,
} from '../domain/productionProgress'
import type { TaskWorkOrderChoice } from '../domain/workOrderCreation'
import '../styles/workspace.css'

const workbench = useAssemblyWorkbench()
const taskView = ref<InstanceType<typeof DepartmentProductionProgressView>>()
const choices = ref<TaskWorkOrderChoice[]>([])
const choiceVisible = ref(false)
let openRevision = 0

function availableChoices(status: ProductionTaskProcessingStatus): TaskWorkOrderChoice[] {
  const repositoryIds = new Set(status.repository_ids)
  return workbench.positions.value.flatMap<TaskWorkOrderChoice>(position => {
    if (position.position_type === 'standard') {
      return position.sources
        .filter(source => (
          source.available_quantity > 0
          && repositoryIds.has(source.repository_id)
        ))
        .map(source => ({
          key: `${position.position_key}:standard:${source.repository_id}`,
          position_key: position.position_key,
          mode: 'standard' as const,
          repository_id: source.repository_id,
          label: `${position.item_name} · ${position.workshop_name}`,
          description: `${source.processing_status} · 可开工 ${source.available_quantity}`,
        }))
    }
    const initial = (
      status.creation_mode === 'assembly_initial'
      && position.initial_capacity_quantity > 0
    )
      ? [{
          key: `${position.position_key}:initial`,
          position_key: position.position_key,
          mode: 'assembly_initial' as const,
          repository_id: null,
          label: `${position.item_name} · 首次${position.workshop_name}`,
          description: `多路物料投入 · 可开工 ${position.initial_capacity_quantity}`,
        }]
      : []
    const continuation = position.continuation_sources
      .filter(source => (
        source.available_quantity > 0
        && repositoryIds.has(source.repository_id)
      ))
      .map(source => ({
        key: `${position.position_key}:continuation:${source.repository_id}`,
        position_key: position.position_key,
        mode: 'assembly_continuation' as const,
        repository_id: source.repository_id,
        label: `${position.item_name} · 后续${position.workshop_name}`,
        description: `${source.processing_status} · 可开工 ${source.available_quantity}`,
      }))
    return [...initial, ...continuation]
  })
}

function activateChoice(choice: TaskWorkOrderChoice) {
  const position = workbench.positions.value.find(
    item => item.position_key === choice.position_key,
  )
  if (!position) {
    ElMessage.warning('开单来源已变化，请重新选择')
    return
  }
  workbench.selectPositionForCreation(position)
  choiceVisible.value = false
  if (choice.mode === 'standard' && position.position_type === 'standard') {
    const source = position.sources.find(item => item.repository_id === choice.repository_id)
    if (!source) {
      ElMessage.warning('开单来源已变化，请重新选择')
      return
    }
    workbench.selectStandardSource(source)
    workbench.openStandardWorkOrder()
    return
  }
  if (choice.mode === 'assembly_initial' && position.position_type === 'assembly') {
    workbench.openInitialAssemblyWorkOrder()
    return
  }
  if (choice.mode === 'assembly_continuation' && position.position_type === 'assembly') {
    const source = position.continuation_sources.find(
      item => item.repository_id === choice.repository_id,
    )
    if (!source) {
      ElMessage.warning('开单来源已变化，请重新选择')
      return
    }
    workbench.selectContinuationSource(source)
    workbench.openContinuationWorkOrder()
  }
}

async function openTaskWorkOrder(
  item: DepartmentProductionProgressItem,
  status: ProductionTaskProcessingStatus,
) {
  const revision = ++openRevision
  choiceVisible.value = false
  choices.value = []
  await workbench.focusTask(item)
  if (revision !== openRevision) return
  choices.value = availableChoices(status)
  if (!choices.value.length) {
    ElMessage.warning(
      workbench.positions.value.length
        ? '当前任务没有可开工数量'
        : '物料尚未到达当前车间',
    )
    return
  }
  if (choices.value.length === 1 && choices.value[0]) {
    activateChoice(choices.value[0])
    return
  }
  choiceVisible.value = true
}

async function refresh() {
  await taskView.value?.load()
}

async function saveStandardWorkOrder(
  payload: Parameters<typeof workbench.saveStandardWorkOrder>[0],
) {
  if (await workbench.saveStandardWorkOrder(payload)) await taskView.value?.load()
}

async function saveAssemblyWorkOrder(
  payload: Parameters<typeof workbench.saveAssemblyWorkOrder>[0],
) {
  if (await workbench.saveAssemblyWorkOrder(payload)) await taskView.value?.load()
}
</script>

<template>
  <main class="production-page">
    <DepartmentPageHeader
      department-name="装配部"
      description="装配任务及装配部所属加工工艺。"
      @refresh="refresh"
    />
    <DepartmentSectionTabs
      department-code="assembly"
      workspace-label="生产任务"
      show-inventory
      show-workers
      show-procedure-prices
    >
      <DepartmentProductionProgressView
        ref="taskView"
        embedded
        department-code="assembly"
        @create-work-order="openTaskWorkOrder"
      />

      <TaskWorkOrderChoiceDialog
        v-model="choiceVisible"
        :choices="choices"
        @confirm="activateChoice"
      />

      <CreateWorkOrderDialog
        v-model="workbench.standardDialogVisible.value"
        :item="workbench.standardCreationTarget.value"
        :workers="workbench.workOrderWorkers.value"
        :submitting="workbench.submitting.value"
        @submit="saveStandardWorkOrder"
      />
      <AssemblyWorkOrderDialog
        v-model="workbench.assemblyDialogVisible.value"
        :item="workbench.activeAssemblyTarget.value"
        :workers="workbench.workOrderWorkers.value"
        :submitting="workbench.submitting.value"
        @submit="saveAssemblyWorkOrder"
      />
    </DepartmentSectionTabs>
  </main>
</template>
