<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { storeToRefs } from 'pinia'
import { useRouter } from 'vue-router'
import { useAuthStore } from '@/stores/auth'
import { useEngineeringProductsStore } from '../stores/engineeringProducts'
import { PRODUCT_PERMISSIONS } from '@/permission/constants'

const router = useRouter()
const authStore = useAuthStore()
const store = useEngineeringProductsStore()
const { loading, products, productTotal } = storeToRefs(store)
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

async function logout() {
  await authStore.logout()
  router.replace('/login')
}

onMounted(() => store.loadProducts(page.value, pageSize))
</script>

<template>
  <main class="page-shell">
    <header class="page-header">
      <div>
        <div class="page-kicker">工程部</div>
        <h1>产品工程资料</h1>
        <p>统一维护产品基础信息、BOM 和图形化工艺路线。</p>
      </div>
      <div class="header-actions">
        <ElButton @click="logout">退出登录</ElButton>
        <ElButton
          v-permission="PRODUCT_PERMISSIONS.add"
          type="primary"
          @click="router.push('/products/new')"
        >录入新产品</ElButton>
      </div>
    </header>
    <section class="content-card">
      <div class="toolbar">
        <ElInput v-model="keyword" clearable placeholder="搜索当前页的客户、产品或型号" />
        <span>当前页 {{ filteredProducts.length }} 个，共 {{ productTotal }} 个产品</span>
      </div>
      <ElTable v-loading="loading" :data="filteredProducts" border>
        <ElTableColumn prop="customer_name" label="客户" min-width="150" />
        <ElTableColumn prop="product_name" label="名称" min-width="190" />
        <ElTableColumn prop="factory_code" label="厂编" min-width="140" />
        <ElTableColumn prop="customer_code" label="客编" min-width="140" />
        <ElTableColumn label="版本" width="80"><template #default="{ row }">V{{ row.version }}</template></ElTableColumn>
        <ElTableColumn prop="updated_at" label="更新时间" min-width="160" />
        <ElTableColumn label="操作" width="140" fixed="right">
          <template #default="{ row }">
            <ElButton
              v-permission="PRODUCT_PERMISSIONS.view"
              link
              type="primary"
              @click="router.push({ path: `/products/${row.id}`, query: { mode: 'view'} })"
            >查看</ElButton>
            <ElButton
              v-permission="PRODUCT_PERMISSIONS.edit"
              link
              @click="router.push({ path: `/products/${row.id}`, query: { mode: 'edit' } })"
            >编辑</ElButton>
          </template>
        </ElTableColumn>
      </ElTable>
      <ElPagination
        v-model:current-page="page"
        class="pagination"
        layout="prev, pager, next, total"
        :page-size="pageSize"
        :total="productTotal"
        @current-change="store.loadProducts($event, pageSize)"
      />
    </section>
  </main>
</template>

<style scoped>
.page-shell { min-height: 100vh; padding: var(--erp-page-gutter); background: var(--md-surface); }
.page-header, .content-card { border: 1px solid var(--md-outline-variant); border-radius: var(--erp-radius-lg); background: var(--md-surface-container-lowest); box-shadow: var(--erp-shadow-sm); }
.page-header { display: flex; justify-content: space-between; gap: 24px; margin-bottom: 18px; padding: 20px 24px; background: var(--md-surface-container-lowest); box-shadow: var(--erp-shadow-sm); }
.page-header h1 { margin: 5px 0; font-size: 24px; font-weight: 600; letter-spacing: -.02em; }
.page-header p { margin: 0; color: var(--el-text-color-secondary); }
.page-kicker { color: var(--erp-primary); font-size: 12px; font-weight: 700; }
.header-actions { display: flex; align-items: center; }
.content-card { padding: 20px; }
.toolbar { display: flex; align-items: center; justify-content: space-between; gap: 20px; margin-bottom: 16px; color: var(--el-text-color-secondary); font-size: 13px; }
.toolbar .el-input { max-width: 360px; }
.pagination { justify-content: flex-end; margin-top: 16px; }
@media (max-width: 680px) {
  .page-shell { padding: 16px; }
  .page-header { align-items: flex-start; flex-direction: column; padding: 16px; }
  .header-actions, .header-actions :deep(.el-button) { width: 100%; }
  .content-card { padding: 16px; }
  .toolbar { align-items: stretch; flex-direction: column; gap: 10px; }
  .toolbar .el-input { width: 100%; max-width: none; }
}
@media (max-width: 480px) {
  .page-shell { padding: 12px; }
  .content-card { padding: 12px; }
}
</style>
