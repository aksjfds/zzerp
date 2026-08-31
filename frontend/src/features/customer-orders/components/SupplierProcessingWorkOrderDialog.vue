<script setup lang="ts">
import { reactive, watch } from 'vue'
import { ElMessage } from 'element-plus'
import type {
  SupplierProcessingTask,
  SupplierProcessingWorkOrderInput,
} from '../domain/supplierProcessing'

const props = defineProps<{
  modelValue: boolean
  task?: SupplierProcessingTask
  submitting?: boolean
}>()
const emit = defineEmits<{
  'update:modelValue': [value: boolean]
  submit: [payload: SupplierProcessingWorkOrderInput]
}>()

const form = reactive({
  supplier_name: '',
  supplier_process_name: '',
  remark: '',
})

watch(() => [props.modelValue, props.task] as const, ([visible, task]) => {
  if (!visible || !task) return
  Object.assign(form, {
    supplier_name: '',
    supplier_process_name: '',
    remark: '',
  })
})

function submit() {
  const task = props.task
  if (!task) return
  const supplierName = form.supplier_name.trim()
  const processName = form.supplier_process_name.trim()
  if (!supplierName) {
    ElMessage.warning('请填写供应商')
    return
  }
  if (!processName) {
    ElMessage.warning('请填写加工工艺')
    return
  }
  emit('submit', {
    production_plan_item_id: task.production_plan_item_id,
    supplier_flow_node_id: task.supplier_flow_node_id,
    supplier_name: supplierName,
    supplier_process_name: processName,
    remark: form.remark.trim() || null,
  })
}
</script>

<template>
  <ElDialog
    :model-value="modelValue"
    title="创建委外加工工单"
    width="520px"
    destroy-on-close
    @update:model-value="emit('update:modelValue', $event)"
  >
    <div v-if="task" class="task-summary">
      <strong>{{ task.item_code }} · {{ task.item_name }}</strong>
      <span>任务数量：{{ task.task_quantity }}</span>
    </div>
    <ElForm label-position="top">
      <ElFormItem label="供应商" required>
        <ElInput v-model="form.supplier_name" maxlength="200" placeholder="填写本张工单的供应商" />
      </ElFormItem>
      <ElFormItem label="加工工艺" required>
        <ElInput v-model="form.supplier_process_name" maxlength="200" placeholder="填写本张工单的加工工艺" />
      </ElFormItem>
      <ElFormItem label="备注">
        <ElInput v-model="form.remark" type="textarea" :rows="3" maxlength="1000" show-word-limit />
      </ElFormItem>
    </ElForm>
    <template #footer>
      <ElButton @click="emit('update:modelValue', false)">取消</ElButton>
      <ElButton type="primary" :loading="submitting" @click="submit">创建工单</ElButton>
    </template>
  </ElDialog>
</template>

<style scoped>
.task-summary {
  display: flex;
  justify-content: space-between;
  gap: 16px;
  margin-bottom: 18px;
  padding: 12px 14px;
  border-radius: var(--erp-radius);
  background: var(--md-surface-container-low);
}
.task-summary span { color: var(--el-text-color-secondary); }
</style>
