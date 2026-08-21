<script setup lang="ts">
import { computed, reactive, watch } from 'vue'
import { ElMessage } from 'element-plus'
import type { RepositoryItem, WorkerItem } from '../domain/types'

const props = defineProps<{
  modelValue: boolean
  item?: RepositoryItem
  materials: RepositoryItem[]
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
    workerId: number | null
    remark: string
  }]
}>()
const form = reactive({
  procedure: null as number | string | null,
  quantity: 1,
  materialQuantities: {} as Record<number, number>,
  workerId: null as number | null,
  remark: '',
})
const materialGroups = computed(() => {
  const groups = new Map<string, RepositoryItem[]>()
  props.materials.forEach((material) => {
    if (material.repository_id === null) return
    groups.set(
      material.assembly_material_key,
      [...(groups.get(material.assembly_material_key) || []), material],
    )
  })
  return [...groups.entries()].map(([key, sources]) => ({
    key,
    name: sources[0]?.part_name || '物料',
    requiredUnit: sources[0]?.assembly_unit_quantity || 1,
    sources,
  }))
})

function allocateDefault() {
  const allocations: Record<number, number> = {}
  materialGroups.value.forEach((group) => {
    let remaining = form.quantity * group.requiredUnit
    group.sources.forEach((source) => {
      if (source.repository_id === null) return
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
  form.procedure = props.item?.available_procedures[0]?.id ?? null
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
  if (form.procedure === null || (typeof form.procedure === 'string' && !form.procedure.trim())) {
    ElMessage.warning('请选择已有工艺或输入新工艺')
    return
  }
  for (const group of materialGroups.value) {
    const required = form.quantity * group.requiredUnit
    const allocated = group.sources.reduce((sum, source) => (
      sum + (source.repository_id === null ? 0 : form.materialQuantities[source.repository_id] || 0)
    ), 0)
    if (allocated !== required) {
      ElMessage.warning(`${group.name}的各来源合计必须为 ${required}`)
      return
    }
  }
  emit('submit', {
    quantity: form.quantity,
    procedureId: typeof form.procedure === 'number' ? form.procedure : null,
    procedureName: typeof form.procedure === 'string' ? form.procedure.trim() : null,
    materials: materialGroups.value.flatMap(group => group.sources).flatMap(source => (
      source.repository_id === null
        ? []
        : [{
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
    width="600px"
    @update:model-value="emit('update:modelValue', $event)"
  >
    <p class="target">
      {{ item?.part_no }} - {{ item?.part_name }} · {{ item?.workshop_name }}
    </p>
    <ElForm label-width="96px">
      <ElFormItem label="加工工艺" required>
        <ElSelect v-model="form.procedure" filterable allow-create default-first-option placeholder="选择已有工艺或输入新工艺">
          <ElOption v-for="procedure in item?.available_procedures || []" :key="procedure.id" :label="procedure.procedure_name" :value="procedure.id" />
        </ElSelect>
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
          <section v-for="group in materialGroups" :key="group.key" class="material-group">
            <div class="material-heading">
              <strong>{{ group.name }}</strong>
              <span>需要 {{ form.quantity * group.requiredUnit }}</span>
            </div>
            <div v-for="(source, index) in group.sources" :key="source.repository_id || source.card_key" class="source-row">
              <span>{{ source.material_source_name || `来源 ${index + 1}` }}</span>
              <small>可用 {{ source.available_quantity }}</small>
              <ElInputNumber
                v-if="source.repository_id !== null && group.sources.length > 1"
                v-model="form.materialQuantities[source.repository_id]"
                :min="0"
                :max="source.available_quantity"
              />
              <span v-else class="fixed-quantity">
                使用 {{ source.repository_id === null ? 0 : form.materialQuantities[source.repository_id] || 0 }}
              </span>
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
.material-groups { display: grid; gap: 12px; width: 100%; }
.material-group { padding: 12px; border: 1px solid var(--md-outline-variant); border-radius: var(--erp-radius); }
.material-heading, .source-row { display: grid; grid-template-columns: minmax(0, 1fr) auto auto; gap: 10px; align-items: center; }
.material-heading { margin-bottom: 8px; color: var(--md-on-surface); }
.material-heading span, .source-row small { color: var(--el-text-color-secondary); }
.source-row + .source-row { margin-top: 8px; }
.source-row :deep(.el-input-number) { width: 140px; }
.fixed-quantity { width: 140px; text-align: right; color: var(--md-on-surface); }
</style>
