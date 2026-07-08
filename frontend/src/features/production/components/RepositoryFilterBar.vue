<script setup lang="ts">
import { onBeforeUnmount, reactive, watch } from 'vue'
import type { RepositoryFilters } from '../domain/types'

const emit = defineEmits<{
  search: [filters: RepositoryFilters]
}>()
const form = reactive({
  keyword: '',
  dates: [] as string[],
  work_status: 'all' as RepositoryFilters['work_status'],
})

let timer: ReturnType<typeof setTimeout> | undefined
function apply() {
  emit('search', {
    keyword: form.keyword.trim(),
    arrived_from: form.dates[0] || null,
    arrived_to: form.dates[1] || null,
    work_status: form.work_status,
  })
}
function schedule() {
  clearTimeout(timer)
  timer = setTimeout(apply, 100)
}
function reset() {
  form.keyword = ''
  form.dates = []
  form.work_status = 'all'
}
watch(form, schedule)
onBeforeUnmount(() => clearTimeout(timer))
</script>

<template>
  <section class="repository-filter-bar">
    <ElSelect v-model="form.work_status" aria-label="生产状态">
      <ElOption label="全部状态" value="all" />
      <ElOption label="未加工" value="unprocessed" />
      <ElOption label="加工中" value="processing" />
      <ElOption label="已完成" value="completed" />
    </ElSelect>
    <ElDatePicker v-model="form.dates" type="daterange" value-format="YYYY-MM-DD" start-placeholder="到达开始日期"
      end-placeholder="到达结束日期" />
    <ElInput v-model="form.keyword" clearable placeholder="搜索产品、厂编、配件或装配体名称" />
    <div class="actions">
      <ElButton @click="reset">重置</ElButton>
    </div>
  </section>
</template>

<style scoped>
.repository-filter-bar {
  display: grid;
  grid-template-columns: 150px 360px minmax(240px, 1fr) auto;
  gap: 12px;
  align-items: center;
  margin-bottom: 18px;
  padding: 16px 20px;
  border: 1px solid var(--erp-border);
  border-radius: 10px;
  background: #fff;
  box-shadow: var(--erp-shadow-sm);
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

  .repository-filter-bar :deep(.el-date-editor),
  .repository-filter-bar .el-select {
    width: 100%;
  }
}
</style>
