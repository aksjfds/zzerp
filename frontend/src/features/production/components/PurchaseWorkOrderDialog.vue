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
    repositoryId: number
    procedureId: number | null
    procedureName: string | null
    quantity: number
    workerId: number | null
    remark: string
  }]
}>()
const form = reactive({
  procedure: null as number | string | null,
  quantity: 1,
  workerId: null as number | null,
  remark: '',
})

watch(() => props.modelValue, (visible) => {
  if (!visible) return
  form.procedure = props.item?.available_procedures[0]?.id ?? null
  form.quantity = props.item?.available_quantity || 1
  form.workerId = null
  form.remark = ''
})

function submit() {
  const item = props.item
  const maximum = item?.available_quantity || 0
  if (!item?.repository_id || form.quantity < 1 || form.quantity > maximum) {
    ElMessage.warning('外购数量超过当前可用数量')
    return
  }
  if (form.procedure === null || (typeof form.procedure === 'string' && !form.procedure.trim())) {
    ElMessage.warning('请选择已有工艺或输入新工艺')
    return
  }
  emit('submit', {
    repositoryId: item.repository_id,
    procedureId: typeof form.procedure === 'number' ? form.procedure : null,
    procedureName: typeof form.procedure === 'string' ? form.procedure.trim() : null,
    quantity: form.quantity,
    workerId: form.workerId,
    remark: form.remark.trim(),
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
      {{ item?.part_no }} - {{ item?.part_name }} · {{ item?.workshop_name }}
    </p>
    <ElForm label-width="96px">
      <ElFormItem label="外购工艺" required>
        <ElSelect v-model="form.procedure" filterable allow-create default-first-option placeholder="选择已有工艺或输入新工艺">
          <ElOption
            v-for="procedure in item?.available_procedures || []"
            :key="procedure.id"
            :label="procedure.procedure_name"
            :value="procedure.id"
          />
        </ElSelect>
      </ElFormItem>
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
      <ElFormItem label="备注">
        <ElInput v-model="form.remark" type="textarea" :rows="3" maxlength="1000" show-word-limit placeholder="填写外购工单备注（可选）" />
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
