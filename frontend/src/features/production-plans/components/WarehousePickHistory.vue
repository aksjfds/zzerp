<script setup lang="ts">
import { onBeforeUnmount, onMounted, ref } from 'vue'
import { getApiErrorDetail } from '@/api/request'
import LoadErrorAlert from '@/shared/feedback/LoadErrorAlert.vue'
import { queryWarehousePicks, type WarehousePick } from '../api/warehouse'
import ProductionDocumentPrintDialog from './ProductionDocumentPrintDialog.vue'

withDefaults(defineProps<{ title?: string }>(), { title: '出料记录' })
const rows = ref<WarehousePick[]>([])
const printRecord = ref<WarehousePick>()
const page = ref(1), total = ref(0), loading = ref(false), error = ref('')
let active = true, revision = 0
async function load() {
  const current = ++revision; loading.value = true; error.value = ''
  try {
    const result = await queryWarehousePicks(page.value)
    if (!active || current !== revision) return
    if (!result.data.length && page.value > 1 && result.total <= (page.value - 1) * 50) {
      page.value = Math.max(1, Math.ceil(result.total / 50)); await load(); return
    }
    rows.value = result.data; total.value = result.total
  } catch (cause) { if (active && current === revision) error.value = getApiErrorDetail(cause)?.message || '出料记录加载失败' }
  finally { if (active && current === revision) loading.value = false }
}
defineExpose({ refresh: load })
onMounted(load)
onBeforeUnmount(() => { active = false; revision += 1 })
</script>
<template>
  <section class="warehouse-history">
    <div class="history-toolbar"><h2>{{ title }}</h2><ElButton :loading="loading" @click="load">刷新</ElButton></div>
    <LoadErrorAlert :message="error" :loading="loading" @retry="load" />
    <ElTable v-if="!error" v-loading="loading" :data="rows" row-key="id" empty-text="暂无出入库记录">
      <ElTableColumn class-name="data-primary" prop="product" label="产品" min-width="220" />
      <ElTableColumn class-name="data-primary" prop="material" label="配件/装配体" min-width="260" />
      <ElTableColumn class-name="data-reference" prop="order_no" label="接收订单" min-width="160" />
      <ElTableColumn prop="department" label="接收部门" min-width="110" />
      <ElTableColumn class-name="data-metric" prop="quantity" label="数量" min-width="120" align="right" />
      <ElTableColumn prop="sources" label="库存来源订单及数量" min-width="260" />
      <ElTableColumn prop="actor_username" label="操作人" min-width="110" />
      <ElTableColumn class-name="data-secondary" prop="created_at" label="时间" min-width="185" />
      <ElTableColumn class-name="data-secondary" prop="note" label="备注" min-width="160" />
      <ElTableColumn label="操作" width="90"><template #default="{ row }"><ElButton link type="primary" @click="printRecord = row">打印</ElButton></template></ElTableColumn>
    </ElTable>
    <ElPagination v-model:current-page="page" :total="total" :page-size="50" layout="prev, pager, next, total" @current-change="load" />
    <ProductionDocumentPrintDialog v-if="printRecord" :document="{ kind: 'warehouse', record: printRecord }" @close="printRecord = undefined" />
  </section>
</template>
<style scoped>
.warehouse-history { min-width: 0; max-width: 100%; box-sizing: border-box; padding: 24px; border: 1px solid var(--erp-border); border-radius: var(--erp-radius-lg); background: var(--erp-surface); }
.history-toolbar { display: flex; align-items: center; justify-content: space-between; gap: 16px; }
h2 { margin: 0; font-size: 20px; }
.el-table { margin-top: 16px; }
.el-pagination { margin-top: 16px; }
@media (max-width: 760px) { .warehouse-history { padding: 16px; } }
</style>
