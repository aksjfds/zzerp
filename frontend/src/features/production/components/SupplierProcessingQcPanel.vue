<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { getApiErrorDetail } from '@/api/request'
import {
  inspectSupplierProcessingWorkOrder,
  querySupplierProcessingQcTasks,
  releaseSupplierProcessingBatch,
} from '../api/qc'
import type {
  SupplierProcessingQcInspectionPayload,
  SupplierProcessingQcTask,
  WorkOrderBatch,
  WorkerItem,
} from '../domain/types'
import SupplierProcessingQcInspectionDialog from './SupplierProcessingQcInspectionDialog.vue'

defineProps<{ workers: WorkerItem[] }>()

const tasks = ref<SupplierProcessingQcTask[]>([])
const total = ref(0)
const loading = ref(false)
const submitting = ref(false)
const releasingBatchId = ref<number | null>(null)
const dialogVisible = ref(false)
const activeTask = ref<SupplierProcessingQcTask>()

async function load() {
  loading.value = true
  try {
    const result = await querySupplierProcessingQcTasks()
    tasks.value = result.items
    total.value = result.total
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
      `确认放行本批 ${batch.qualified_quantity || 0} 件合格品到正式下一节点？确认后不能更改。`,
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
    <article v-for="task in tasks" :key="task.work_order_id" class="supplier-qc-card">
      <div class="card-heading">
        <div>
          <strong>{{ task.work_order_no }} · {{ task.item_code }} · {{ task.item_name }}</strong>
          <p>{{ task.supplier_name }} · {{ task.supplier_process_name }}</p>
        </div>
        <ElButton type="primary" @click="openInspection(task)">录入本次结果</ElButton>
      </div>
      <div class="progress-grid">
        <span>任务数<strong>{{ task.task_quantity }}</strong></span>
        <span>累计质检<strong>{{ task.inspected_quantity }}</strong></span>
        <span>累计合格<strong>{{ task.qualified_quantity }}</strong></span>
        <span>累计返工<strong>{{ task.rework_quantity }}</strong></span>
        <span>累计报废<strong>{{ task.scrap_quantity }}</strong></span>
        <span>累计遗失<strong>{{ task.lost_quantity }}</strong></span>
        <span>剩余待合格<strong>{{ task.remaining_qualified_quantity }}</strong></span>
        <span>待放行<strong>{{ task.pending_destination_quantity }}</strong></span>
        <span>已放行<strong>{{ task.released_quantity }}</strong></span>
      </div>
      <p v-if="task.remark" class="task-remark">备注：{{ task.remark }}</p>
      <ElTable
        v-if="task.batches.length"
        v-table-column-widths="'production.supplier-processing-qc-batches'"
        :data="task.batches"
        border
        table-layout="auto"
        class="batch-history"
      >
        <ElTableColumn prop="recorded_at" label="质检时间" min-width="160" />
        <ElTableColumn prop="qc_worker_name" label="QC 工人" min-width="110" />
        <ElTableColumn prop="submitted_quantity" label="本次质检" min-width="100" />
        <ElTableColumn prop="qualified_quantity" label="合格" min-width="80" />
        <ElTableColumn prop="rework_quantity" label="返工" min-width="80" />
        <ElTableColumn prop="scrap_quantity" label="报废" min-width="80" />
        <ElTableColumn prop="lost_quantity" label="遗失" min-width="80" />
        <ElTableColumn prop="defect_reason" label="不良原因" min-width="160" />
        <ElTableColumn label="合格品去向" min-width="130">
          <template #default="{ row }">
            <ElTag v-if="row.qualified_destination === 'release'" type="success">已放行</ElTag>
            <ElButton
              v-else-if="row.qualified_quantity"
              link
              type="primary"
              :loading="releasingBatchId === row.id"
              :disabled="releasingBatchId !== null && releasingBatchId !== row.id"
              @click="release(row)"
            >放行</ElButton>
            <span v-else class="no-release">无合格品</span>
          </template>
        </ElTableColumn>
      </ElTable>
      <ElEmpty v-else description="尚未录入质检结果" :image-size="48" />
    </article>
    <ElEmpty v-if="!loading && !tasks.length" description="暂无待处理委外加工工单" :image-size="72" />
    <SupplierProcessingQcInspectionDialog
      v-model="dialogVisible"
      :task="activeTask"
      :workers="workers"
      :submitting="submitting"
      @submit="saveInspection"
    />
  </section>
</template>

<style scoped>
.supplier-qc-panel { min-height: 300px; }
.panel-heading, .card-heading { display: flex; align-items: center; justify-content: space-between; gap: 16px; }
.panel-heading { margin-bottom: 16px; }
.panel-heading h2 { margin: 0; font-size: 20px; }
.panel-heading p, .card-heading p, .task-remark { margin: 5px 0 0; color: var(--el-text-color-secondary); font-size: 13px; }
.panel-heading > span { color: var(--el-text-color-secondary); font-size: 13px; }
.supplier-qc-card { margin-bottom: 14px; padding: 16px; border: 1px solid var(--md-outline-variant); border-radius: var(--erp-radius); background: var(--md-surface-container-lowest); }
.progress-grid { display: grid; grid-template-columns: repeat(5, minmax(90px, 1fr)); gap: 10px; margin: 14px 0; }
.progress-grid span { display: flex; flex-direction: column; gap: 4px; padding: 10px; border-radius: var(--erp-radius); background: var(--md-surface-container-low); color: var(--el-text-color-secondary); font-size: 12px; }
.progress-grid strong { color: var(--el-text-color-primary); font-size: 17px; }
.batch-history { margin-top: 14px; }
.no-release { color: var(--el-text-color-secondary); font-size: 13px; }
@media (max-width: 900px) { .progress-grid { grid-template-columns: repeat(3, 1fr); } }
@media (max-width: 640px) {
  .panel-heading, .card-heading { align-items: stretch; flex-direction: column; }
  .progress-grid { grid-template-columns: repeat(2, 1fr); }
}
</style>
