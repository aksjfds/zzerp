<script setup lang="ts">
import { onBeforeUnmount, reactive, watch } from 'vue'
import type { ProductionWorkbenchWorkshop } from '../domain/productionWorkbench'
import type { ProductionWorkbenchAttention } from '../domain/productionWorkbench'

defineProps<{ workshops: ProductionWorkbenchWorkshop[] }>()
const emit = defineEmits<{
  search: [filters: {
    keyword: string
    workshopName?: string
    attention: ProductionWorkbenchAttention
  }]
}>()
const form = reactive({
  keyword: '',
  workshopName: undefined as string | undefined,
  attention: 'all' as ProductionWorkbenchAttention,
})
let timer: ReturnType<typeof setTimeout> | undefined

function apply() {
  emit('search', {
    keyword: form.keyword.trim(),
    workshopName: form.workshopName,
    attention: form.attention,
  })
}

function schedule() {
  clearTimeout(timer)
  timer = setTimeout(apply, 350)
}

function reset() {
  form.keyword = ''
  form.workshopName = undefined
  form.attention = 'all'
}

watch(form, schedule)
onBeforeUnmount(() => clearTimeout(timer))
</script>

<template>
  <section class="workbench-filter-bar">
    <ElSelect v-model="form.attention" aria-label="关注状态">
      <ElOption label="全部物料" value="all" />
      <ElOption label="可开工" value="available" />
      <ElOption label="加工中" value="processing" />
      <ElOption label="待处理结果" value="ready_for_result" />
      <ElOption label="质检中" value="qc" />
      <ElOption label="返工中" value="rework" />
    </ElSelect>
    <ElSelect v-model="form.workshopName" clearable placeholder="全部车间" aria-label="车间">
      <ElOption
        v-for="workshop in workshops"
        :key="workshop.id"
        :label="workshop.workshop_name"
        :value="workshop.workshop_name"
      />
    </ElSelect>
    <ElInput v-model="form.keyword" clearable placeholder="搜索订单、产品、厂编或物料" />
    <ElButton @click="reset">重置</ElButton>
  </section>
</template>

<style scoped>
.workbench-filter-bar { display: grid; grid-template-columns: 150px 190px minmax(240px, 1fr) auto; gap: 12px; align-items: center; margin-bottom: 18px; }
@media (max-width: 900px) {
  .workbench-filter-bar { grid-template-columns: 1fr; }
  .workbench-filter-bar :deep(.el-select), .workbench-filter-bar :deep(.el-button) { width: 100%; }
}
</style>
