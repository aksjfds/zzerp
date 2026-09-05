<script setup lang="ts">
import { computed, reactive, watch } from 'vue'
import { ElMessage } from 'element-plus'
import type { WorkerItem } from '../domain/types'
import type {
  AssemblyWorkOrderCreationMaterial,
  AssemblyWorkOrderCreationTarget,
} from '../domain/workOrderCreation'

const props = defineProps<{
  modelValue: boolean
  item?: AssemblyWorkOrderCreationTarget
  workers: WorkerItem[]
  submitting: boolean
}>()
const emit = defineEmits<{
  'update:modelValue': [value: boolean]
  submit: [payload: {
    quantity: number
    materials: Array<{ repository_id: number; quantity: number }>
    procedureId: number | null
    procedureName: string | null
    isTemporary: boolean
    workerId: number | null
    remark: string
  }]
}>()
const form = reactive({
  procedureId: null as number | null,
  temporaryProcedureName: '',
  isTemporary: false,
  quantity: 1,
  materialQuantities: {} as Record<number, number>,
  workerId: null as number | null,
  remark: '',
})
const materialGroups = computed(() => {
  return props.item?.materials || []
})

function requiredQuantity(group: AssemblyWorkOrderCreationMaterial) {
  return form.quantity * group.unit_quantity
}

function allocatedQuantity(group: AssemblyWorkOrderCreationMaterial) {
  return group.sources.reduce((sum, source) => (
    sum + (form.materialQuantities[source.repository_id] || 0)
  ), 0)
}

function availableQuantity(group: AssemblyWorkOrderCreationMaterial) {
  return group.sources.reduce((sum, source) => sum + source.available_quantity, 0)
}

function allocateDefault() {
  const allocations: Record<number, number> = {}
  materialGroups.value.forEach((group) => {
    let remaining = requiredQuantity(group)
    group.sources.forEach((source) => {
      const allocated = Math.min(source.available_quantity, remaining)
      allocations[source.repository_id] = allocated
      remaining -= allocated
    })
  })
  form.materialQuantities = allocations
}

watch(() => props.modelValue, (visible) => {
  if (!visible) return
  form.quantity = props.item?.available_quantity || 1
  form.procedureId = props.item?.available_procedures[0]?.id ?? null
  form.temporaryProcedureName = ''
  form.isTemporary = false
  allocateDefault()
  form.workerId = null
  form.remark = ''
})

function updateQuantity(value?: number) {
  form.quantity = value || 1
  allocateDefault()
}

function submit() {
  const maximum = props.item?.available_quantity || 0
  if (form.quantity < 1 || form.quantity > maximum) {
    ElMessage.warning('工单数量超过当前可生产数量')
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
  for (const group of materialGroups.value) {
    const required = requiredQuantity(group)
    const allocated = allocatedQuantity(group)
    if (allocated !== required) {
      ElMessage.warning(`${group.item_name}的各来源合计必须为 ${required}`)
      return
    }
  }
  emit('submit', {
    quantity: form.quantity,
    procedureId: form.isTemporary ? null : form.procedureId,
    procedureName: form.isTemporary ? temporaryName : null,
    isTemporary: form.isTemporary,
    materials: materialGroups.value.flatMap(group => group.sources).flatMap(source => (
      [{
        repository_id: source.repository_id,
        quantity: form.materialQuantities[source.repository_id] || 0,
      }]
    )),
    workerId: form.workerId,
    remark: form.remark.trim(),
  })
}
</script>

<template>
  <ElDialog
    :model-value="modelValue"
    :title="`开${item?.workshop_name || '多路车间'}工单`"
    width="min(720px, 94vw)"
    @update:model-value="emit('update:modelValue', $event)"
  >
    <p class="target">
      {{ item?.part_no }} - {{ item?.part_name }} · {{ item?.workshop_name }}
    </p>
    <ElForm label-width="96px">
      <ElFormItem :label="form.isTemporary ? '临时工艺' : '加工工艺'" required>
        <ElSelect v-if="!form.isTemporary" v-model="form.procedureId" filterable placeholder="选择已配置工艺">
          <ElOption v-for="procedure in item?.available_procedures || []" :key="procedure.id" :label="procedure.procedure_name" :value="procedure.id" />
        </ElSelect>
        <ElInput v-else v-model="form.temporaryProcedureName" maxlength="200" placeholder="填写配置以外的工艺" />
      </ElFormItem>
      <ElFormItem label="工单数量">
        <ElInputNumber
          v-model="form.quantity"
          :min="1"
          :max="item?.available_quantity || 1"
          @update:model-value="updateQuantity"
        />
      </ElFormItem>
      <ElFormItem label="来源分配" required>
        <div class="material-groups">
          <section v-for="group in materialGroups" :key="group.material_key" class="material-group">
            <div class="material-heading">
              <div class="material-identity">
                <strong>{{ group.item_code }} {{ group.item_name }}</strong>
                <small>每件用量 {{ group.unit_quantity }}</small>
              </div>
              <ElTag
                :type="allocatedQuantity(group) === requiredQuantity(group) ? 'success' : 'danger'"
                effect="plain"
              >可用 {{ availableQuantity(group) }} / 分配 {{ allocatedQuantity(group) }}</ElTag>
            </div>
            <div class="source-list">
            </div>
          </section>
        </div>
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
      <div class="dialog-footer">
        <ElButton plain @click="form.isTemporary = !form.isTemporary">
          {{ form.isTemporary ? '返回普通工单' : '临时工单' }}
        </ElButton>
        <div>
          <ElButton @click="emit('update:modelValue', false)">取消</ElButton>
          <ElButton type="primary" :loading="submitting" :disabled="!form.isTemporary && form.procedureId === null" @click="submit">
            {{ form.isTemporary ? '创建临时工单' : '创建工单' }}
          </ElButton>
        </div>
      </div>
    </template>
  </ElDialog>
</template>

<style scoped>
.target { margin: 0 0 18px; color: var(--el-text-color-secondary); }
.el-select { width: 100%; }
.material-groups { display: grid; gap: 12px; width: 100%; }
.material-group { overflow: hidden; border: 1px solid var(--md-outline-variant); border-radius: var(--erp-radius); }
.material-heading { display: flex; align-items: center; justify-content: space-between; gap: 12px; padding: 12px 14px; background: var(--md-surface-container-low); }
.material-identity, .source-identity, .source-quantity, .source-allocation { display: flex; flex-direction: column; gap: 4px; }
.material-identity small, .source-identity span, .source-quantity span, .source-allocation > span { color: var(--el-text-color-secondary); font-size: 12px; }
.source-list { padding: 0 14px; }
.source-row { display: grid; grid-template-columns: minmax(0, 1fr) 72px 140px; gap: 16px; align-items: center; padding: 12px 0; }
.source-row + .source-row { border-top: 1px solid var(--md-outline-variant); }
.source-quantity { align-items: flex-end; }
.source-allocation { align-items: flex-end; }
.source-allocation :deep(.el-input-number) { width: 140px; }
.dialog-footer { display: flex; justify-content: space-between; gap: 12px; width: 100%; }
@media (max-width: 640px) {
  .material-heading { align-items: flex-start; flex-direction: column; }
  .source-row { grid-template-columns: minmax(0, 1fr) auto; }
  .source-allocation { grid-column: 1 / -1; align-items: stretch; }
  .source-allocation :deep(.el-input-number) { width: 100%; }
}
</style>
