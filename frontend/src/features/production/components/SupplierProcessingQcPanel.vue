<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { getApiErrorDetail } from '@/api/request'
import {
  inspectSupplierProcessingWorkOrder,
  querySupplierProcessingQcTasks,
  releaseSupplierProcessingBatch,
  undoQcInspection,
  undoQcDestination,
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
const activeView = ref<'active' | 'history'>('active')
const loading = ref(false)
const submitting = ref(false)
const releasingBatchId = ref<number | null>(null)
const undoingBatchId = ref<number | null>(null)
const dialogVisible = ref(false)
const activeTask = ref<SupplierProcessingQcTask>()
const detailTask = ref<SupplierProcessingQcTask>()
const detailVisible = ref(false)
let loadRevision = 0
const releaseCandidatesByWorkOrderId = computed(() => new Map(
  tasks.value.map(task => [
    task.work_order_id,
    task.batches.filter(batch => (
      batch.recorded_at
      && (batch.qualified_quantity || 0) > 0
      && !batch.qualified_destination
    )),
  ]),
))

async function load() {
  const revision = ++loadRevision
  const history = activeView.value === 'history'
  loading.value = true
  try {
    const result = await querySupplierProcessingQcTasks(history)
    if (revision !== loadRevision) return
    tasks.value = result.items
    if (detailTask.value) {
      detailTask.value = result.items.find(
        task => task.work_order_id === detailTask.value?.work_order_id,
      )
      if (!detailTask.value) detailVisible.value = false
    }
  } catch (error) {
    if (revision === loadRevision) {
      ElMessage.error(getApiErrorDetail(error)?.message || '委外加工质检任务加载失败')
    }
  } finally {
    if (revision === loadRevision) loading.value = false
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

function selectView(value: unknown) {
  if (value !== 'active' && value !== 'history') return
  activeView.value = value
  detailVisible.value = false
  detailTask.value = undefined
  void load()
}

function releasableBatches(task: SupplierProcessingQcTask) {
  return releaseCandidatesByWorkOrderId.value.get(task.work_order_id) || []
}

function batchSequence(task: SupplierProcessingQcTask, batch: WorkOrderBatch) {
  return task.batches.findIndex(item => item.id === batch.id) + 1
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

async function release(task: SupplierProcessingQcTask, batch: WorkOrderBatch) {
  try {
    await ElMessageBox.confirm(
      `确认将本批 ${batch.qualified_quantity || 0} 件合格品放行至「${task.release_target_name || '未配置下一节点'}」？尚未被下游使用时可以撤回。`,
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
  if (task.status === 'cancelled') return { label: '已取消', type: 'info' as const }
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

async function undoRelease(batch: WorkOrderBatch) {
  try {
    await ElMessageBox.confirm(
      '仅该批合格品尚未被后续工单或成品入库使用时可以撤回放行。',
      '撤回放行',
      { type: 'warning', confirmButtonText: '确认撤回', cancelButtonText: '取消' },
    )
    undoingBatchId.value = batch.id
    await undoQcDestination(batch.id)
    await load()
    ElMessage.success('委外加工放行已撤回')
  } catch (error) {
    if (error !== 'cancel' && error !== 'close') {
      ElMessage.error(getApiErrorDetail(error)?.message || '委外加工放行撤回失败')
    }
  } finally {
    undoingBatchId.value = null
  }
}

onMounted(refresh)
defineExpose({ refresh })
</script>

<template>
  <section v-loading="loading" class="supplier-qc-panel">
    <div class="qc-filter-bar">
      <ElSegmented
        :model-value="activeView"
        :options="[
          { label: '待处理', value: 'active' },
          { label: '历史记录', value: 'history' },
        ]"
        aria-label="委外质检状态"
        @update:model-value="selectView"
      />
    </div>
    <ElTable
      v-table-column-widths="'production.supplier-processing-qc'"
      :data="tasks"
      row-key="work_order_id"
      border
      stripe
      table-layout="auto"
      :empty-text="activeView === 'history' ? '暂无委外加工历史记录' : '暂无待处理委外加工工单'"
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
      <ElTableColumn label="操作" min-width="210">
        <template #default="{ row }">
          <div class="table-actions">
            <ElButton v-if="activeView === 'active'" type="primary" link @click="openInspection(row)">录入</ElButton>
            <ElButton link @click="openDetail(row)">查看</ElButton>
            <ElButton
              v-if="activeView === 'active' && releasableBatches(row).length === 1"
              type="primary"
              link
              :loading="releasingBatchId === releasableBatches(row)[0]?.id"
              :disabled="releasingBatchId !== null && releasingBatchId !== releasableBatches(row)[0]?.id"
              @click="release(row, releasableBatches(row)[0]!)"
            >放行</ElButton>
            <ElPopover
              v-else-if="activeView === 'active' && releasableBatches(row).length > 1"
              placement="bottom-end"
              trigger="click"
              :width="320"
            >
              <template #reference>
                <ElButton type="primary" link>放行（{{ releasableBatches(row).length }}批）</ElButton>
              </template>
              <div class="release-batch-list">
                <div v-for="batch in releasableBatches(row)" :key="batch.id" class="release-batch-item">
                  <span>质检批次 {{ batchSequence(row, batch) }} · 合格 {{ batch.qualified_quantity }}</span>
                  <ElButton
                    type="primary"
                    link
                    :loading="releasingBatchId === batch.id"
                    :disabled="releasingBatchId !== null && releasingBatchId !== batch.id"
                    @click="release(row, batch)"
                  >放行</ElButton>
                </div>
              </div>
            </ElPopover>
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
      :undoing-batch-id="undoingBatchId"
      @undo-inspection="undoInspection"
      @undo-release="undoRelease"
    />
  </section>
</template>

<style scoped>
.supplier-qc-panel { min-height: 300px; }
.qc-filter-bar { display: flex; margin-bottom: 14px; }
.table-actions { display: flex; flex-wrap: wrap; gap: 8px; }
.table-actions :deep(.el-button) { margin: 0; }
.release-batch-list { display: grid; gap: 8px; }
.release-batch-item { display: flex; align-items: center; justify-content: space-between; gap: 12px; }
</style>
