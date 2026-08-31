<script setup lang="ts">
import { computed, reactive, watch } from 'vue'
import { ElMessage } from 'element-plus'
import type {
  SupplierProcessingQcInspectionPayload,
  SupplierProcessingQcTask,
  WorkerItem,
} from '../domain/types'

const props = defineProps<{
  modelValue: boolean
  task?: SupplierProcessingQcTask
  workers: WorkerItem[]
  submitting?: boolean
}>()
const emit = defineEmits<{
  'update:modelValue': [value: boolean]
  submit: [payload: SupplierProcessingQcInspectionPayload]
}>()

const inspection = reactive<SupplierProcessingQcInspectionPayload>({
  qc_worker_id: 0,
  qualified_quantity: 0,
  rework_quantity: 0,
  scrap_quantity: 0,
  lost_quantity: 0,
  defect_reason: '',
})
const inspectedThisTime = computed(() => (
  inspection.qualified_quantity
  + inspection.rework_quantity
  + inspection.scrap_quantity
  + inspection.lost_quantity
))

watch(() => [props.modelValue, props.task] as const, ([visible, task]) => {
  if (!visible || !task) return
  Object.assign(inspection, {
    qc_worker_id: 0,
    qualified_quantity: 0,
    rework_quantity: 0,
    scrap_quantity: 0,
    lost_quantity: 0,
    defect_reason: '',
  })
})

function submit() {
  if (!inspection.qc_worker_id) {
    ElMessage.warning('请选择 QC 工人')
    return
  }
  if (inspectedThisTime.value <= 0) {
    ElMessage.warning('本次质检结果数量必须大于 0')
    return
  }
  if (inspection.qualified_quantity > (props.task?.remaining_qualified_quantity || 0)) {
    ElMessage.warning('本次合格数量不能超过剩余待合格数量')
    return
  }
  const abnormalQuantity = inspection.rework_quantity
    + inspection.scrap_quantity + inspection.lost_quantity
  if (abnormalQuantity > 0 && !inspection.defect_reason.trim()) {
    ElMessage.warning('存在返工、报废或遗失数量时必须填写不良原因')
    return
  }
  emit('submit', {
    ...inspection,
    defect_reason: inspection.defect_reason.trim(),
  })
}
</script>

<template>
  <ElDialog
    :model-value="modelValue"
    title="录入委外加工 QC 结果"
    width="560px"
    destroy-on-close
    @update:model-value="emit('update:modelValue', $event)"
  >
    <div v-if="task" class="task-summary">
      <strong>{{ task.item_code }} · {{ task.item_name }}</strong>
      <span>剩余待合格：{{ task.remaining_qualified_quantity }}</span>
    </div>
    <ElForm label-position="top">
      <ElFormItem label="QC 工人" required>
        <ElSelect v-model="inspection.qc_worker_id" placeholder="请选择 QC 工人" style="width: 100%">
          <ElOption v-for="worker in workers" :key="worker.id" :label="worker.worker_name" :value="worker.id" />
        </ElSelect>
      </ElFormItem>
      <div class="inspection-grid">
        <ElFormItem label="合格"><ElInputNumber v-model="inspection.qualified_quantity" :min="0" /></ElFormItem>
        <ElFormItem label="返工"><ElInputNumber v-model="inspection.rework_quantity" :min="0" /></ElFormItem>
        <ElFormItem label="报废"><ElInputNumber v-model="inspection.scrap_quantity" :min="0" /></ElFormItem>
        <ElFormItem label="遗失"><ElInputNumber v-model="inspection.lost_quantity" :min="0" /></ElFormItem>
      </div>
      <p class="result-total">本次质检：{{ inspectedThisTime }} 件</p>
      <ElFormItem label="不良原因" :required="inspection.rework_quantity + inspection.scrap_quantity + inspection.lost_quantity > 0">
        <ElInput v-model="inspection.defect_reason" type="textarea" :rows="3" maxlength="1000" />
      </ElFormItem>
    </ElForm>
    <template #footer>
      <ElButton @click="emit('update:modelValue', false)">取消</ElButton>
      <ElButton type="primary" :loading="submitting" @click="submit">确认录入</ElButton>
    </template>
  </ElDialog>
</template>

<style scoped>
.task-summary { display: flex; justify-content: space-between; gap: 16px; margin-bottom: 18px; padding: 12px 14px; border-radius: var(--erp-radius); background: var(--md-surface-container-low); }
.task-summary span, .result-total { color: var(--el-text-color-secondary); }
.inspection-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 10px; }
.result-total { margin: -2px 0 16px; font-size: 13px; }
@media (max-width: 560px) { .inspection-grid { grid-template-columns: 1fr; } }
</style>
