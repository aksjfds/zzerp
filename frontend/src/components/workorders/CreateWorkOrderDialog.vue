<script setup lang="ts">
import { computed, reactive, ref } from 'vue'
import {
  PROCEDURE_LABELS,
  PROCEDURE_OPTIONS,
  type CreateWorkOrderPayload,
  type Procedure,
} from '@/types/workorder'

const props = defineProps<{
  modelValue: boolean
}>()

const emit = defineEmits<{
  'update:modelValue': [value: boolean]
  submit: [payload: CreateWorkOrderPayload]
}>()

const visible = computed({
  get: () => props.modelValue,
  set: (value) => emit('update:modelValue', value),
})

const availableProcedures = [...PROCEDURE_OPTIONS]
const selectedProcedure = ref<Procedure | ''>('laser')
const form = reactive({
  item: '',
  quantity: 1,
  procedures: [] as Procedure[],
})

const proceduresToAdd = computed(() =>
  availableProcedures.filter((procedure) => !form.procedures.includes(procedure)),
)

function resetForm() {
  form.item = ''
  form.quantity = 1
  form.procedures = []
  selectedProcedure.value = proceduresToAdd.value[0] ?? 'laser'
}

function addProcedure() {
  if (!selectedProcedure.value || form.procedures.includes(selectedProcedure.value)) {
    return
  }

  form.procedures.push(selectedProcedure.value)
  selectedProcedure.value = proceduresToAdd.value[0] ?? ''
}

function removeProcedure(index: number) {
  form.procedures.splice(index, 1)
  selectedProcedure.value = proceduresToAdd.value[0] ?? ''
}

function moveProcedure(index: number, direction: -1 | 1) {
  const targetIndex = index + direction

  if (targetIndex < 0 || targetIndex >= form.procedures.length) {
    return
  }

  const current = form.procedures[index]
  const target = form.procedures[targetIndex]

  if (!current || !target) {
    return
  }

  form.procedures[index] = target
  form.procedures[targetIndex] = current
}

function submitForm() {
  if (!form.item.trim() || form.quantity <= 0 || form.procedures.length === 0) {
    return
  }

  emit('submit', {
    item: form.item.trim(),
    quantity: form.quantity,
    procedures: [...form.procedures],
  })
}

function getProcedureLabel(procedure: Procedure) {
  return PROCEDURE_LABELS[procedure]
}
</script>

<template>
  <ElDialog v-model="visible" title="添加工单" width="560px" @open="resetForm">
    <ElForm label-position="top">
      <ElFormItem label="部件">
        <ElInput v-model="form.item" placeholder="例如：MOG3V45-过桥" />
      </ElFormItem>

      <ElFormItem label="数量">
        <ElInputNumber v-model="form.quantity" :min="1" :step="1" controls-position="right" />
      </ElFormItem>

      <ElFormItem label="工序流程">
        <div class="procedure-builder">
          <div class="procedure-picker">
            <ElSelect v-model="selectedProcedure" :disabled="proceduresToAdd.length === 0" placeholder="选择工序">
              <ElOption
                v-for="procedure in proceduresToAdd"
                :key="procedure"
                :label="getProcedureLabel(procedure)"
                :value="procedure"
              />
            </ElSelect>
            <ElButton :disabled="proceduresToAdd.length === 0" @click="addProcedure">加入流程</ElButton>
          </div>

          <div class="ordered-procedures">
            <div v-for="(procedure, index) in form.procedures" :key="procedure" class="procedure-row">
              <div class="procedure-sequence">
                <span>{{ index + 1 }}</span>
                <strong>{{ getProcedureLabel(procedure) }}</strong>
              </div>
              <div class="procedure-actions">
                <ElButton text :disabled="index === 0" @click="moveProcedure(index, -1)">上移</ElButton>
                <ElButton text :disabled="index === form.procedures.length - 1" @click="moveProcedure(index, 1)">
                  下移
                </ElButton>
                <ElButton text type="danger" @click="removeProcedure(index)">移除</ElButton>
              </div>
            </div>
            <ElEmpty v-if="form.procedures.length === 0" description="请按加工顺序加入工序" :image-size="72" />
          </div>
        </div>
      </ElFormItem>
    </ElForm>

    <template #footer>
      <ElButton @click="visible = false">取消</ElButton>
      <ElButton type="primary" :disabled="form.procedures.length === 0" @click="submitForm">
        确认添加
      </ElButton>
    </template>
  </ElDialog>
</template>

<style scoped>
.procedure-builder {
  display: grid;
  gap: 12px;
  width: 100%;
}

.procedure-picker {
  display: grid;
  grid-template-columns: 1fr auto;
  gap: 10px;
}

.ordered-procedures {
  display: grid;
  gap: 8px;
}

.procedure-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  padding: 10px 12px;
  border: 1px solid var(--erp-border);
  border-radius: 8px;
  background: var(--erp-surface-muted);
}

.procedure-sequence {
  display: flex;
  align-items: center;
  gap: 10px;
}

.procedure-sequence span {
  display: grid;
  width: 28px;
  height: 28px;
  place-items: center;
  border-radius: 8px;
  background: #dbeafe;
  color: #1d4ed8;
  font-weight: 700;
}

.procedure-sequence strong {
  color: var(--erp-text);
}

.procedure-actions {
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  justify-content: flex-end;
  gap: 2px;
}

@media (max-width: 760px) {
  .procedure-picker,
  .procedure-row {
    grid-template-columns: 1fr;
  }

  .procedure-row {
    align-items: flex-start;
    flex-direction: column;
  }
}
</style>
