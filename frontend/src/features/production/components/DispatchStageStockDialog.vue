<script setup lang="ts">
import { computed, reactive, watch } from 'vue'
import { ElMessage } from 'element-plus'
import type { RepositoryItem, SubstepCard } from '../domain/types'

const props = defineProps<{
  modelValue: boolean
  item?: RepositoryItem
  substeps: SubstepCard[]
  submitting?: boolean
}>()
const emit = defineEmits<{
  'update:modelValue': [value: boolean]
  submit: [payload: { stageStockId: number; quantity: number }]
}>()
const form = reactive({ stageStockId: null as number | null, quantity: 1 })
const dispatchableSubsteps = computed(() => props.substeps.filter(
  item => item.stage_stock_id !== null && item.available_quantity > 0,
))
const selectedSource = computed(() => dispatchableSubsteps.value.find(
  item => item.stage_stock_id === form.stageStockId,
))

watch(() => [props.modelValue, props.substeps] as const, ([visible]) => {
  if (!visible) return
  const onlySource = dispatchableSubsteps.value.length === 1
    ? dispatchableSubsteps.value[0]
    : undefined
  form.stageStockId = onlySource?.stage_stock_id || null
  form.quantity = onlySource?.available_quantity || 1
})

watch(() => form.stageStockId, () => {
  if (selectedSource.value) form.quantity = selectedSource.value.available_quantity
})

function submit() {
  if (!selectedSource.value?.stage_stock_id) {
    ElMessage.warning('请选择要出货的已完细分')
    return
  }
  if (form.quantity < 1 || form.quantity > selectedSource.value.available_quantity) {
    ElMessage.warning('出货数量超过当前可出货数量')
    return
  }
  emit('submit', {
    stageStockId: selectedSource.value.stage_stock_id,
    quantity: form.quantity,
  })
}
</script>

<template>
  <ElDialog
    :model-value="modelValue"
    title="工艺出货"
    width="480px"
    @update:model-value="emit('update:modelValue', $event)"
  >
    <p class="target">{{ item?.part_no }} - {{ item?.part_name }} · {{ item?.procedure_name }}</p>
    <ElForm v-if="dispatchableSubsteps.length" label-width="86px">
      <ElFormItem label="已完细分" required>
        <ElSelect v-model="form.stageStockId" placeholder="请选择出货来源" style="width: 100%">
          <ElOption
            v-for="substep in dispatchableSubsteps"
            :key="substep.card_key"
            :value="substep.stage_stock_id"
            :label="`${substep.substep_name}完 · 已完 ${substep.completed_quantity} · 可出货 ${substep.available_quantity}`"
          />
        </ElSelect>
      </ElFormItem>
      <ElFormItem label="出货数量" required>
        <ElInputNumber
          v-model="form.quantity"
          :min="1"
          :max="selectedSource?.available_quantity || 1"
        />
      </ElFormItem>
    </ElForm>
    <ElEmpty v-else description="暂无可出货的已完细分" :image-size="64" />
    <template #footer>
      <ElButton @click="emit('update:modelValue', false)">取消</ElButton>
      <ElButton
        type="primary"
        :disabled="!dispatchableSubsteps.length"
        :loading="submitting"
        @click="submit"
      >确认出货</ElButton>
    </template>
  </ElDialog>
</template>

<style scoped>
.target { margin: 0 0 18px; color: var(--el-text-color-secondary); }
</style>
