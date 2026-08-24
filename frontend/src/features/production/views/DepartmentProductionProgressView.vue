<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { ElMessage } from 'element-plus'
import { useRoute } from 'vue-router'
import { getApiErrorDetail } from '@/api/request'
import DepartmentPageHeader from '@/shared/layout/DepartmentPageHeader.vue'
import DepartmentProductionTaskTable from '../components/DepartmentProductionTaskTable.vue'
import ProductionProgressItemDrawer from '../components/ProductionProgressItemDrawer.vue'
import {
  queryDepartmentProductionProgress,
} from '../api/productionProgress'
import type { DepartmentProductionProgressItem } from '../domain/productionProgress'
import '../styles/workspace.css'

const props = withDefaults(defineProps<{
  embedded?: boolean
  departmentCode?: string
  departmentName?: string
}>(), {
  embedded: false,
  departmentCode: '',
  departmentName: '生产部门',
})
const route = useRoute()
const departmentCode = computed(
  () => String(props.departmentCode || route.meta.departmentCode || ''),
)
const items = ref<DepartmentProductionProgressItem[]>([])
const loading = ref(false)
const keyword = ref('')
const page = ref(1)
const pageSize = 50
const total = ref(0)
const selectedItem = ref<DepartmentProductionProgressItem | null>(null)
const detailVisible = ref(false)


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
      getApiErrorDetail(error)?.message || '生产任务加载失败',
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

function openDetail(item: DepartmentProductionProgressItem) {
  selectedItem.value = item
  detailVisible.value = true
}

onMounted(load)
</script>

<template>
  <component :is="embedded ? 'section' : 'main'" :class="{ 'production-page': !embedded }">
    <DepartmentPageHeader
      v-if="!embedded"
      :department-name="departmentName"
      page-title="生产任务"
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

      <DepartmentProductionTaskTable
        :items="items"
        :department-code="departmentCode"
        :loading="loading"
        @select="openDetail"
      />

      <ElPagination
        v-model:current-page="page"
        class="progress-pagination"
        layout="prev, pager, next, total"
        :page-size="pageSize"
        :total="total"
        @current-change="load"
      />
    </section>

    <ProductionProgressItemDrawer
      v-model="detailVisible"
      :department-code="departmentCode"
      :item="selectedItem"
    />
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
