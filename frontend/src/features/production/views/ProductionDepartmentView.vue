<script setup lang="ts">
import { ref } from 'vue'
import { ElMessage } from 'element-plus'
import DepartmentPageHeader from '@/shared/layout/DepartmentPageHeader.vue'
import CreateWorkOrderDialog from '../components/CreateWorkOrderDialog.vue'
import DepartmentSectionTabs from '../components/DepartmentSectionTabs.vue'
import TaskWorkOrderChoiceDialog from '../components/TaskWorkOrderChoiceDialog.vue'
import DepartmentProductionProgressView from './DepartmentProductionProgressView.vue'
import { useProductionWorkbench } from '../composables/useProductionWorkbench'
import type {
  DepartmentProductionProgressItem,
  ProductionTaskProcessingStatus,
} from '../domain/productionProgress'
import type { TaskWorkOrderChoice } from '../domain/workOrderCreation'
import '../styles/workspace.css'

const props = withDefaults(defineProps<{
  departmentCode: string
  departmentName: string
  description: string
  specialPrinting?: boolean
}>(), { specialPrinting: false })
const workbench = useProductionWorkbench(props.departmentCode)
const taskView = ref<InstanceType<typeof DepartmentProductionProgressView>>()
const choices = ref<TaskWorkOrderChoice[]>([])
const choiceVisible = ref(false)
let openRevision = 0

function availableChoices(status: ProductionTaskProcessingStatus): TaskWorkOrderChoice[] {
  const repositoryIds = new Set(status.repository_ids)
  return workbench.positions.value.flatMap(position => position.sources
    .filter(source => (
      source.available_quantity > 0
      && repositoryIds.has(source.repository_id)
    ))
    .map(source => ({
      key: `${position.position_key}:${source.repository_id}`,
      position_key: position.position_key,
      mode: 'standard' as const,
      repository_id: source.repository_id,
      label: `${position.item_name} · ${position.workshop_name}`,
      description: `${position.source_node_label} · 可开工 ${source.available_quantity}`,
    })))
}

function activateChoice(choice: TaskWorkOrderChoice) {
  const position = workbench.positions.value.find(
    item => item.position_key === choice.position_key,
  )
  const source = position?.sources.find(
    item => item.repository_id === choice.repository_id,
  )
  if (!position || !source) {
    ElMessage.warning('开单来源已变化，请重新选择')
    return
  }
  workbench.selectPositionForCreation(position)
  workbench.selectSource(source)
  choiceVisible.value = false
  workbench.openWorkOrder()
}

async function openTaskWorkOrder(
  item: DepartmentProductionProgressItem,
  status: ProductionTaskProcessingStatus,
) {
  const revision = ++openRevision
  choiceVisible.value = false
  choices.value = []
  if (item.production_item_id === null) {
    ElMessage.warning('物料尚未进入生产流程')
    return
  }
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

async function saveWorkOrder(
  payload: Parameters<typeof workbench.saveWorkOrder>[0],
) {
  if (await workbench.saveWorkOrder(payload)) await taskView.value?.load()
}
</script>

<template>
  <main class="production-page">
    <DepartmentPageHeader
      :department-name="departmentName"
      :description="description"
      @refresh="refresh"
    />
    <DepartmentSectionTabs
      :department-code="departmentCode"
      workspace-label="生产任务"
      show-inventory
      show-workers
      show-procedure-prices
    >
      <DepartmentProductionProgressView
        ref="taskView"
        embedded
        :department-code="departmentCode"
        :special-printing="specialPrinting"
        @create-work-order="openTaskWorkOrder"
      />

      <TaskWorkOrderChoiceDialog
        v-model="choiceVisible"
        :choices="choices"
        @confirm="activateChoice"
      />

      <CreateWorkOrderDialog
        v-model="workbench.dialogVisible.value"
        :item="workbench.creationTarget.value"
        :workers="workbench.workOrderWorkers.value"
        :submitting="workbench.submitting.value"
        @submit="saveWorkOrder"
      />
    </DepartmentSectionTabs>
  </main>
</template>
