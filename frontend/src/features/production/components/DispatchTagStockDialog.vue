<script setup lang="ts">
import { computed, reactive, watch } from 'vue'
import { ElMessage } from 'element-plus'
import type { RepositoryItem, TagCard } from '../domain/types'

const props = defineProps<{
  modelValue: boolean
  item?: RepositoryItem
  tagCards: TagCard[]
  submitting?: boolean
}>()
const emit = defineEmits<{
  'update:modelValue': [value: boolean]
  submit: [payload: { tagStockId: number; quantity: number }]
}>()
const form = reactive({ tagStockId: null as number | null, quantity: 1 })
const dispatchableSources = computed(() => props.tagCards.filter(
  item => item.tag_stock_id !== null && item.available_quantity > 0,
))
const selectedSource = computed(() => dispatchableSources.value.find(
  item => item.tag_stock_id === form.tagStockId,
))

watch(() => [props.modelValue, props.tagCards] as const, ([visible]) => {
  if (!visible) return
  const source = dispatchableSources.value.length === 1
    ? dispatchableSources.value[0]
    : undefined
  form.tagStockId = source?.tag_stock_id || null
  form.quantity = source?.available_quantity || 1
})

watch(() => form.tagStockId, () => {
  if (selectedSource.value) form.quantity = selectedSource.value.available_quantity
})

function submit() {
  if (!selectedSource.value?.tag_stock_id) {
    ElMessage.warning('请选择要出货的标记组合')
    return
  }
  if (form.quantity < 1 || form.quantity > selectedSource.value.available_quantity) {
    ElMessage.warning('出货数量超过当前可出货数量')
    return
  }
  emit('submit', {
    tagStockId: selectedSource.value.tag_stock_id,
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
    <ElForm v-if="dispatchableSources.length" label-width="96px">
      <ElFormItem label="标记组合" required>
        <ElSelect v-model="form.tagStockId" placeholder="请选择出货来源" style="width: 100%">
          <ElOption
            v-for="source in dispatchableSources"
            :key="source.card_key"
            :value="source.tag_stock_id"
            :label="`${source.tag_set_name} · 可出货 ${source.available_quantity}`"
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
    <ElEmpty v-else description="暂无可出货的已完成标记组合" :image-size="64" />
    <template #footer>
      <ElButton @click="emit('update:modelValue', false)">取消</ElButton>
      <ElButton
        type="primary"
        :disabled="!dispatchableSources.length"
        :loading="submitting"
        @click="submit"
      >确认出货</ElButton>
    </template>
  </ElDialog>
</template>

<style scoped>
.target { margin: 0 0 18px; color: var(--el-text-color-secondary); }
</style>
