<script setup lang="ts">
import { reactive, watch } from 'vue'
import { ElMessage } from 'element-plus'
import type { RepositoryItem, WorkerItem } from '../domain/types'

const props = defineProps<{
  modelValue: boolean
  item?: RepositoryItem
  workers: WorkerItem[]
  submitting: boolean
}>()
const emit = defineEmits<{
  'update:modelValue': [value: boolean]
  submit: [payload: { quantity: number; workerId: number | null; remark: string }]
}>()
const form = reactive({
  quantity: 1,
  workerId: null as number | null,
  remark: '',
})

watch(() => props.modelValue, (visible) => {
  if (!visible) return
  form.quantity = props.item?.available_quantity || 1
  form.workerId = null
  form.remark = ''
})

function submit() {
  const maximum = props.item?.available_quantity || 0
  if (form.quantity < 1 || form.quantity > maximum) {
    ElMessage.warning('装配数量超过当前可装配数量')
    return
  }
  emit('submit', {
    quantity: form.quantity,
    workerId: form.workerId,
    remark: form.remark.trim(),
  })
}
</script>

<template>
  <ElDialog
    :model-value="modelValue"
    title="开装配工单"
    width="500px"
    @update:model-value="emit('update:modelValue', $event)"
  >
    <p class="target">
      {{ item?.part_no }} - {{ item?.part_name }} · {{ item?.procedure_name }}
    </p>
    <ElForm label-width="96px">
      <ElFormItem label="工单数量">
        <ElInputNumber
          v-model="form.quantity"
          :min="1"
          :max="item?.available_quantity || 1"
        />
      </ElFormItem>
      <ElFormItem label="执行工人">
        <ElSelect v-model="form.workerId" placement="top-start" :fallback-placements="['top-start', 'top-end']" clearable placeholder="暂不分配工人">
          <ElOption
            v-for="worker in workers"
            :key="worker.id"
            :label="worker.worker_name"
            :value="worker.id"
          />
        </ElSelect>
      </ElFormItem>
      <ElFormItem label="备注">
        <ElInput v-model="form.remark" type="textarea" :rows="3" maxlength="1000" show-word-limit placeholder="填写装配工单备注（可选）" />
      </ElFormItem>
    </ElForm>
    <template #footer>
      <ElButton @click="emit('update:modelValue', false)">取消</ElButton>
      <ElButton type="primary" :loading="submitting" @click="submit">
        创建工单
      </ElButton>
    </template>
  </ElDialog>
</template>

<style scoped>
.target { margin: 0 0 18px; color: var(--el-text-color-secondary); }
.el-select { width: 100%; }
</style>
