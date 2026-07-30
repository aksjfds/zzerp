<script setup lang="ts">
import { onBeforeUnmount, reactive, watch } from 'vue'
import type { RepositoryWorkshop } from '../api/departmentRepositories'
import type { RepositoryFilters } from '../domain/types'

defineProps<{
  workshops: RepositoryWorkshop[]
}>()

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
      <ElOption label="未加工" value="unprocessed" />
      <ElOption label="加工中" value="processing" />
      <ElOption label="已完成" value="completed" />
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
