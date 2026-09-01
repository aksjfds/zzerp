<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { ElMessage } from 'element-plus'
import DepartmentPageHeader from '@/shared/layout/DepartmentPageHeader.vue'
import { queryDepartmentWorkers } from '../api/departmentWorkers'
import DepartmentSectionTabs from '../components/DepartmentSectionTabs.vue'
import StandardQcWorkspace from '../components/StandardQcWorkspace.vue'
import SupplierProcessingQcPanel from '../components/SupplierProcessingQcPanel.vue'
import type { WorkerItem } from '../domain/types'
import '../styles/workspace.css'

const qcTabs = [{ name: 'supplier-processing', label: '委外加工质检' }] as const
const workers = ref<WorkerItem[]>([])
const standardWorkspace = ref<{ refresh: () => Promise<void> }>()
const supplierProcessingPanel = ref<{ refresh: () => Promise<void> }>()

async function loadWorkers() {
  try {
    workers.value = await queryDepartmentWorkers('qc')
  } catch {
    ElMessage.warning('QC 工人列表加载失败')
  }
}

async function refreshWorkspace() {
  await Promise.all([
    loadWorkers(),
    standardWorkspace.value?.refresh(),
    supplierProcessingPanel.value?.refresh(),
  ])
}

onMounted(loadWorkers)
</script>

<template>
  <main class="production-page">
    <DepartmentPageHeader
      department-name="QC部门"
      description="先录入工单质检结果，再决定合格品返回、放行或入库。"
      @refresh="refreshWorkspace"
    />
    <DepartmentSectionTabs
      department-code="qc"
      workspace-label="生产工单质检"
      :additional-tabs="qcTabs"
      show-workers
    >
      <StandardQcWorkspace ref="standardWorkspace" :workers="workers" />
      <template #supplier-processing>
        <SupplierProcessingQcPanel ref="supplierProcessingPanel" :workers="workers" />
      </template>
    </DepartmentSectionTabs>
  </main>
</template>
