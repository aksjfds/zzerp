<script setup lang="ts">
import { onMounted } from 'vue'
import DepartmentPageHeader from '../components/DepartmentPageHeader.vue'
import QcBatchCards from '../components/QcBatchCards.vue'
import QcInspectionDialog from '../components/QcInspectionDialog.vue'
import { useQcDepartment } from '../composables/useQcDepartment'
import '../styles/workspace.css'

const {
  activeBatch,
  batches,
  changePage,
  dialogVisible,
  load,
  loading,
  openInspection,
  page,
  pageSize,
  refresh,
  saveInspection,
  submitting,
  total,
  workers,
} = useQcDepartment()

onMounted(load)
</script>

<template>
  <main class="production-page">
    <DepartmentPageHeader
      department-name="QC部门"
      description="所有待检工单批次与质检结果录入。"
      @refresh="refresh"
    />
    <section class="production-card qc-workspace">
      <div class="qc-heading">
        <strong>待检批次</strong>
        <span>共 {{ total }} 批</span>
      </div>
      <QcBatchCards :items="batches" :loading="loading" @inspect="openInspection" />
      <ElPagination
        v-model:current-page="page"
        class="production-pagination"
        layout="prev, pager, next, total"
        :page-size="pageSize"
        :total="total"
        @current-change="changePage"
      />
    </section>
    <QcInspectionDialog
      v-model="dialogVisible"
      :batch="activeBatch"
      :workers="workers"
      :submitting="submitting"
      @submit="saveInspection"
    />
  </main>
</template>

<style scoped>
.qc-workspace { min-height: 300px; }
.qc-heading { display: flex; justify-content: space-between; align-items: center; }
.qc-heading span { color: var(--el-text-color-secondary); font-size: 13px; }
</style>
