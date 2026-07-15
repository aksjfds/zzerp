<script setup lang="ts">
import { onMounted } from 'vue'
import DepartmentPageHeader from '../components/DepartmentPageHeader.vue'
import RepositoryFilterBar from '../components/RepositoryFilterBar.vue'
import RepositoryCards from '../components/RepositoryCards.vue'
import QcBatchCards from '../components/QcBatchCards.vue'
import QcInspectionDialog from '../components/QcInspectionDialog.vue'
import { useQcDepartment } from '../composables/useQcDepartment'
import '../styles/workspace.css'

const controller = useQcDepartment()
const { workspace } = controller
const {
  items, loading, pageSize,
  repositoryPage, repositoryTotal, selectedRepository, selectedCardKey, workers,
} = workspace
const {
  activeBatch, applyFilters, batches, detailLoading, dialogVisible,
  changeRepositoryPage, historyPage, historyTotal, load, loadDetails, openInspection,
  refresh, saveInspection, selectRepository, submitting,
} = controller
onMounted(load)
</script>

<template>
  <main class="production-page">
    <DepartmentPageHeader department-name="QC部门" description="待质检配件与质检结果录入。" @refresh="refresh" />
    <RepositoryFilterBar @search="applyFilters" />
    <section class="production-workspace">
      <div class="production-card">
        <RepositoryCards :items="items" :loading="loading" :selected-key="selectedCardKey"
          :allow-work-order="false" @select="selectRepository" />
        <ElPagination v-model:current-page="repositoryPage" class="production-pagination" layout="prev, next, total"
          :page-size="pageSize" :total="repositoryTotal" @current-change="changeRepositoryPage" />
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
