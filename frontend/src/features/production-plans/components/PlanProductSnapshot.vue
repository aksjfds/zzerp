<script setup lang="ts">
import { onBeforeUnmount, onMounted, ref } from 'vue'
import { BomEditor, ProcessFlowCanvas } from '@/features/process-designer'
import LoadErrorAlert from '@/shared/feedback/LoadErrorAlert.vue'
import { getApiErrorDetail } from '@/api/request'
import { queryPlanProductSnapshot } from '../api/plans'
import type { PlanProductSnapshot } from '../domain/types'

const props = defineProps<{ planId: number; productId: number }>()
const snapshot = ref<PlanProductSnapshot>()
const loading = ref(false)
const error = ref('')
let active = true
let revision = 0
async function load() {
  const current = ++revision
  loading.value = true
  error.value = ''
  try {
    const result = await queryPlanProductSnapshot(props.planId, props.productId)
    if (active && current === revision) snapshot.value = result
  } catch (cause) {
    if (active && current === revision) error.value = getApiErrorDetail(cause)?.message || '计划快照加载失败'
  } finally { if (active && current === revision) loading.value = false }
}
onMounted(load)
onBeforeUnmount(() => { active = false; revision += 1 })
</script>
<template>
  <section v-loading="loading" class="snapshot-view">
    <LoadErrorAlert :message="error" :loading="loading" @retry="load" />
    <template v-if="snapshot && !error">
      <header><div><h2>{{ snapshot.factory_code }} · {{ snapshot.product_name }}</h2><span class="snapshot-version">{{ snapshot.source_version_value }}</span></div><ElTag type="info">只读</ElTag></header>
      <BomEditor :model-value="snapshot.bom_items" :factory-code="snapshot.factory_code" readonly />
      <h3>快照工艺路线</h3><ProcessFlowCanvas :model-value="snapshot.process_flow" readonly />
    </template>
  </section>
</template>
<style scoped>
.snapshot-view { min-height: 180px; } header { display: flex; flex-wrap: wrap; align-items: center; justify-content: space-between; gap: 16px; margin-bottom: 24px; } h2 { margin: 0; font-size: 20px; } .snapshot-version { color: var(--erp-text-muted); font-size: 13px; } h3 { margin: 32px 0 16px; font-size: 18px; }
</style>
