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
  submit: [payload: {
    repositoryId: number | null
    tagStockId: null
    quantity: number
    workerId: number | null
    tagNames: string[]
  }]
}>()
const form = reactive({
  quantity: 1,
  workerId: null as number | null,
})

watch(() => props.modelValue, (visible) => {
  if (!visible) return
  form.quantity = props.item?.available_quantity || 1
  form.workerId = null
})

function submit() {
  const item = props.item
  const maximum = item?.available_quantity || 0
  if (!item?.repository_id || form.quantity < 1 || form.quantity > maximum) {
    ElMessage.warning('外购数量超过当前可用数量')
    return
  }
  emit('submit', {
    repositoryId: item.repository_id,
    tagStockId: null,
    quantity: form.quantity,
    workerId: form.workerId,
    tagNames: [],
  })
}
</script>

<template>
  <ElDialog
    :model-value="modelValue"
    title="创建外购入库单"
    width="500px"
    @update:model-value="emit('update:modelValue', $event)"
  >
    <p class="target">
      {{ item?.part_no }} - {{ item?.part_name }} · {{ item?.procedure_name }}
    </p>
    <ElForm label-width="96px">
      <ElFormItem label="外购数量">
        <ElInputNumber
          v-model="form.quantity"
          :min="1"
          :max="item?.available_quantity || 1"
        />
      </ElFormItem>
      <ElFormItem label="经办人">
        <ElSelect v-model="form.workerId" placement="top-start" :fallback-placements="['top-start', 'top-end']" clearable placeholder="暂不分配经办人">
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
      <ElButton type="primary" :loading="submitting" @click="submit">
        创建外购单
      </ElButton>
    </template>
  </ElDialog>
</template>

<style scoped>
.target { margin: 0 0 18px; color: var(--el-text-color-secondary); }
.el-select { width: 100%; }
</style>
