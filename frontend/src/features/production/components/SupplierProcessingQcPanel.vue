<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { getApiErrorDetail } from '@/api/request'
import {
  inspectSupplierProcessingWorkOrder,
  querySupplierProcessingQcTasks,
  releaseSupplierProcessingBatch,
  undoQcInspection,
} from '../api/qc'
import type {
  SupplierProcessingQcInspectionPayload,
  SupplierProcessingQcTask,
  WorkOrderBatch,
  WorkerItem,
} from '../domain/types'
import SupplierProcessingQcInspectionDialog from './SupplierProcessingQcInspectionDialog.vue'
import SupplierProcessingQcDrawer from './SupplierProcessingQcDrawer.vue'

defineProps<{ workers: WorkerItem[] }>()

const tasks = ref<SupplierProcessingQcTask[]>([])
const total = ref(0)
const loading = ref(false)
const submitting = ref(false)
const releasingBatchId = ref<number | null>(null)
const undoingBatchId = ref<number | null>(null)
const dialogVisible = ref(false)
const activeTask = ref<SupplierProcessingQcTask>()
const detailTask = ref<SupplierProcessingQcTask>()
const detailVisible = ref(false)

async function load() {
  loading.value = true
  try {
    const result = await querySupplierProcessingQcTasks()
    tasks.value = result.items
    total.value = result.total
    if (detailTask.value) {
      detailTask.value = result.items.find(
        task => task.work_order_id === detailTask.value?.work_order_id,
      )
      if (!detailTask.value) detailVisible.value = false
    }
  } catch (error) {
    ElMessage.error(getApiErrorDetail(error)?.message || '委外加工质检任务加载失败')
  } finally {
    loading.value = false
  }
}

async function refresh() {
  await load()
}

function openInspection(task: SupplierProcessingQcTask) {
  activeTask.value = task
  dialogVisible.value = true
}

function openDetail(task: SupplierProcessingQcTask) {
  detailTask.value = task
  detailVisible.value = true
}

async function saveInspection(payload: SupplierProcessingQcInspectionPayload) {
  const task = activeTask.value
  if (!task) return
  submitting.value = true
  try {
    await inspectSupplierProcessingWorkOrder(task.work_order_id, payload)
    dialogVisible.value = false
    activeTask.value = undefined
    await load()
    ElMessage.success('委外加工 QC 结果已录入')
  } catch (error) {
    ElMessage.error(getApiErrorDetail(error)?.message || '委外加工 QC 结果录入失败')
  } finally {
    submitting.value = false
  }
}

async function release(batch: WorkOrderBatch) {
  try {
    await ElMessageBox.confirm(
      `确认放行本批 ${batch.qualified_quantity || 0} 件合格品？确认后不能更改。`,
      '确认放行',
      { type: 'warning', confirmButtonText: '确认放行', cancelButtonText: '取消' },
    )
  } catch {
    return
  }
  releasingBatchId.value = batch.id
  try {
    await releaseSupplierProcessingBatch(batch.id)
    await load()
    ElMessage.success('该批合格品已放行')
  } catch (error) {
    ElMessage.error(getApiErrorDetail(error)?.message || '合格品放行失败')
  } finally {
    releasingBatchId.value = null
  }
}

function taskStatus(task: SupplierProcessingQcTask) {
  if (task.status === 'closed') return { label: '质检完成', type: 'success' as const }
  if (task.pending_destination_quantity > 0) {
    return { label: '待放行', type: 'primary' as const }
  }
  return { label: '待质检', type: 'warning' as const }
}

async function undoInspection(batch: WorkOrderBatch) {
  try {
    await ElMessageBox.confirm(
      '确认撤回本次委外加工 QC 结果？本次分批质检记录将被删除。',
      '撤回质检',
      { type: 'warning', confirmButtonText: '确认撤回', cancelButtonText: '取消' },
    )
  } catch {
    return
  }
  undoingBatchId.value = batch.id
  try {
    await undoQcInspection(batch.id)
    await load()
    ElMessage.success('委外加工 QC 结果已撤回')
  } catch (error) {
    ElMessage.error(getApiErrorDetail(error)?.message || '委外加工 QC 结果撤回失败')
  } finally {
    undoingBatchId.value = null
  }
}

onMounted(refresh)
defineExpose({ refresh })
</script>

<template>
  <section v-loading="loading" class="supplier-qc-panel">
    <header class="panel-heading">
      <div>
        <h2>委外加工质检</h2>
        <p>按实际质检批次分次录入结果；每批合格品单独确认放行。</p>
      </div>
      <span>待处理 {{ total }} 张工单</span>
    </header>
    <ElTable
      v-table-column-widths="'production.supplier-processing-qc'"
      :data="tasks"
      row-key="work_order_id"
      border
      stripe
      table-layout="auto"
      empty-text="暂无待处理委外加工工单"
    >
      <ElTableColumn label="物料" min-width="190">
        <template #default="{ row }">
          <strong>{{ row.item_code }} {{ row.item_name }}</strong>
        </template>
      </ElTableColumn>
      <ElTableColumn label="工单号" min-width="170">
        <template #default="{ row }"><strong>工单{{ row.work_order_no }}</strong></template>
      </ElTableColumn>
      <ElTableColumn prop="supplier_name" label="供应商" min-width="130" />
      <ElTableColumn prop="supplier_process_name" label="工艺" min-width="130" />
      <ElTableColumn label="状态" min-width="110">
        <template #default="{ row }">
          <ElTag :type="taskStatus(row).type" effect="light" size="small">
            {{ taskStatus(row).label }}
          </ElTag>
        </template>
      </ElTableColumn>
      <ElTableColumn label="操作" min-width="150">
        <template #default="{ row }">
          <div class="table-actions">
            <ElButton type="primary" link @click="openInspection(row)">录入</ElButton>
            <ElButton link @click="openDetail(row)">查看</ElButton>
          </div>
        </template>
      </ElTableColumn>
    </ElTable>
    <SupplierProcessingQcInspectionDialog
      v-model="dialogVisible"
      :task="activeTask"
      :workers="workers"
      :submitting="submitting"
      @submit="saveInspection"
    />
    <SupplierProcessingQcDrawer
      v-model="detailVisible"
      :task="detailTask"
      :releasing-batch-id="releasingBatchId"
      :undoing-batch-id="undoingBatchId"
      @release="release"
      @undo-inspection="undoInspection"
    />
  </section>
</template>

<style scoped>
.supplier-qc-panel { min-height: 300px; }
.panel-heading { display: flex; align-items: center; justify-content: space-between; gap: 16px; }
.panel-heading { margin-bottom: 16px; }
.panel-heading h2 { margin: 0; font-size: 20px; }
.panel-heading p { margin: 5px 0 0; color: var(--el-text-color-secondary); font-size: 13px; }
.panel-heading > span { color: var(--el-text-color-secondary); font-size: 13px; }
.table-actions { display: flex; flex-wrap: wrap; gap: 8px; }
.table-actions :deep(.el-button) { margin: 0; }
@media (max-width: 640px) {
  .panel-heading { align-items: stretch; flex-direction: column; }
}
</style>
