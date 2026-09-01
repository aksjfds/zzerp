<script setup lang="ts">
import { computed, ref, toRef } from 'vue'
import { useProductionProgressDetail } from '../composables/useProductionProgressDetail'
import { useAssemblyWorkOrderActions } from '../composables/useAssemblyWorkOrderActions'
import { useProductionWorkOrderActions } from '../composables/useProductionWorkOrderActions'
import type { WorkOrderSubmissionTarget } from '../composables/workOrderActionSupport'
import {
  canSubmitDirectResult,
  canSubmitInitialQc,
  commonWorkOrderActions,
} from '../domain/workOrderCardPolicy'
import type {
  DepartmentProductionProgressItem,
  ProductionProgressWorkOrder,
  ProductionTaskProcessingStatus,
} from '../domain/productionProgress'
import type { WorkOrderBatch } from '../domain/types'
import PolishWorkOrderPrintDialog from './PolishWorkOrderPrintDialog.vue'
import WorkOrderPrintDialog from './WorkOrderPrintDialog.vue'
import WorkOrderRecordCard from './WorkOrderRecordCard.vue'

const props = withDefaults(defineProps<{
  modelValue: boolean
  departmentCode: string
  item: DepartmentProductionProgressItem | null
  status: ProductionTaskProcessingStatus | null
  specialPrinting?: boolean
}>(), { specialPrinting: false })
const emit = defineEmits<{
  'update:modelValue': [value: boolean]
  changed: []
}>()

const visible = computed({
  get: () => props.modelValue,
  set: (value: boolean) => emit('update:modelValue', value),
})
const drawerRef = ref<{ handleClose: () => void } | null>(null)

function closeByContextMenu() {
  drawerRef.value?.handleClose()
}

const { detail, loading, reload } = useProductionProgressDetail(
  toRef(props, 'modelValue'),
  toRef(props, 'departmentCode'),
  toRef(props, 'item'),
)
async function refreshAfterAction() {
  await reload()
  emit('changed')
}
const productionActions = useProductionWorkOrderActions(refreshAfterAction)
const assemblyActions = useAssemblyWorkOrderActions(refreshAfterAction)
const allWorkOrders = computed(() => [
  ...new Map(
    (detail.value?.work_orders || []).map(workOrder => [workOrder.id, workOrder]),
  ).values(),
])
const relatedWorkOrderQuantities = computed(() => new Map(
  (props.status?.related_work_orders || []).map(
    item => [item.work_order_id, item.quantity],
  ),
))
const relatedBatchQuantities = computed(() => new Map(
  (props.status?.related_batches || []).map(
    item => [item.batch_id, item.quantity],
  ),
))
const relatedBatchIds = computed(() => [...relatedBatchQuantities.value.keys()])
const relatedMode = computed(() => props.status?.action === 'view_work_orders')
const exceptionMode = computed(() => props.status?.status === 'exception')
const displayedWorkOrders = computed(() => {
  if (!relatedMode.value) {
    return allWorkOrders.value
  }
  return allWorkOrders.value.filter(
    workOrder => relatedWorkOrderQuantities.value.has(workOrder.id),
  )
})
const drawerTitle = computed(() => {
  if (exceptionMode.value) return '异常情况'
  return relatedMode.value
    ? `${props.status?.label || '当前状态'}相关工单`
    : '任务全部工单'
})
const emptyDescription = computed(() => (
  exceptionMode.value
    ? '该物料暂无异常情况'
    : relatedMode.value
    ? '当前状态没有关联工单'
    : '该任务尚未创建工单'
))
const printVisible = ref(false)
const printItem = ref<ProductionProgressWorkOrder['work_order']>()

function displayedBatches(workOrder: ProductionProgressWorkOrder) {
  const batches = workOrder.work_order.batches
  if (!relatedMode.value || !relatedBatchQuantities.value.size) return batches
  return batches.filter(batch => relatedBatchQuantities.value.has(batch.id))
}

function relatedWorkOrderQuantity(workOrderId: number) {
  return relatedWorkOrderQuantities.value.get(workOrderId) || 0
}

function relatedBatchQuantity(batchId: number) {
  return relatedBatchQuantities.value.get(batchId) || 0
}

function submissionTarget(
  workOrder: ProductionProgressWorkOrder,
): WorkOrderSubmissionTarget {
  return {
    id: workOrder.id,
    work_order_no: workOrder.work_order_no,
    work_order_type: workOrder.work_order_type,
    quantity: workOrder.work_order_quantity,
    output_unit_quantity: workOrder.output_unit_quantity,
    direct_result_allowed: workOrder.direct_result_allowed,
  }
}

function submitQc(workOrder: ProductionProgressWorkOrder) {
  const actions = workOrder.work_order_type === 'assembly'
    ? assemblyActions
    : productionActions
  return actions.submitQc(submissionTarget(workOrder))
}

function submitDirectResult(workOrder: ProductionProgressWorkOrder) {
  const actions = workOrder.work_order_type === 'assembly'
    ? assemblyActions
    : productionActions
  return actions.submitDirectResult(submissionTarget(workOrder))
}

function resubmitQc(
  workOrder: ProductionProgressWorkOrder,
  batch: WorkOrderBatch,
) {
  const actions = workOrder.work_order_type === 'assembly'
    ? assemblyActions
    : productionActions
  return actions.resubmitQc(workOrder.work_order, batch)
}

function cancelWorkOrder(workOrder: ProductionProgressWorkOrder) {
  const actions = workOrder.work_order_type === 'assembly'
    ? assemblyActions
    : productionActions
  return actions.cancel(workOrder.work_order)
}

function undoWorkOrderOperation(workOrder: ProductionProgressWorkOrder) {
  const actions = workOrder.work_order_type === 'assembly'
    ? assemblyActions
    : productionActions
  return actions.undo(workOrder.work_order)
}

function openPrint(workOrder: ProductionProgressWorkOrder) {
  printItem.value = workOrder.work_order
  printVisible.value = true
}
</script>

<template>
  <ElDrawer
    ref="drawerRef"
    v-model="visible"
    :title="drawerTitle"
    size="76%"
    destroy-on-close
    modal-class="production-progress-overlay"
    class="production-progress-drawer"
    @contextmenu.prevent="closeByContextMenu"
  >
    <div v-loading="loading" class="drawer-body">
      <template v-if="detail">
        <header class="task-header">
          <div>
            <p>订单 {{ detail.customer_order_no }}</p>
            <h2>{{ detail.part_no }} · {{ detail.part_name }}</h2>
            <p>{{ detail.factory_code }} · {{ detail.product_name }}</p>
          </div>
          <div class="task-header-actions">
            <ElTag
              v-if="relatedMode"
              :type="exceptionMode ? 'danger' : 'primary'"
              effect="plain"
            >{{ status?.label }} · 合计 {{ status?.quantity }}</ElTag>
            <strong>工单 {{ displayedWorkOrders.length }} 张</strong>
          </div>
        </header>

        <section v-if="displayedWorkOrders.length" class="work-order-cards">
          <WorkOrderRecordCard
            v-for="workOrder in displayedWorkOrders"
            :key="workOrder.id"
            :record="workOrder"
            :batches="displayedBatches(workOrder)"
            :highlighted-batch-ids="relatedBatchIds"
            :exception-mode="exceptionMode"
          >
            <template #contextTag>
              <ElTag
                v-if="relatedMode"
                class="related-status"
                :type="exceptionMode ? 'danger' : 'primary'"
                effect="plain"
              >
                {{ exceptionMode ? '异常' : status?.label }} · 本工单 {{ relatedWorkOrderQuantity(workOrder.id) }}
              </ElTag>
            </template>
            <template #batchTag="{ batch }">
              <ElTag
                v-if="relatedMode && relatedBatchQuantities.has(batch.id)"
                :type="exceptionMode ? 'danger' : 'primary'"
                size="small"
                effect="plain"
              >{{ exceptionMode ? '异常' : '本状态' }} {{ relatedBatchQuantity(batch.id) }}</ElTag>
            </template>
            <template #batchActions="{ batch }">
              <footer
                v-if="!exceptionMode && commonWorkOrderActions.showReworkQc(workOrder.work_order, batch)"
                class="qc-batch-actions"
              >
                <ElButton
                  type="warning"
                  plain
                  size="small"
                  @click="resubmitQc(workOrder, batch)"
                >返工送检</ElButton>
              </footer>
            </template>
            <template #actions>
              <footer v-if="!exceptionMode" class="work-order-actions">
                <div>
                  <ElButton
                    v-if="canSubmitInitialQc(workOrder)"
                    type="warning"
                    @click="submitQc(workOrder)"
                  >送检</ElButton>
                  <ElButton
                    v-if="canSubmitDirectResult(workOrder)"
                    type="success"
                    @click="submitDirectResult(workOrder)"
                  >确认合格</ElButton>
                </div>
                <div>
                  <ElButton @click="openPrint(workOrder)">打印</ElButton>
                  <ElButton
                    v-if="commonWorkOrderActions.showUndo(workOrder.work_order)"
                    type="danger"
                    plain
                    @click="undoWorkOrderOperation(workOrder)"
                  >{{ workOrder.work_order.undo_operation?.operation_label }}</ElButton>
                  <ElButton
                    v-if="commonWorkOrderActions.showCancel(workOrder.work_order)"
                    @click="cancelWorkOrder(workOrder)"
                  >取消工单</ElButton>
                </div>
              </footer>
            </template>
          </WorkOrderRecordCard>
        </section>
        <ElEmpty v-else :description="emptyDescription" />
      </template>
      <ElEmpty v-else-if="!loading" description="工单信息未加载" />
    </div>
  </ElDrawer>
  <PolishWorkOrderPrintDialog
    v-if="specialPrinting"
    v-model="printVisible"
    :item="printItem"
  />
  <WorkOrderPrintDialog v-else v-model="printVisible" :item="printItem" />
</template>

<style scoped>
:global(.el-overlay.is-drawer.production-progress-overlay) {
  --erp-drawer-transition-duration: 300ms;
  background-color: transparent !important;
}

.drawer-body {
  min-height: 360px;
}

.task-header {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 20px;
  margin-bottom: 16px;
  padding: 16px 18px;
  border: 1px solid var(--md-outline-variant);
  border-radius: var(--erp-radius-lg);
  background: var(--md-surface-container-low);
}

.task-header h2,
.task-header p {
  margin: 0;
}

.task-header h2 {
  margin: 4px 0;
  font-size: 20px;
}

.task-header p {
  color: var(--md-on-surface-variant);
}

.task-header-actions {
  display: flex;
  align-items: flex-end;
  flex-direction: column;
  gap: 10px;
}

.related-status {
  align-self: flex-start;
}

.work-order-cards {
  display: grid;
  gap: 14px;
}

.qc-batch-actions {
  display: flex;
  justify-content: flex-end;
  margin-top: 10px;
}

.work-order-actions {
  display: flex;
  flex-wrap: wrap;
  justify-content: space-between;
  gap: 8px;
  margin-top: 16px;
  padding-top: 14px;
  border-top: 1px solid var(--md-outline-variant);
}

.work-order-actions > div {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}

.work-order-actions :deep(.el-button) {
  margin: 0;
}

@media (max-width: 680px) {
  .task-header {
    flex-direction: column;
  }
}
</style>
