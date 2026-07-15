<script setup lang="ts">
import { reactive, watch } from 'vue'
import type { RepositoryItem, WorkerItem } from '../domain/types'

const props = withDefaults(defineProps<{
  modelValue: boolean
  item?: RepositoryItem
  workers: WorkerItem[]
  submitting: boolean
  mode?: 'production' | 'purchase'
}>(), { mode: 'production' })
const emit = defineEmits<{
  'update:modelValue': [value: boolean]
  submit: [payload: { quantity: number; workerId: number | null }]
}>()
const form = reactive({ quantity: 1, workerId: null as number | null })

watch(() => props.modelValue, (visible) => {
  if (visible) {
    form.quantity = props.item?.available_quantity || 1
    form.workerId = null
  }
})
</script>

<template>
  <ElDialog
    :model-value="modelValue"
    :title="props.mode === 'purchase' ? '创建外购入库单' : '开工艺工单'"
    width="460px"
    @update:model-value="emit('update:modelValue', $event)"
  >
    <p class="target">{{ item?.part_no }} - {{ item?.part_name }} · {{ item?.procedure_name }}</p>
    <ElForm label-width="80px">
      <ElFormItem :label="props.mode === 'purchase' ? '外购数量' : '工单数量'">
        <ElInputNumber v-model="form.quantity" :min="1" :max="item?.available_quantity || 1" />
      </ElFormItem>
      <ElFormItem :label="props.mode === 'purchase' ? '经办人' : '执行工人'">
        <ElSelect v-model="form.workerId" clearable placeholder="暂不分配工人">
          <ElOption
            v-for="worker in workers"
            :key="worker.id"
            :label="worker.worker_name"
            :value="worker.id"
          />
        </ElSelect>
      </ElFormItem>
    </ElForm>
    <template #footer>
      <ElButton @click="emit('update:modelValue', false)">取消</ElButton>
      <ElButton
        type="primary"
        :loading="submitting"
        @click="emit('submit', { quantity: form.quantity, workerId: form.workerId })"
      >{{ props.mode === 'purchase' ? '创建外购单' : '创建工单' }}</ElButton>
    </template>
  </ElDialog>
</template>

<style scoped>
.target { margin: 0 0 18px; color: var(--el-text-color-secondary); }
.el-select { width: 100%; }
</style>
