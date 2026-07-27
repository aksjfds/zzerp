<script setup lang="ts">
import { computed, onMounted, reactive, ref } from 'vue'
import { ElMessage } from 'element-plus'
import { getApiErrorDetail } from '@/api/request'
import PartDepartmentProgressCell from '../components/PartDepartmentProgressCell.vue'
import { queryPmcPartProgress } from '../api/pmcPartProgress'
import type {
  PmcPartProgressRow,
  PmcProgressDepartment,
} from '../domain/pmcPartProgress'

const rows = ref<PmcPartProgressRow[]>([])
const departments = ref<PmcProgressDepartment[]>([])
const loading = ref(false)
const page = ref(1)
const pageSize = 50
const total = ref(0)
const filters = reactive({
  keyword: '',
  orderStatus: '',
  departmentCode: '',
  onlyException: false,
  onlyUnfinished: false,
})
const visibleDepartments = computed(() => filters.departmentCode
  ? departments.value.filter(item => item.department_code === filters.departmentCode)
  : departments.value)

async function load() {
  loading.value = true
  try {
    const result = await queryPmcPartProgress({
      page: page.value,
      page_size: pageSize,
      keyword: filters.keyword.trim() || undefined,
      order_status: filters.orderStatus || undefined,
      department_code: filters.departmentCode || undefined,
      only_exception: filters.onlyException || undefined,
      only_unfinished: filters.onlyUnfinished || undefined,
    })
    rows.value = result.data
    total.value = result.total
    departments.value = result.departments
  } catch (error) {
    ElMessage.error(getApiErrorDetail(error)?.message || '配件生产进度加载失败')
  } finally {
    loading.value = false
  }
}

function search() {
  page.value = 1
  void load()
}

function clear() {
  Object.assign(filters, {
    keyword: '',
    orderStatus: '',
    departmentCode: '',
    onlyException: false,
    onlyUnfinished: false,
  })
  search()
}

onMounted(load)
defineExpose({ load })
</script>

<template>
  <section class="pmc-part-progress">
    <div class="progress-filters">
      <ElInput
        v-model="filters.keyword"
        clearable
        placeholder="搜索订单号、客户、厂编、产品或配件"
        @clear="search"
        @keyup.enter="search"
      />
      <ElSelect
        v-model="filters.orderStatus"
        placement="top-start"
        :fallback-placements="['top-start', 'top-end']"
        clearable
        placeholder="订单状态"
      >
        <ElOption label="草稿" value="draft" />
        <ElOption label="已确认" value="confirmed" />
        <ElOption label="生产中" value="planned" />
        <ElOption label="已完成" value="closed" />
        <ElOption label="已取消" value="cancelled" />
      </ElSelect>
      <ElSelect
        v-model="filters.departmentCode"
        placement="top-start"
        :fallback-placements="['top-start', 'top-end']"
        clearable
        placeholder="部门"
      >
        <ElOption
          v-for="department in departments"
          :key="department.department_code"
          :label="department.department_name"
          :value="department.department_code"
        />
      </ElSelect>
      <ElCheckbox v-model="filters.onlyUnfinished">仅未完成</ElCheckbox>
      <ElCheckbox v-model="filters.onlyException">仅异常</ElCheckbox>
      <ElButton type="primary" @click="search">查询</ElButton>
      <ElButton @click="clear">清空</ElButton>
    </div>

    <ElTable
      v-loading="loading"
      :data="rows"
      border
      class="progress-matrix"
      empty-text="暂无符合条件的配件"
    >
      <ElTableColumn fixed label="配件" width="260">
        <template #default="{ row }">
          <strong>{{ row.part_display_name }}</strong>
          <p>{{ row.customer_name }} · 订单 {{ row.customer_order_no }}</p>
        </template>
      </ElTableColumn>
      <ElTableColumn
        v-for="department in visibleDepartments"
        :key="department.department_code"
        :label="department.department_name"
        min-width="190"
      >
        <template #default="{ row }">
          <PartDepartmentProgressCell
            :item="row.departments[department.department_code]"
            :department-code="department.department_code"
          />
        </template>
      </ElTableColumn>
      <ElTableColumn label="需求" width="82" align="center">
        <template #default="{ row }">{{ row.target_quantity }}</template>
      </ElTableColumn>
      <ElTableColumn label="交期" width="112">
        <template #default="{ row }">{{ row.delivery_date }}</template>
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
</template>

<style scoped>
.pmc-part-progress {
  padding: 20px;
  border: 1px solid var(--erp-border);
  border-radius: var(--erp-radius-lg);
  background: var(--md-surface-container-lowest);
  box-shadow: var(--erp-shadow-sm);
}
.progress-filters {
  display: grid;
  grid-template-columns: minmax(260px, 1fr) 150px 160px auto auto auto auto;
  gap: 10px;
  align-items: center;
  margin-bottom: 16px;
}
.progress-matrix :deep(.el-table__cell) { vertical-align: top; }
.progress-matrix strong { font-size: 13px; }
.progress-matrix p { margin: 5px 0 0; color: var(--el-text-color-secondary); font-size: 12px; }
.progress-pagination { justify-content: flex-end; margin-top: 16px; }
@media (max-width: 1100px) {
  .progress-filters { grid-template-columns: repeat(3, minmax(0, 1fr)); }
}
@media (max-width: 680px) {
  .pmc-part-progress { padding: 12px; border-radius: var(--erp-radius); }
  .progress-filters { grid-template-columns: 1fr; }
  .progress-filters :deep(.el-button) { width: 100%; margin: 0; }
}
</style>
