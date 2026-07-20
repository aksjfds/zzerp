<script setup lang="ts">
import type { ProcedureTag } from '../domain/types'

defineProps<{
  tags: ProcedureTag[]
  existingTagIds: number[]
  applyingTagIds: number[]
  loading: boolean
  disabled?: boolean
}>()
const emit = defineEmits<{
  'update:existingTagIds': [value: number[]]
  'update:applyingTagIds': [value: number[]]
}>()

function updateExistingTagIds(ids?: number[]) {
  emit('update:existingTagIds', ids || [])
}

function updateApplyingTagIds(ids?: number[]) {
  emit('update:applyingTagIds', ids || [])
}
</script>

<template>
  <div v-loading="loading" class="procedure-tag-filters">
    <ElSelect
      :model-value="existingTagIds"
      :disabled="disabled"
      multiple
      filterable
      clearable
      tag-type="danger"
      tag-effect="dark"
      placeholder="筛选已有标记"
      @update:model-value="updateExistingTagIds"
    >
      <ElOption
        v-for="tag in tags"
        :key="tag.id"
        :label="tag.tag_name"
        :value="tag.id"
      />
    </ElSelect>
    <ElSelect
      :model-value="applyingTagIds"
      :disabled="disabled"
      multiple
      filterable
      clearable
      tag-type="danger"
      tag-effect="dark"
      placeholder="筛选正在打标记"
      @update:model-value="updateApplyingTagIds"
    >
      <ElOption
        v-for="tag in tags"
        :key="tag.id"
        :label="tag.tag_name"
        :value="tag.id"
      />
    </ElSelect>
  </div>
</template>

<style scoped>
.procedure-tag-filters {
  display: grid;
  width: min(520px, 100%);
  grid-template-columns: repeat(2, minmax(210px, 1fr));
  gap: 12px;
  align-items: center;
  padding: 16px 20px;
  border: 1px solid var(--erp-border);
  border-radius: 10px;
  background: #fff;
  box-shadow: var(--erp-shadow-sm);
}

.el-select { width: 100%; }

@media (max-width: 760px) {
  .procedure-tag-filters {
    grid-template-columns: 1fr;
    width: 100%;
  }
}
</style>
