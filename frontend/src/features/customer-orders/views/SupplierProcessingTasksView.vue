<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { getApiErrorDetail } from '@/api/request'
import { SUPPLIER_PROCESSING_PERMISSIONS } from '@/permission/constants'
import SupplierProcessingWorkOrderDialog from '../components/SupplierProcessingWorkOrderDialog.vue'
import {
  createSupplierProcessingWorkOrder,
  cancelSupplierProcessingWorkOrder,
  querySupplierProcessingTasks,
} from '../api/supplierProcessing'
import type {
  SupplierProcessingTask,
  SupplierProcessingWorkOrderInput,
} from '../domain/supplierProcessing'

const tasks = ref<SupplierProcessingTask[]>([])
const total = ref(0)
const loading = ref(false)
const submitting = ref(false)
const dialogVisible = ref(false)
const activeTask = ref<SupplierProcessingTask>()

const statusLabels = {
  open: '加工中',
  closed: '已结单',
  cancelled: '已取消',
} as const

function workOrderStatusLabel(task: SupplierProcessingTask) {
  return task.work_order_status ? statusLabels[task.work_order_status] : '未开单'
}

function workOrderStatusType(task: SupplierProcessingTask) {
  if (task.work_order_status === 'closed') return 'success'
  if (task.work_order_status === 'cancelled') return 'info'
  return task.work_order_status === 'open' ? 'warning' : 'info'
}

async function load() {
  if (loading.value) return
  loading.value = true
  try {
    const result = await querySupplierProcessingTasks()
    tasks.value = result.items
    total.value = result.total
  } catch (error) {
    ElMessage.error(getApiErrorDetail(error)?.message || '委外加工任务加载失败')
  } finally {
    loading.value = false
  }
}

function openCreateDialog(task: SupplierProcessingTask) {
  activeTask.value = task
  dialogVisible.value = true
}

async function submit(payload: SupplierProcessingWorkOrderInput) {
  submitting.value = true
  try {
    await createSupplierProcessingWorkOrder(payload)
    dialogVisible.value = false
    activeTask.value = undefined
    await load()
    ElMessage.success('委外加工工单已创建')
  } catch (error) {
    ElMessage.error(getApiErrorDetail(error)?.message || '委外加工工单创建失败')
  } finally {
    submitting.value = false
  }
}

async function cancelWorkOrder(task: SupplierProcessingTask) {
  if (!task.work_order_id) return
  try {
    await ElMessageBox.confirm(
      '仅尚未录入任何质检结果的委外工单可以取消。取消后可重新创建，是否继续？',
      '取消委外工单',
      { type: 'warning', confirmButtonText: '确认取消' },
    )
    await cancelSupplierProcessingWorkOrder(task.work_order_id)
    await load()
    ElMessage.success('委外加工工单已取消')
  } catch (error) {
    if (error !== 'cancel' && error !== 'close') {
      ElMessage.error(getApiErrorDetail(error)?.message || '委外加工工单取消失败')
    }
  }
}

onMounted(load)
defineExpose({ load })
</script>

<template>
  <section class="supplier-tasks-view">
    <div class="view-heading">
      <div>
        <h2>委外加工任务</h2>
        <p>生产计划确认后可创建一次委外工单；任务数量由生产计划确定。</p>
      </div>
      <div class="heading-actions">
        <span>共 {{ total }} 项</span>
        <ElButton :loading="loading" @click="load">刷新</ElButton>
      </div>
    </div>
    <ElTable
      v-table-column-widths="'sales.supplier-processing-tasks'"
      v-loading="loading"
      :data="tasks"
      border
      stripe
      table-layout="auto"
    >
      <ElTableColumn prop="item_code" label="物料编号" min-width="150" />
      <ElTableColumn prop="item_name" label="配件名称" min-width="180" />
      <ElTableColumn prop="product_version" label="产品版本" min-width="100" />
      <ElTableColumn prop="task_quantity" label="任务数量" min-width="110" />
      <ElTableColumn label="工单状态" min-width="120">
        <template #default="{ row }">
          <ElTag :type="workOrderStatusType(row)">{{ workOrderStatusLabel(row) }}</ElTag>
        </template>
      </ElTableColumn>
      <ElTableColumn label="操作" min-width="120">
        <template #default="{ row }">
          <ElButton
            v-if="row.can_create_work_order"
            v-permission="SUPPLIER_PROCESSING_PERMISSIONS.create"
            link
            type="primary"
            @click="openCreateDialog(row)"
          >创建工单</ElButton>
          <ElButton
            v-else-if="row.work_order_status === 'open'"
            v-permission="SUPPLIER_PROCESSING_PERMISSIONS.create"
            link
            type="danger"
            @click="cancelWorkOrder(row)"
          >取消工单</ElButton>
          <span v-else class="operation-hint">{{ row.work_order_id ? '已创建' : '不可开单' }}</span>
        </template>
      </ElTableColumn>
    </ElTable>
    <SupplierProcessingWorkOrderDialog
      v-model="dialogVisible"
      :task="activeTask"
      :submitting="submitting"
      @submit="submit"
    />
  </section>
</template>

<style scoped>
.supplier-tasks-view { min-width: 0; }
.view-heading, .heading-actions { display: flex; align-items: center; justify-content: space-between; gap: 16px; }
.view-heading { margin-bottom: 16px; }
.view-heading h2 { margin: 0; font-size: 20px; }
.view-heading p { margin: 5px 0 0; color: var(--el-text-color-secondary); font-size: 13px; }
.heading-actions span, .operation-hint { color: var(--el-text-color-secondary); font-size: 13px; }
@media (max-width: 680px) {
  .view-heading { align-items: stretch; flex-direction: column; }
}
</style>
