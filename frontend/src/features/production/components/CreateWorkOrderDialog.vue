<script setup lang="ts">
import { computed, nextTick, reactive, ref, watch } from 'vue'
import { ElMessage } from 'element-plus'
import type { RepositoryItem, TagCard, WorkerItem } from '../domain/types'

const props = withDefaults(defineProps<{
  modelValue: boolean
  item?: RepositoryItem
  sources?: TagCard[]
  preferredSourceKey?: string | null
  workers: WorkerItem[]
  submitting: boolean
  mode?: 'production' | 'purchase' | 'assembly'
}>(), { mode: 'production', sources: () => [] })
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
const tagInputRef = ref<{ focus: () => void }>()
const tagInputKey = ref(0)
const tagInputFocused = ref(false)
const tagQuery = ref('')
const sourceOptions = computed(() => props.sources.filter(item => (
  item.available_quantity > 0
  && ((item.repository_id === null) !== (item.tag_stock_id === null))
)))
const selectedSource = computed(() => sourceOptions.value.find(
  item => item.card_key === form.sourceKey,
))
const maximumQuantity = computed(() => (
  props.mode === 'production'
    ? selectedSource.value?.available_quantity || 1
    : props.item?.available_quantity || 1
))
const normalizedTagNames = computed(() => form.tagNames
  .map(name => name.trim())
  .filter((name, index, names) => Boolean(name) && names.indexOf(name) === index))
const tagSuggestions = computed(() => {
  const keyword = tagQuery.value.trim().toLocaleLowerCase('zh-CN')
  const excludedNames = new Set([
    ...normalizedTagNames.value,
    ...(selectedSource.value?.tag_names || []),
  ])
  return (props.item?.available_tags || [])
    .filter(tag => !excludedNames.has(tag.tag_name))
    .filter(tag => (
      !keyword
      || tag.tag_name.toLocaleLowerCase('zh-CN').includes(keyword)
    ))
})
const showTagSuggestions = computed(() => (
  tagInputFocused.value
  && normalizedTagNames.value.length < 20
  && tagSuggestions.value.length > 0
))
const targetTagSetName = computed(() => {
  const names = normalizedTagNames.value
  if (!names.length) return '-'
  const source = selectedSource.value
  const members = (source?.tag_ids || []).map((id, index) => ({
    id,
    name: source?.tag_names[index] || '',
  }))
  const knownTags = new Map(
    (props.item?.available_tags || []).map(tag => [tag.tag_name, tag.id]),
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
  () => [props.modelValue, props.sources, props.preferredSourceKey] as const,
  ([visible]) => {
    if (!visible) return
    const preferred = sourceOptions.value.find(
      item => item.card_key === props.preferredSourceKey,
    )
    const source = preferred || sourceOptions.value[0]
    form.sourceKey = source?.card_key || ''
    form.quantity = source?.available_quantity || props.item?.available_quantity || 1
    form.workerId = null
    form.tagNames = []
    tagInputKey.value += 1
    tagInputFocused.value = false
    tagQuery.value = ''
  },
)

watch(() => form.sourceKey, () => {
  if (selectedSource.value) form.quantity = selectedSource.value.available_quantity
})

function selectTagSuggestion(name: string) {
  if (normalizedTagNames.value.length >= 20) return
  form.tagNames = [...normalizedTagNames.value, name]
  tagQuery.value = ''
  tagInputKey.value += 1
  void nextTick(() => tagInputRef.value?.focus())
}

function submit() {
  const tagNames = normalizedTagNames.value
  if (props.mode === 'production' && !selectedSource.value) {
    ElMessage.warning('请选择有可用数量的来源标记组合')
    return
  }
  if (props.mode === 'production' && tagNames.length === 0) {
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
    repositoryId: props.mode === 'production'
      ? selectedSource.value?.repository_id ?? null
      : props.item?.repository_id ?? null,
    tagStockId: props.mode === 'production'
      ? selectedSource.value?.tag_stock_id ?? null
      : null,
    quantity: form.quantity,
    workerId: form.workerId,
    tagNames: props.mode === 'production' ? tagNames : [],
  })
}
</script>

<template>
  <ElDialog
    :model-value="modelValue"
    :title="props.mode === 'purchase' ? '创建外购入库单' : props.mode === 'assembly' ? '开装配工单' : '开标记工单'"
    width="500px"
    @update:model-value="emit('update:modelValue', $event)"
  >
    <p class="target">
      {{ item?.part_no }} - {{ item?.part_name }} · {{ item?.procedure_name }}
    </p>
    <ElForm label-width="96px">
      <ElFormItem v-if="props.mode === 'production'" label="来源组合" required>
        <ElSelect v-model="form.sourceKey" placeholder="请选择来源标记组合">
          <ElOption
            v-for="source in sourceOptions"
            :key="source.card_key"
            :value="source.card_key"
            :label="`${source.tag_set_name} · 可用 ${source.available_quantity}`"
          />
        </ElSelect>
      </ElFormItem>
      <ElFormItem v-if="props.mode === 'production'" label="新增标记" required>
        <div class="tag-input-wrapper">
          <ElInputTag
            tag-type="danger"
            tag-effect="dark"
            :key="tagInputKey"
            ref="tagInputRef"
            v-model="form.tagNames"
            :max="20"
            :maxlength="200"
            clearable
            placeholder="输入或选择标记，可添加多个"
            @input="tagQuery = $event"
            @add-tag="tagQuery = ''"
            @focus="tagInputFocused = true"
            @blur="tagInputFocused = false"
          />
          <div v-if="showTagSuggestions" class="tag-suggestions">
            <button
              v-for="tag in tagSuggestions"
              :key="tag.id"
              class="tag-suggestion"
              type="button"
              @mousedown.prevent="selectTagSuggestion(tag.tag_name)"
            >
              {{ tag.tag_name }}
            </button>
          </div>
        </div>
      </ElFormItem>
      <ElFormItem v-if="props.mode === 'production'" label="目标组合">
        <span class="target-combination">{{ targetTagSetName }}</span>
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
      <ElButton type="primary" :loading="submitting" @click="submit">
        {{ props.mode === 'purchase' ? '创建外购单' : '创建工单' }}
      </ElButton>
    </template>
  </ElDialog>
</template>

<style scoped>
.target { margin: 0 0 18px; color: var(--el-text-color-secondary); }
.target-combination { overflow-wrap: anywhere; }
.el-select, .el-input-tag { width: 100%; }
.tag-input-wrapper { position: relative; width: 100%; }
.tag-suggestions {
  position: absolute;
  z-index: 20;
  top: calc(100% + 6px);
  right: 0;
  left: 0;
  max-height: 220px;
  padding: 6px 0;
  overflow-y: auto;
  background: var(--el-bg-color-overlay);
  border: 1px solid var(--el-border-color-light);
  border-radius: var(--el-border-radius-base);
  box-shadow: var(--el-box-shadow-light);
}
.tag-suggestion {
  display: block;
  width: 100%;
  padding: 8px 12px;
  color: var(--el-text-color-regular);
  text-align: left;
  cursor: pointer;
  background: transparent;
  border: 0;
}
.tag-suggestion:hover { background: var(--el-fill-color-light); }
</style>
