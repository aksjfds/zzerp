<script setup lang="ts">
import { computed, onMounted } from 'vue'
import { useRoute } from 'vue-router'
import { WorkerOverview } from '@/features/workers'
import DepartmentPageHeader from '@/shared/layout/DepartmentPageHeader.vue'
import CreateWorkerDialog from '../components/CreateWorkerDialog.vue'
import { useDepartmentWorkers } from '../composables/useDepartmentWorkers'
import '../styles/workspace.css'

const props = withDefaults(defineProps<{
  embedded?: boolean
  departmentCode?: string
}>(), {
  embedded: false,
  departmentCode: '',
})
const route = useRoute()
const departmentCode = String(
  props.departmentCode || route.params.departmentCode || route.meta.departmentCode || '',
)
const departmentNames: Record<string, string> = {
  stamp: '冲压部',
  cnc: '机加部',
  polish: '表面处理部',
  qc: 'QC部门',
  assembly: '装配部',
}
const controller = useDepartmentWorkers(departmentCode)
const departmentName = computed(() => (
  controller.overview.value?.department_name
  || departmentNames[departmentCode]
  || '生产部门'
))

onMounted(controller.loadWorkers)
</script>

<template>
  <component :is="embedded ? 'section' : 'main'" :class="{ 'production-page': !embedded }">
    <DepartmentPageHeader
      v-if="!embedded"
      :department-name="departmentName"
      :page-title="`${departmentName}工人管理`"
      description="查看本部门工人及其工作情况，并录入新工人。"
      @refresh="controller.loadWorkers"
    />
    <WorkerOverview
      v-model:worker-keyword="controller.workerKeyword.value"
      v-model:department-filter="controller.departmentFilter.value"
      v-model:selected-month="controller.selectedMonth.value"
      :departments="controller.departments.value"
      :workers="controller.filteredWorkers.value"
      :selected-worker="controller.selectedWorker.value"
      :selected-worker-title="controller.selectedWorkerTitle.value"
      :history="controller.history.value"
      :workers-loading="controller.workersLoading.value"
      :history-loading="controller.historyLoading.value"
      :pay-summary="controller.paySummary.value"
      :pay-loading="controller.payLoading.value"
      :show-department-filter="false"
      allow-create
      allow-manage
      @select="controller.selectWorker"
      @month-change="controller.loadWorkerDetails"
      @create="controller.createWorker"
      @edit="controller.editWorker"
      @delete="controller.removeWorker"
    />
    <CreateWorkerDialog
      v-model="controller.dialogVisible.value"
      :workshops="controller.overview.value?.workshops || []"
      :submitting="controller.submitting.value"
      :worker="controller.editingWorker.value"
      @submit="controller.saveWorker"
    />
  </component>
</template>
