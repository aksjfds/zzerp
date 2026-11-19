<script setup lang="ts">
import { onBeforeUnmount, onMounted, ref } from 'vue'
import { getApiErrorDetail } from '@/api/request'
import LoadErrorAlert from '@/shared/feedback/LoadErrorAlert.vue'
import { queryWarehouseStocks, queryDepartmentWarehouseStocks, type WarehouseStock } from '../api/warehouse'
import WarehouseDispatchDialog from './WarehouseDispatchDialog.vue'

const props = defineProps<{ canDispatch?: boolean; departmentCode?: string }>()
const emit = defineEmits<{ dispatched: [] }>()
const dispatching = ref<WarehouseStock>()
function dispatched() { dispatching.value = undefined; void load(); emit('dispatched') }

const stocks = ref<WarehouseStock[]>([])
const page = ref(1), total = ref(0), loading = ref(false), error = ref('')
let active = true, revision = 0
async function load() {
  const current = ++revision; loading.value = true; error.value = ''
  try {
    const result = props.departmentCode
      ? await queryDepartmentWarehouseStocks(page.value, props.departmentCode)
      : await queryWarehouseStocks(page.value)
    if (!active || current !== revision) return
    if (!result.data.length && page.value > 1 && result.total <= (page.value - 1) * 50) {
      page.value = Math.max(1, Math.ceil(result.total / 50)); await load(); return
    }
    stocks.value = result.data; total.value = result.total
  } catch (cause) { if (active && current === revision) error.value = getApiErrorDetail(cause)?.message || '库存加载失败' }
  finally { if (active && current === revision) loading.value = false }
}
defineExpose({ refresh: load })
onMounted(load)
onBeforeUnmount(() => { active = false; revision += 1 })
</script>
<template>
  <section class="warehouse-panel">
    <div class="warehouse-toolbar"><h2>库存</h2><ElButton :loading="loading" @click="load">刷新库存</ElButton></div>
    <LoadErrorAlert :message="error" :loading="loading" @retry="load" />
    <ElTable v-if="!error" v-loading="loading" :data="stocks" row-key="id" empty-text="暂无库存">
      <ElTableColumn class-name="data-primary" prop="product" label="产品" min-width="220" />
      <ElTableColumn class-name="data-primary" prop="material" label="配件/装配体" min-width="260" />
      <ElTableColumn class-name="data-metric" prop="available_quantity" label="库存" min-width="140" align="right" />
      <ElTableColumn class-name="data-secondary" prop="arrival_date" label="到料日期" min-width="150" />
      <ElTableColumn label="操作" width="100"><template #default="{ row }">
        <ElButton v-if="props.canDispatch" link type="primary" :disabled="loading" @click="dispatching = row">出料</ElButton>
        <span v-else>—</span>
      </template></ElTableColumn>
    </ElTable>
    <WarehouseDispatchDialog v-if="dispatching && props.canDispatch" :stocks="[dispatching]" @close="dispatching = undefined" @saved="dispatched" />
    <ElPagination v-model:current-page="page" :total="total" :page-size="50" layout="prev, pager, next, total" @current-change="load" />
  </section>
</template>
<style scoped>
.warehouse-panel { min-width: 0; padding: 24px; border: 1px solid var(--erp-border); border-radius: var(--erp-radius-lg); background: var(--erp-surface); }
.warehouse-toolbar { display: flex; align-items: center; justify-content: space-between; gap: 16px; margin-bottom: 16px; }
.warehouse-toolbar h2 { margin: 0; font-size: 20px; }
.el-pagination { margin-top: 16px; }
@media (max-width: 760px) { .warehouse-panel { padding: 16px; } }
</style>
