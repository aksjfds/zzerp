<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { ElMessage } from 'element-plus'
import { useRouter } from 'vue-router'
import {
  queryDepartmentWorkers,
  queryPolishProcesses,
  queryPolishWorkerOverview,
  queryProducts,
} from '@/api/production'
import { useAuthStore } from '@/stores/auth'
import type {
  PolishProcessStep,
  PolishWorkerOverview,
  ProductItem,
  WorkerItem,
} from '@/types/production'

const department = 'polish' as const
const router = useRouter()
const authStore = useAuthStore()
const loading = ref(false)
const workers = ref<WorkerItem[]>([])
const products = ref<ProductItem[]>([])
const processes = ref<PolishProcessStep[]>([])
const overview = ref<PolishWorkerOverview[]>([])
const selectedWorkerId = ref<number>()
const selectedProductId = ref<number>()
const selectedProcessName = ref<string>()

function formatDate(date: Date) {
  const year = date.getFullYear()
  const month = String(date.getMonth() + 1).padStart(2, '0')
  const day = String(date.getDate()).padStart(2, '0')
  return `${year}-${month}-${day}`
}

function currentMonthRange() {
  const today = new Date()
  return [formatDate(new Date(today.getFullYear(), today.getMonth(), 1)), formatDate(today)]
}

const dateRange = ref<string[]>(currentMonthRange())
const processOptions = computed(() =>
  [...new Set(processes.value.map((item) => item.processName))].sort((left, right) =>
    left.localeCompare(right, 'zh-CN'),
  ),
)
const workerOptions = computed(() => {
  const options = new Map(workers.value.map((worker) => [worker.id, worker.name]))
  overview.value.forEach((worker) => options.set(worker.workerId, worker.workerName))
  return [...options].map(([id, name]) => ({ id, name }))
})

async function loadOverview() {
  const [startDate, endDate] = dateRange.value
  if (!startDate || !endDate) {
    ElMessage.warning('请选择完整的日期范围')
    return
  }

  loading.value = true
  try {
    overview.value = await queryPolishWorkerOverview({
      startDate,
      endDate,
      workerId: selectedWorkerId.value,
      productId: selectedProductId.value,
      processName: selectedProcessName.value,
    })
  } catch {
    ElMessage.error('工人历史统计加载失败')
  } finally {
    loading.value = false
  }
}

async function resetFilters() {
  dateRange.value = currentMonthRange()
  selectedWorkerId.value = undefined
  selectedProductId.value = undefined
  selectedProcessName.value = undefined
  await loadOverview()
}

async function switchUser() {
  await authStore.logout()
  router.replace('/login')
}

async function loadPage() {
  loading.value = true
  try {
    const [startDate, endDate] = dateRange.value
    if (!startDate || !endDate) return
    const [workerData, productData, processData] = await Promise.all([
      queryDepartmentWorkers(department),
      queryProducts(),
      queryPolishProcesses(department),
    ])
    workers.value = workerData
    products.value = productData.filter((product) => product.process.includes(department))
    processes.value = processData
    overview.value = await queryPolishWorkerOverview({
      startDate,
      endDate,
    })
  } catch {
    ElMessage.error('工人总览加载失败')
  } finally {
    loading.value = false
  }
}

onMounted(loadPage)
</script>

<template>
  <main class="dashboard-page">
    <header class="dashboard-header">
      <div class="navbar-title">
        <div class="page-kicker">磨房部门</div>
        <h1>工人工作总览</h1>
      </div>
      <nav class="header-actions" aria-label="磨房导航">
        <ElButton @click="router.push('/dashboard')">产品总览</ElButton>
        <ElButton @click="router.push('/dashboard/polish')">磨房工单</ElButton>
        <ElButton class="nav-current" type="primary" aria-current="page">工人总览</ElButton>
        <ElButton @click="switchUser">切换用户</ElButton>
      </nav>
    </header>

    <section class="section-card filter-card">
      <div class="section-head">
        <div>
          <h2>历史数据筛选</h2>
          <p>按工单结单时间统计，汇总比率按数量加权计算。</p>
        </div>
      </div>
      <div class="filter-grid">
        <ElDatePicker
          v-model="dateRange"
          type="daterange"
          range-separator="至"
          start-placeholder="开始日期"
          end-placeholder="结束日期"
          value-format="YYYY-MM-DD"
          :clearable="false"
        />
        <ElSelect v-model="selectedWorkerId" clearable placeholder="全部工人">
          <ElOption
            v-for="worker in workerOptions"
            :key="worker.id"
            :label="worker.name"
            :value="worker.id"
          />
        </ElSelect>
        <ElSelect v-model="selectedProductId" clearable filterable placeholder="全部产品">
          <ElOption
            v-for="product in products"
            :key="product.id"
            :label="`${product.orderId} · ${product.zzCode} · ${product.productName}`"
            :value="product.id"
          />
        </ElSelect>
        <ElSelect v-model="selectedProcessName" clearable filterable placeholder="全部工艺">
          <ElOption
            v-for="process in processOptions"
            :key="process"
            :label="process"
            :value="process"
          />
        </ElSelect>
        <div class="filter-actions">
          <ElButton type="primary" @click="loadOverview">查询</ElButton>
          <ElButton @click="resetFilters">重置</ElButton>
        </div>
      </div>
    </section>

    <section v-loading="loading" class="worker-list">
      <article v-for="worker in overview" :key="worker.workerId" class="section-card worker-card">
        <div class="worker-head">
          <div>
            <span>磨房工人</span>
            <h2>{{ worker.workerName }}</h2>
          </div>
          <ElTag type="info">已结工单 {{ worker.workOrderCount }} 张</ElTag>
        </div>

        <div class="quantity-grid">
          <div><span>领取/完成</span><strong>{{ worker.issuedQuantity }}/{{ worker.okQuantity }}</strong></div>
          <div><span>报废总数</span><strong>{{ worker.scrapQuantity }}</strong></div>
          <div><span>遗失总数</span><strong>{{ worker.lostQuantity }}</strong></div>
        </div>

        <div class="quantity-grid">
          <div><span>总完成率</span><strong>{{ worker.completionRate }}%</strong></div>
          <div><span>总报废率</span><strong>{{ worker.scrapRate }}%</strong></div>
          <div><span>总遗失率</span><strong>{{ worker.lostRate }}%</strong></div>
        </div>

        <ElCollapse v-if="worker.orders.length" class="order-details">
          <ElCollapseItem :title="`查看 ${worker.orders.length} 张已结工单明细`">
            <ElTable :data="worker.orders" stripe>
              <ElTableColumn prop="workOrderNo" label="工单号" min-width="150" />
              <ElTableColumn label="产品" min-width="210">
                <template #default="{ row }">
                  {{ row.orderId }} · {{ row.zzCode }} · {{ row.productName }}
                </template>
              </ElTableColumn>
              <ElTableColumn prop="processName" label="工艺" min-width="100" />
              <ElTableColumn prop="issuedQuantity" label="领取" width="72" />
              <ElTableColumn prop="okQuantity" label="完成" width="72" />
              <ElTableColumn prop="scrapQuantity" label="报废" width="72" />
              <ElTableColumn prop="lostQuantity" label="遗失" width="72" />
              <ElTableColumn label="完成率" width="88">
                <template #default="{ row }">{{ row.completionRate }}%</template>
              </ElTableColumn>
              <ElTableColumn label="报废率" width="88">
                <template #default="{ row }">{{ row.scrapRate }}%</template>
              </ElTableColumn>
              <ElTableColumn label="遗失率" width="88">
                <template #default="{ row }">{{ row.lostRate }}%</template>
              </ElTableColumn>
              <ElTableColumn prop="closedAt" label="结单时间" min-width="150" />
            </ElTable>
          </ElCollapseItem>
        </ElCollapse>
        <ElEmpty v-else description="所选范围内没有已结工单" :image-size="56" />
      </article>
      <ElEmpty v-if="!loading && overview.length === 0" description="暂无磨房工人数据" />
    </section>
  </main>
</template>

<style scoped>
.dashboard-page {
  min-height: 100vh;
  padding: 22px;
  background: var(--erp-bg);
}

.dashboard-header,
.section-card {
  border: 1px solid var(--erp-border);
  border-radius: 8px;
  background: #fff;
  box-shadow: var(--erp-shadow-sm);
}

.dashboard-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 20px;
  margin-bottom: 18px;
  padding: 16px 20px;
}

.navbar-title h1,
.section-head h2,
.worker-head h2 { margin: 6px 0 0; }
.page-kicker,
.worker-head span { color: var(--erp-primary); font-size: 12px; font-weight: 700; }
.header-actions { display: flex; flex-wrap: wrap; justify-content: flex-end; gap: 8px; }
.header-actions :deep(.el-button + .el-button) { margin-left: 0; }
.nav-current { pointer-events: none; }
.section-card { padding: 18px; }
.filter-card { margin-bottom: 18px; }
.section-head { margin-bottom: 16px; }
.section-head p { margin: 6px 0 0; color: var(--erp-text-muted); }
.filter-grid {
  display: grid;
  grid-template-columns: minmax(260px, 1.2fr) repeat(3, minmax(150px, 1fr)) auto;
  gap: 12px;
}
.filter-grid :deep(.el-date-editor),
.filter-grid :deep(.el-select) { width: 100%; }
.filter-actions { display: flex; gap: 8px; }
.filter-actions :deep(.el-button + .el-button) { margin-left: 0; }
.worker-list { display: grid; gap: 18px; min-height: 120px; }
.worker-head { display: flex; align-items: center; justify-content: space-between; gap: 12px; }
.quantity-grid {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 10px;
  margin: 18px 0;
}
.quantity-grid div { padding: 12px; border-radius: 8px; background: var(--erp-surface-muted); }
.quantity-grid span { display: block; color: var(--erp-text-muted); font-size: 12px; }
.quantity-grid strong { display: block; margin-top: 5px; font-size: 20px; }
.rate-grid { display: grid; grid-template-columns: repeat(3, 1fr); gap: 18px; }
.rate-item { display: grid; gap: 8px; }
.rate-item > span { color: var(--erp-text-muted); font-size: 13px; }
.order-details { margin-top: 18px; }

@media (max-width: 1000px) {
  .filter-grid { grid-template-columns: 1fr 1fr; }
  .rate-grid { grid-template-columns: 1fr; }
}

@media (max-width: 640px) {
  .dashboard-page { padding: 12px; }
  .dashboard-header,
  .worker-head { align-items: flex-start; flex-direction: column; }
  .header-actions { justify-content: flex-start; width: 100%; }
  .filter-grid,
  .quantity-grid { grid-template-columns: 1fr; }
}
</style>
