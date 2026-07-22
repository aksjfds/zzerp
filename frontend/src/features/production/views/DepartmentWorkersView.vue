<script setup lang="ts">
import { computed, onMounted } from 'vue'
import { useRoute } from 'vue-router'
import WorkerOverview from '@/features/workers/components/WorkerOverview.vue'
import DepartmentPageHeader from '../components/DepartmentPageHeader.vue'
import CreateWorkerDialog from '../components/CreateWorkerDialog.vue'
import { useDepartmentWorkers } from '../composables/useDepartmentWorkers'
import '../styles/workspace.css'

const route = useRoute()
const departmentCode = String(route.params.departmentCode)
const departmentNames: Record<string, string> = {
  stamp: '冲压部门',
  polish: '表面处理部门',
  qc: 'QC部门',
  assembly: '装配部门',
  warehouse: '仓库部门',
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
  <main class="production-page">
    <DepartmentPageHeader
      :department-name="departmentName"
      :page-title="`${departmentName}工人管理`"
      description="查看本部门工人及其工作情况，并录入新工人。"
      :back-path="`/${departmentCode}`"
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
      :show-department-filter="false"
      allow-create
      @select="controller.selectWorker"
      @month-change="controller.loadHistory"
      @create="controller.dialogVisible.value = true"
    />
    <CreateWorkerDialog
      v-model="controller.dialogVisible.value"
      :workshops="controller.overview.value?.workshops || []"
      :submitting="controller.submitting.value"
      @submit="controller.saveWorker"
    />
  </main>
</template>
