<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { ElMessage } from 'element-plus'
import { getApiErrorDetail } from '@/api/request'
import DepartmentPageHeader from '../components/DepartmentPageHeader.vue'
import RepositoryCards from '../components/RepositoryCards.vue'
import QcBatchCards from '../components/QcBatchCards.vue'
import QcInspectionDialog from '../components/QcInspectionDialog.vue'
import { useDepartmentWorkspace } from '../composables/useDepartmentWorkspace'
import { inspectQcBatch, queryPendingQcBatches } from '../api/repositories'
import type { PendingQcBatch, QcInspectionPayload, RepositoryItem } from '../domain/types'
import '../styles/workspace.css'

const workspace = useDepartmentWorkspace('qc', true)
const {
  items, loading, pageSize,
  repositoryPage, repositoryTotal, selectedProductionItemId, selectedRepository, selectedRepositoryId, workers,
} = workspace
const batches = ref<PendingQcBatch[]>([])
const activeBatch = ref<PendingQcBatch>()
const detailLoading = ref(false)
const historyPage = ref(1)
const historyTotal = ref(0)
const dialogVisible = ref(false)
const submitting = ref(false)

async function loadDetails() {
  batches.value = []
  historyTotal.value = 0
  if (!selectedProductionItemId.value) return
  detailLoading.value = true
  try {
    const result = await queryPendingQcBatches(historyPage.value, pageSize, selectedProductionItemId.value)
    batches.value = result.items
    historyTotal.value = result.total
  } catch { ElMessage.warning('关联质检记录加载失败') }
  finally { detailLoading.value = false }
}
async function loadAll() { await workspace.loadRepositories(); await loadDetails() }
function selectRepository(item: RepositoryItem) {
  workspace.selectRepository(item)
  historyPage.value = 1
  void loadDetails()
}
function openInspection(batch: PendingQcBatch) {
  activeBatch.value = batch
  dialogVisible.value = true
}
async function saveInspection(payload: QcInspectionPayload) {
  if (!activeBatch.value) return
  submitting.value = true
  try {
    await inspectQcBatch(activeBatch.value.id, payload)
    dialogVisible.value = false
    await loadAll()
    ElMessage.success('QC 结果已录入')
  } catch (error) { ElMessage.error(getApiErrorDetail(error)?.message || 'QC 结果录入失败') }
  finally { submitting.value = false }
}
async function refresh() { historyPage.value = 1; await workspace.refresh(); await loadDetails() }
onMounted(async () => { await workspace.load(); await loadDetails() })
</script>

<template>
  <main class="production-page">
    <DepartmentPageHeader department-name="QC部门" description="待质检配件与质检结果录入。" @refresh="refresh" />
    <section class="production-workspace">
      <div class="production-card">
        <RepositoryCards :items="items" :loading="loading" :selected-id="selectedRepositoryId"
          :allow-work-order="false" @select="selectRepository" />
        <ElPagination v-model:current-page="repositoryPage" class="production-pagination" layout="prev, next, total"
          :page-size="pageSize" :total="repositoryTotal" @current-change="workspace.loadRepositories" />
      </div>
      <div class="production-card production-details">
        <div v-if="selectedRepository" class="production-selection"><strong>{{ selectedRepository.part_no }} - {{
          selectedRepository.part_name }}</strong><span>{{ selectedRepository.customer_order_no }} · {{
              selectedRepository.procedure_name }}</span></div>
        <QcBatchCards :items="batches" :loading="detailLoading" @inspect="openInspection" />
        <ElPagination v-model:current-page="historyPage" class="production-pagination" layout="prev, pager, next, total"
          :page-size="pageSize" :total="historyTotal" @current-change="loadDetails" />
      </div>
    </section>
    <QcInspectionDialog v-model="dialogVisible" :batch="activeBatch" :workers="workers" :submitting="submitting"
      @submit="saveInspection" />
  </main>
</template>
