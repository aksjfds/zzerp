<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { ElMessage } from 'element-plus'
import { useRoute } from 'vue-router'
import { getApiErrorDetail } from '@/api/request'
import { getDepartmentModule } from '@/features/departments/registry'
import DepartmentPageHeader from '../components/DepartmentPageHeader.vue'
import {
  queryDepartmentProductionProgress,
  type DepartmentProductionProgressItem,
} from '../api/productionProgress'
import '../styles/workspace.css'

const props = withDefaults(defineProps<{
  embedded?: boolean
  departmentCode?: string
}>(), {
  embedded: false,
  departmentCode: '',
})
const route = useRoute()
const departmentCode = computed(
  () => String(props.departmentCode || route.meta.departmentCode || ''),
)
const department = computed(() => getDepartmentModule(departmentCode.value))
const items = ref<DepartmentProductionProgressItem[]>([])
const loading = ref(false)
const keyword = ref('')
const page = ref(1)
const pageSize = 50
const total = ref(0)

async function load() {
  if (!departmentCode.value) return
  loading.value = true
  try {
    const result = await queryDepartmentProductionProgress(
      departmentCode.value,
      page.value,
      pageSize,
      keyword.value.trim(),
    )
    items.value = result.data
    total.value = result.total
  } catch (error) {
    ElMessage.error(
      getApiErrorDetail(error)?.message || '生产进度加载失败',
    )
  } finally {
    loading.value = false
  }
}

function search() {
  page.value = 1
  void load()
}

function clear() {
  keyword.value = ''
  search()
}

onMounted(load)
</script>

<template>
  <component :is="embedded ? 'section' : 'main'" :class="{ 'production-page': !embedded }">
    <DepartmentPageHeader
      v-if="!embedded"
      :department-name="department?.name || '生产部门'"
      page-title="生产进度"
      description="生产计划创建后即可查看本部门需要生产的配件或装配体。"
      @refresh="load"
    />

    <section class="progress-panel">
      <div class="progress-toolbar">
        <ElInput
          v-model="keyword"
          clearable
          placeholder="搜索物料编号、物料名称或订单号"
          @clear="search"
          @keyup.enter="search"
        />
        <ElButton type="primary" @click="search">查询</ElButton>
        <ElButton @click="clear">清空</ElButton>
      </div>

      <ElTable
        v-loading="loading"
        :data="items"
        border
        stripe
        table-layout="auto"
        empty-text="暂无生产进度"
      >
        <ElTableColumn prop="part_no" label="物料编号" min-width="150" />
        <ElTableColumn prop="part_name" label="配件/装配体" min-width="180" />
        <ElTableColumn prop="customer_order_no" label="订单号" min-width="160" />
        <ElTableColumn prop="order_date" label="订单日期" width="120" />
        <ElTableColumn prop="order_quantity" label="需求数量" width="110" align="right" />
        <ElTableColumn prop="shipped_quantity" label="累计出货数量" width="140" align="right" />
        <ElTableColumn prop="outstanding_quantity" label="欠交数量" width="110" align="right">
          <template #default="{ row }">
            <span :class="{ outstanding: row.outstanding_quantity > 0 }">
              {{ row.outstanding_quantity }}
            </span>
          </template>
        </ElTableColumn>
        <ElTableColumn prop="completion_date" label="完成日期" width="120">
          <template #default="{ row }">{{ row.completion_date || '—' }}</template>
        </ElTableColumn>
        <ElTableColumn prop="remark" label="备注" min-width="220" show-overflow-tooltip>
          <template #default="{ row }">{{ row.remark || '—' }}</template>
        </ElTableColumn>
      </ElTable>

      <ElPagination
        v-model:current-page="page"
        class="progress-pagination"
        layout="prev, pager, next, total"
        :page-size="pageSize"
        :total="total"
        @current-change="load"
      />
    </section>
  </component>
</template>

<style scoped>
.progress-panel {
  padding: 18px;
  border: 1px solid var(--md-outline-variant);
  border-radius: var(--erp-radius-lg);
  background: var(--md-surface-container-lowest);
  box-shadow: var(--erp-shadow-sm);
}

.progress-toolbar {
  display: grid;
  grid-template-columns: minmax(260px, 520px) auto auto;
  gap: 10px;
  margin-bottom: 16px;
}

.outstanding {
  color: var(--erp-danger);
  font-weight: 700;
}

.progress-pagination {
  justify-content: flex-end;
  margin-top: 16px;
}

@media (max-width: 680px) {
  .progress-panel {
    padding: 12px;
  }

  .progress-toolbar {
    grid-template-columns: 1fr;
  }

  .progress-toolbar :deep(.el-button) {
    width: 100%;
    margin: 0;
  }
}
</style>
