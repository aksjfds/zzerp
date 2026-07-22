<script setup lang="ts">
import { computed, reactive, watch } from 'vue'
import { ElMessage } from 'element-plus'
import type { RepositoryItem, TagCard, WorkerItem } from '../domain/types'

const props = withDefaults(defineProps<{
  modelValue: boolean
  item?: RepositoryItem
  sources?: TagCard[]
  workers: WorkerItem[]
  submitting: boolean
}>(), { sources: () => [] })
const emit = defineEmits<{
  'update:modelValue': [value: boolean]
  submit: [payload: {
    repositoryId: number | null
    tagStockId: number | null
    quantity: number
    workerId: number | null
    tagNames: string[]
  }]
}>()
const form = reactive({
  sourceKey: '',
  quantity: 1,
  workerId: null as number | null,
  tagNames: [] as string[],
})
const sourceOptions = computed(() => props.sources.filter(item => (
  item.available_quantity > 0
  && item.can_create_work_order
  && ((item.repository_id === null) !== (item.tag_stock_id === null))
)))
const selectedSource = computed(() => sourceOptions.value.find(
  item => item.card_key === form.sourceKey,
))
const maximumQuantity = computed(() => selectedSource.value?.available_quantity || 1)
const normalizedTagNames = computed(() => (form.tagNames || [])
  .map(name => name.trim())
  .filter((name, index, names) => Boolean(name) && names.indexOf(name) === index))
const tagOptions = computed(() => {
  const sourceNames = new Set(selectedSource.value?.tag_names || [])
  return (props.item?.configured_tags || []).filter(
    tag => !sourceNames.has(tag.tag_name),
  )
})
const targetTagSetName = computed(() => {
  const names = normalizedTagNames.value
  if (!names.length) return '-'
  const source = selectedSource.value
  const members = (source?.tag_ids || []).map((id, index) => ({
    id,
    name: source?.tag_names[index] || '',
  }))
  const knownTags = new Map(
    (props.item?.configured_tags || []).map(tag => [tag.tag_name, tag.id]),
  )
  const knownMembers = names
    .filter(name => knownTags.has(name))
    .map(name => ({ id: knownTags.get(name) as number, name }))
  const newNames = names.filter(name => !knownTags.has(name))
  return [...members, ...knownMembers].sort((left, right) => left.id - right.id)
    .map(member => member.name)
    .concat(newNames)
    .filter(Boolean)
    .join(' + ')
})

watch(
  () => [props.modelValue, props.sources] as const,
  ([visible]) => {
    if (!visible) return
    const source = sourceOptions.value[0]
    form.sourceKey = source?.card_key || ''
    form.quantity = source?.available_quantity || props.item?.available_quantity || 1
    form.workerId = null
    form.tagNames = []
  },
)

watch(() => form.sourceKey, () => {
  if (selectedSource.value) form.quantity = selectedSource.value.available_quantity
})

function updateTagNames(names?: string[]) {
  form.tagNames = names || []
}

function submit() {
  const tagNames = normalizedTagNames.value
  if (!selectedSource.value) {
    ElMessage.warning('请选择有可用数量的来源标记组合')
    return
  }
  if (tagNames.length === 0) {
    ElMessage.warning('请至少输入一个本次新增标记')
    return
  }
  if (tagNames.some(name => selectedSource.value?.tag_names.includes(name))) {
    ElMessage.warning('来源组合已经包含本次输入的标记')
    return
  }
  if (tagNames.length > 20) {
    ElMessage.warning('一张工单最多新增 20 个标记')
    return
  }
  if (tagNames.some(name => name.length > 200)) {
    ElMessage.warning('标记名称不能超过 200 个字符')
    return
  }
  if (form.quantity < 1 || form.quantity > maximumQuantity.value) {
    ElMessage.warning('工单数量超过来源可用数量')
    return
  }
  emit('submit', {
    repositoryId: selectedSource.value?.repository_id ?? null,
    tagStockId: selectedSource.value?.tag_stock_id ?? null,
    quantity: form.quantity,
    workerId: form.workerId,
    tagNames,
  })
}
</script>

<template>
  <ElDialog
    :model-value="modelValue"
    title="开标记工单"
    width="500px"
    @update:model-value="emit('update:modelValue', $event)"
  >
    <p class="target">
      {{ item?.part_no }} - {{ item?.part_name }} · {{ item?.procedure_name }}
    </p>
    <ElForm label-width="96px">
      <ElFormItem label="来源组合" required>
        <ElSelect v-model="form.sourceKey" placement="top-start" :fallback-placements="['top-start', 'top-end']" placeholder="请选择来源标记组合">
          <ElOption
            v-for="source in sourceOptions"
            :key="source.card_key"
            :value="source.card_key"
            :label="`${source.tag_set_name} · 可用 ${source.available_quantity}`"
          />
        </ElSelect>
      </ElFormItem>
      <ElFormItem label="新增标记" required>
        <ElSelect
          :model-value="form.tagNames"
          placement="top-start"
          :fallback-placements="['top-start', 'top-end']"
          multiple
          filterable
          default-first-option
          clearable
          :multiple-limit="20"
          tag-type="danger"
          tag-effect="dark"
          placeholder="选择一个或多个已配置必做标记"
          @update:model-value="updateTagNames"
        >
          <ElOption
            v-for="tag in tagOptions"
            :key="tag.id"
            :label="tag.tag_name"
            :value="tag.tag_name"
          />
        </ElSelect>
      </ElFormItem>
      <ElFormItem label="目标组合">
        <span class="target-combination">{{ targetTagSetName }}</span>
      </ElFormItem>
      <ElFormItem label="工单数量">
        <ElInputNumber v-model="form.quantity" :min="1" :max="maximumQuantity" />
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
.target-combination { overflow-wrap: anywhere; }
.el-select { width: 100%; }
</style>
