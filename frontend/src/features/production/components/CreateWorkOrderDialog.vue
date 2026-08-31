<script setup lang="ts">
import { computed, reactive, watch } from 'vue'
import { ElMessage } from 'element-plus'
import type { WorkerItem } from '../domain/types'
import type { WorkOrderCreationTarget } from '../domain/workOrderCreation'

const props = defineProps<{
  modelValue: boolean
  item?: WorkOrderCreationTarget
  workers: WorkerItem[]
  submitting: boolean
}>()
const emit = defineEmits<{
  'update:modelValue': [value: boolean]
  submit: [payload: {
    repositoryId: number
    procedureId: number | null
    procedureName: string | null
    isTemporary: boolean
    quantity: number
    workerId: number | null
    remark: string
  }]
}>()
const form = reactive({
  procedureId: null as number | null,
  temporaryProcedureName: '',
  isTemporary: false,
  quantity: 1,
  workerId: null as number | null,
  remark: '',
})
const maximumQuantity = computed(() => props.item?.available_quantity || 1)

watch(() => props.modelValue, (visible) => {
  if (!visible) return
  form.procedureId = props.item?.available_procedures[0]?.id ?? null
  form.temporaryProcedureName = ''
  form.isTemporary = false
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
  if (!form.isTemporary && form.procedureId === null) {
    ElMessage.warning('请选择已配置工艺')
    return
  }
  const temporaryName = form.temporaryProcedureName.trim()
  if (form.isTemporary && !temporaryName) {
    ElMessage.warning('请填写临时工艺名称')
    return
  }
  if (form.isTemporary && props.item?.available_procedures.some(item => item.procedure_name === temporaryName)) {
    ElMessage.warning('该工艺已在正式配置中，请创建普通工单')
    return
  }
  if (form.quantity < 1 || form.quantity > maximumQuantity.value) {
    ElMessage.warning('工单数量超过当前可用数量')
    return
  }
  emit('submit', {
    repositoryId: item.repository_id,
    procedureId: form.isTemporary ? null : form.procedureId,
    procedureName: form.isTemporary ? temporaryName : null,
    isTemporary: form.isTemporary,
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
      <ElFormItem :label="form.isTemporary ? '临时工艺' : '加工工艺'" required>
        <ElSelect
          v-if="!form.isTemporary"
          v-model="form.procedureId"
          filterable
          placeholder="选择已配置工艺"
        >
          <ElOption
            v-for="procedure in item?.available_procedures || []"
            :key="procedure.id"
            :label="procedure.procedure_name"
            :value="procedure.id"
          />
        </ElSelect>
        <ElInput v-else v-model="form.temporaryProcedureName" maxlength="200" placeholder="填写配置以外的工艺" />
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
      <div class="dialog-footer">
        <ElButton plain @click="form.isTemporary = !form.isTemporary">
          {{ form.isTemporary ? '返回普通工单' : '临时工单' }}
        </ElButton>
        <div>
          <ElButton @click="emit('update:modelValue', false)">取消</ElButton>
          <ElButton type="primary" :loading="submitting" :disabled="!form.isTemporary && form.procedureId === null" @click="submit">{{ form.isTemporary ? '创建临时工单' : '创建工单' }}</ElButton>
        </div>
      </div>
    </template>
  </ElDialog>
</template>

<style scoped>
.target { margin: 0 0 18px; color: var(--el-text-color-secondary); }
.target-combination { overflow-wrap: anywhere; }
.el-select { width: 100%; }
.dialog-footer { display: flex; justify-content: space-between; gap: 12px; width: 100%; }
</style>
