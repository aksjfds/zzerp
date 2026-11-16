<script setup lang="ts">
import { useCompactViewport } from '@/shared/layout/useCompactViewport'

import { computed, onMounted, ref } from 'vue'
import { storeToRefs } from 'pinia'
import { useRouter } from 'vue-router'
import PageHeader from '@/shared/layout/PageHeader.vue'
import { useEngineeringProductsStore } from '../stores/engineeringProducts'
import { PRODUCT_PERMISSIONS } from '@/permission/constants'
import LoadErrorAlert from '@/shared/feedback/LoadErrorAlert.vue'

const compact = useCompactViewport()
const router = useRouter()
const store = useEngineeringProductsStore()
const { loading, products, productTotal, productsError } = storeToRefs(store)
const keyword = ref('')
const page = ref(1)
const pageSize = 50
const filteredProducts = computed(() => {
  const value = keyword.value.trim().toLowerCase()
  if (!value) return products.value
  return products.value.filter((product) => [
    product.customer_name,
    product.product_name,
    product.factory_code,
    product.customer_code,
  ].some((item) => item.toLowerCase().includes(value)))
})

function loadProducts() {
  return store.loadProducts(page.value, pageSize)
}

onMounted(loadProducts)
</script>

<template>
  <main class="page-shell">
    <PageHeader section-name="工程管理" page-title="产品工程">
      <template #actions><ElButton :loading="loading" @click="loadProducts">刷新数据</ElButton><ElButton v-permission="PRODUCT_PERMISSIONS.add" type="primary" @click="router.push('/products/new')">＋ 新建产品</ElButton></template>
    </PageHeader>
    <div class="overview-grid" aria-label="产品概览" :aria-busy="loading">
      <section class="overview-item"><span>产品总数</span><strong>{{ loading || productsError ? '—' : productTotal }}</strong></section>
      <section class="overview-item"><span>本页可用</span><strong>{{ loading || productsError ? '—' : products.filter(item => item.design_ready).length }}</strong></section>
      <section class="overview-item"><span>本页待完善</span><strong>{{ loading || productsError ? '—' : products.filter(item => !item.design_ready).length }}</strong></section>
    </div>
    <section class="content-card">
      <div class="collection-heading"><div><h2>产品目录</h2></div></div>
      <div class="toolbar">
        <ElInput v-model="keyword" clearable placeholder="搜索当前页的客户、产品或型号" aria-label="搜索当前页产品" />
        <span v-if="!loading && !productsError">当前页 {{ filteredProducts.length }} 个，共 {{ productTotal }} 个产品</span>
      </div>
      <LoadErrorAlert :message="productsError" :loading="loading" @retry="loadProducts" />
      <ElTable v-if="!productsError" v-table-column-widths="'engineering.products'" v-loading="loading" :data="filteredProducts" table-layout="auto" :empty-text="loading ? '正在加载产品…' : keyword.trim() ? '当前页没有匹配的产品' : '暂无产品'">
        <ElTableColumn prop="customer_name" label="客户" min-width="150" />
        <ElTableColumn label="产品" min-width="220"><template #default="{ row }"><RouterLink class="record-title" :to="{ path: `/products/${row.id}`, query: { mode: 'view' } }">{{ row.product_name }}</RouterLink><small class="record-subtitle">{{ row.factory_code }}</small></template></ElTableColumn>
        <ElTableColumn prop="customer_code" label="客编" min-width="140" />
        <ElTableColumn label="外观版本" min-width="140" show-overflow-tooltip><template #default="{ row }">{{ row.version_value }}</template></ElTableColumn>
        <ElTableColumn label="可用状态" min-width="210">
          <template #default="{ row }">
            <div class="readiness-cell">
              <ElTag :type="row.design_ready ? 'success' : 'danger'" effect="light">
                {{ row.design_ready ? '可用' : '不可用' }}
              </ElTag>
              <span v-if="!row.design_ready">{{ row.design_ready_reason }}</span>
            </div>
          </template>
        </ElTableColumn>
        <ElTableColumn prop="updated_at" label="更新时间" min-width="160" />
        <ElTableColumn label="操作" min-width="120" :fixed="compact ? false : 'right'">
          <template #default="{ row }">
            <div class="row-actions">
              <ElButton
                v-permission="PRODUCT_PERMISSIONS.view"
                link
                @click="router.push({ path: `/products/${row.id}`, query: { mode: 'view'} })"
              >查看</ElButton>
              <ElButton
                v-permission="PRODUCT_PERMISSIONS.edit"
                link
                type="primary"
                @click="router.push({ path: `/products/${row.id}`, query: { mode: 'edit' } })"
              >编辑</ElButton>
            </div>
          </template>
        </ElTableColumn>
      </ElTable>
      <ElPagination
        v-if="!productsError"
        v-model:current-page="page"
        class="pagination"
        layout="prev, pager, next, total"
        :page-size="pageSize"
        :total="productTotal"
        @current-change="loadProducts"
      />
    </section>
  </main>
</template>

<style scoped>
.page-shell { padding: 32px; }
.content-card { min-width: 0; padding: 24px; border: 1px solid var(--erp-border); border-radius: 12px; background: var(--erp-surface); box-shadow: var(--erp-shadow-sm); }
.toolbar { display: flex; align-items: center; justify-content: space-between; gap: 16px; margin: 24px 0 16px; color: var(--erp-text-muted); font-size: 12px; }
.toolbar .el-input { width: min(400px, 100%); }
.row-actions { display: flex; gap: 12px; } .row-actions :deep(.el-button) { margin: 0; }
.readiness-cell { display: grid; justify-items: start; gap: 6px; }
.readiness-cell > span:not(.el-tag) { color: var(--erp-text-muted); font-size: 12px; }
.pagination { margin-top: 24px; }
@media (max-width: 760px) { .page-shell { padding: 24px 16px; } .content-card { padding: 16px; } .toolbar { align-items: stretch; flex-direction: column; } }
</style>
