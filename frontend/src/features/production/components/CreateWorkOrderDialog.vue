<script setup lang="ts">
import { computed, reactive, watch } from 'vue'
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
const maximumQuantity = computed(() => props.item?.available_quantity || 1)

watch(() => props.modelValue, (visible) => {
  if (!visible) return
  form.procedure = props.item?.available_procedures[0]?.id ?? null
  form.quantity = props.item?.available_quantity || 1
  form.workerId = null
  form.remark = ''
})

function submit() {
  const item = props.item
  if (!item?.repository_id) {
    ElMessage.warning('当前物料没有可用库存')
    return
  }
  if (form.procedure === null || (typeof form.procedure === 'string' && !form.procedure.trim())) {
    ElMessage.warning('请选择已有工艺或输入新工艺')
    return
  }
  if (form.quantity < 1 || form.quantity > maximumQuantity.value) {
    ElMessage.warning('工单数量超过当前可用数量')
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
    :title="`开${item?.workshop_name || '车间'}工单`"
    width="500px"
    @update:model-value="emit('update:modelValue', $event)"
  >
    <p class="target">{{ item?.part_no }} - {{ item?.part_name }} · {{ item?.workshop_name }}</p>
    <ElForm label-width="96px">
      <ElFormItem label="加工工艺" required>
        <ElSelect
          v-model="form.procedure"
          filterable
          allow-create
          default-first-option
          placeholder="选择已有工艺或输入新工艺"
        >
          <ElOption
            v-for="procedure in item?.available_procedures || []"
            :key="procedure.id"
            :label="procedure.procedure_name"
            :value="procedure.id"
          />
        </ElSelect>
      </ElFormItem>
      <ElFormItem label="工单数量">
        <ElInputNumber v-model="form.quantity" :min="1" :max="maximumQuantity" />
      </ElFormItem>
      <ElFormItem label="执行工人">
        <ElSelect v-model="form.workerId" clearable placeholder="暂不分配工人">
          <ElOption v-for="worker in workers" :key="worker.id" :label="worker.worker_name" :value="worker.id" />
        </ElSelect>
      </ElFormItem>
      <ElFormItem label="备注">
        <ElInput v-model="form.remark" type="textarea" :rows="3" maxlength="1000" show-word-limit placeholder="填写工单备注（可选）" />
      </ElFormItem>
    </ElForm>
    <template #footer>
      <ElButton @click="emit('update:modelValue', false)">取消</ElButton>
      <ElButton type="primary" :loading="submitting" @click="submit">创建工单</ElButton>
    </template>
  </ElDialog>
</template>

<style scoped>
.target { margin: 0 0 18px; color: var(--el-text-color-secondary); }
.target-combination { overflow-wrap: anywhere; }
.el-select { width: 100%; }
</style>
