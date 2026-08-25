<script setup lang="ts">
import { onBeforeUnmount, reactive, watch } from 'vue'
import type { RepositoryWorkshop } from '../domain/repositories'
import type { RepositoryFilters } from '../domain/types'
import { repositoryStatusLabel } from '../domain/repositoryWorkStatus'

const props = withDefaults(defineProps<{
  workshops: RepositoryWorkshop[]
  mode?: 'production' | 'assembly'
}>(), { mode: 'production' })

const emit = defineEmits<{
  search: [filters: RepositoryFilters]
}>()
const form = reactive({
  keyword: '',
  workshop_name: null as string | null,
  work_status: 'all' as RepositoryFilters['work_status'],
})

let timer: ReturnType<typeof setTimeout> | undefined
function apply() {
  emit('search', {
    keyword: form.keyword.trim(),
    workshop_name: form.workshop_name,
    work_status: form.work_status,
  })
}
function schedule() {
  clearTimeout(timer)
  timer = setTimeout(apply, 350)
}
function reset() {
  form.keyword = ''
  form.workshop_name = null
  form.work_status = 'all'
}
watch(form, schedule)
onBeforeUnmount(() => clearTimeout(timer))
</script>

<template>
  <section class="repository-filter-bar">
    <ElSelect v-model="form.work_status" placement="bottom-start" :fallback-placements="['bottom-start', 'bottom-end']" aria-label="生产状态">
      <ElOption label="全部状态" value="all" />
      <template v-if="props.mode === 'production'">
        <ElOption :label="repositoryStatusLabel('unprocessed', props.mode)" value="unprocessed" />
        <ElOption :label="repositoryStatusLabel('processing', props.mode)" value="processing" />
        <ElOption :label="repositoryStatusLabel('completed', props.mode)" value="completed" />
      </template>
      <template v-else>
        <ElOption :label="repositoryStatusLabel('unprocessed', props.mode)" value="unprocessed" />
        <ElOption :label="repositoryStatusLabel('processing', props.mode)" value="processing" />
        <ElOption :label="repositoryStatusLabel('qc', props.mode)" value="qc" />
        <ElOption :label="repositoryStatusLabel('rework', props.mode)" value="rework" />
        <ElOption :label="repositoryStatusLabel('completed', props.mode)" value="completed" />
      </template>
    </ElSelect>
    <ElSelect
      v-model="form.workshop_name"
      placement="bottom-start"
      :fallback-placements="['bottom-start', 'bottom-end']"
      clearable
      placeholder="全部车间"
      aria-label="车间"
    >
      <ElOption
        v-for="workshop in workshops"
        :key="workshop.id"
        :label="workshop.workshop_name"
        :value="workshop.workshop_name"
      />
    </ElSelect>
    <ElInput v-model="form.keyword" clearable placeholder="搜索产品、厂编、配件或装配体名称" />
    <div class="actions">
      <ElButton @click="reset">重置</ElButton>
    </div>
  </section>
</template>

<style scoped>
.repository-filter-bar {
  display: grid;
  grid-template-columns: 150px 200px minmax(240px, 1fr) auto;
  gap: 12px;
  align-items: center;
  margin-bottom: 18px;
}

.actions {
  display: flex;
  justify-content: flex-end;
  gap: 8px;
}

@media (max-width: 900px) {
  .repository-filter-bar {
    grid-template-columns: 1fr;
  }

  .repository-filter-bar .el-select {
    width: 100%;
  }

  .actions, .actions :deep(.el-button) {
    width: 100%;
  }
}
</style>
