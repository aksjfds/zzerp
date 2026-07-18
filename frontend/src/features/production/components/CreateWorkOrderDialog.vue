<script setup lang="ts">
import { computed, reactive, watch } from 'vue'
import { ElMessage } from 'element-plus'
import type { RepositoryItem, SubstepCard, WorkerItem } from '../domain/types'

const props = withDefaults(defineProps<{
  modelValue: boolean
  item?: RepositoryItem
  source?: SubstepCard
  workers: WorkerItem[]
  submitting: boolean
  mode?: 'production' | 'purchase' | 'assembly'
}>(), { mode: 'production' })
const emit = defineEmits<{
  'update:modelValue': [value: boolean]
  submit: [payload: { quantity: number; workerId: number | null; substepName: string | null }]
}>()
const form = reactive({
  quantity: 1,
  workerId: null as number | null,
  substepName: '',
})
const maximumQuantity = computed(() => (
  props.source?.available_quantity || props.item?.available_quantity || 1
))
const sourceName = computed(() => {
  if (!props.source) return null
  if (props.source.substep_id === null) return `未${props.item?.procedure_name || '加工'}`
  return `${props.source.substep_name || '当前细分'}完`
})

watch(() => props.modelValue, (visible) => {
  if (visible) {
    form.quantity = maximumQuantity.value
    form.workerId = null
    form.substepName = ''
  }
})

function suggestSubsteps(
  query: string,
  callback: (suggestions: Array<{ value: string }>) => void,
) {
  const keyword = query.trim().toLocaleLowerCase('zh-CN')
  const suggestions = (props.item?.available_substeps || [])
    .map(item => item.substep_name)
    .filter((name, index, names) => names.indexOf(name) === index)
    .filter(name => !keyword || name.toLocaleLowerCase('zh-CN').includes(keyword))
    .map(value => ({ value }))
  callback(suggestions)
}

function submit() {
  const substepName = form.substepName?.trim() || null
  if (props.mode !== 'assembly' && !substepName) {
    ElMessage.warning('请输入工单细分')
    return
  }
  if (substepName && substepName.length > 200) {
    ElMessage.warning('工单细分不能超过 200 个字符')
    return
  }
  emit('submit', {
    quantity: form.quantity,
    workerId: form.workerId,
    substepName,
  })
}
</script>

<template>
  <ElDialog
    :model-value="modelValue"
    :title="props.mode === 'purchase' ? '创建外购入库单' : props.mode === 'assembly' ? '开装配工单' : '开细分工单'"
    width="460px"
    @update:model-value="emit('update:modelValue', $event)"
  >
    <p class="target">
      {{ item?.part_no }} - {{ item?.part_name }} · {{ item?.procedure_name }}
      <template v-if="sourceName"> · 来源：{{ sourceName }}</template>
      <template v-else-if="item?.current_stage_name"> · {{ item.current_stage_name }}</template>
    </p>
    <ElForm label-width="80px">
      <ElFormItem v-if="props.mode !== 'assembly'" label="工单细分" required>
        <ElAutocomplete
          v-model="form.substepName"
          :fetch-suggestions="suggestSubsteps"
          clearable
          placeholder="输入或选择本次加工细分"
        />
      </ElFormItem>
      <ElFormItem :label="props.mode === 'purchase' ? '外购数量' : '工单数量'">
        <ElInputNumber v-model="form.quantity" :min="1" :max="maximumQuantity" />
      </ElFormItem>
      <ElFormItem :label="props.mode === 'purchase' ? '经办人' : '执行工人'">
        <ElSelect v-model="form.workerId" clearable placeholder="暂不分配工人">
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
      <ElButton
        type="primary"
        :loading="submitting"
        @click="submit"
      >{{ props.mode === 'purchase' ? '创建外购单' : '创建工单' }}</ElButton>
    </template>
  </ElDialog>
</template>

<style scoped>
.target { margin: 0 0 18px; color: var(--el-text-color-secondary); }
.el-select, .el-autocomplete { width: 100%; }
</style>
