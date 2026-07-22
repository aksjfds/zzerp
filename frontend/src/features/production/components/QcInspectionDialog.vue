<script setup lang="ts">
import { reactive, watch } from 'vue'
import { ElMessage } from 'element-plus'
import type { PendingQcBatch, QcInspectionPayload, WorkerItem } from '../domain/types'

const props = defineProps<{
  modelValue: boolean
  batch?: PendingQcBatch
  workers: WorkerItem[]
  submitting?: boolean
}>()
const emit = defineEmits<{
  'update:modelValue': [value: boolean]
  submit: [payload: QcInspectionPayload]
}>()
const inspection = reactive<QcInspectionPayload>({
  qc_worker_id: 0,
  qualified_quantity: 0,
  rework_quantity: 0,
  scrap_quantity: 0,
  lost_quantity: 0,
  defect_reason: '',
})

watch(() => [props.modelValue, props.batch] as const, ([visible, batch]) => {
  if (!visible || !batch) return
  Object.assign(inspection, {
    qc_worker_id: 0,
    qualified_quantity: batch.submitted_quantity,
    rework_quantity: 0,
    scrap_quantity: 0,
    lost_quantity: 0,
    defect_reason: '',
  })
})

function submit() {
  if (!props.batch) return
  if (!inspection.qc_worker_id) {
    ElMessage.warning('请选择 QC 工人')
    return
  }
  const total = inspection.qualified_quantity + inspection.rework_quantity
    + inspection.scrap_quantity + inspection.lost_quantity
  if (total !== props.batch.submitted_quantity) {
    ElMessage.warning('质检结果合计必须等于送检数量')
    return
  }
  const abnormalQuantity = inspection.rework_quantity
    + inspection.scrap_quantity + inspection.lost_quantity
  if (abnormalQuantity > 0 && !inspection.defect_reason.trim()) {
    ElMessage.warning('存在返工、报废或遗失数量时必须填写不良原因')
    return
  }
  emit('submit', { ...inspection })
}
</script>

<template>
  <ElDialog :model-value="modelValue" title="录入 QC 结果" width="520px" @update:model-value="emit('update:modelValue', $event)">
    <p class="inspection-title">{{ batch?.work_order_name }} · 送检数量：{{ batch?.submitted_quantity }}</p>
    <ElFormItem label="QC 工人" required>
      <ElSelect v-model="inspection.qc_worker_id" placement="top-start" :fallback-placements="['top-start', 'top-end']" placeholder="请选择 QC 工人" style="width: 100%">
        <ElOption v-for="worker in workers" :key="worker.id" :label="worker.worker_name" :value="worker.id" />
      </ElSelect>
    </ElFormItem>
    <div class="inspection-grid">
      <ElFormItem label="合格"><ElInputNumber v-model="inspection.qualified_quantity" :min="0" /></ElFormItem>
      <ElFormItem label="返工"><ElInputNumber v-model="inspection.rework_quantity" :min="0" /></ElFormItem>
      <ElFormItem label="报废"><ElInputNumber v-model="inspection.scrap_quantity" :min="0" /></ElFormItem>
      <ElFormItem label="遗失"><ElInputNumber v-model="inspection.lost_quantity" :min="0" /></ElFormItem>
    </div>
    <ElFormItem
      label="不良原因"
      :required="inspection.rework_quantity + inspection.scrap_quantity + inspection.lost_quantity > 0"
    ><ElInput v-model="inspection.defect_reason" type="textarea" /></ElFormItem>
    <template #footer>
      <ElButton @click="emit('update:modelValue', false)">取消</ElButton>
      <ElButton type="primary" :loading="submitting" @click="submit">确认录入</ElButton>
    </template>
  </ElDialog>
</template>

<style scoped>
.inspection-title { margin-top: 0; font-weight: 700; }
.inspection-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 10px; }
</style>
